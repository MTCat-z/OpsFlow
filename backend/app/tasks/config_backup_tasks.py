import difflib
import hashlib
import logging
from datetime import datetime

from sqlmodel import Session, select

from app.tasks.worker import celery_app
from app.core.database import engine
from app.models.asset import Asset
from app.models.config_backup import ConfigBackupJob, ConfigSnapshot
from app.services.ssh_executor import execute_ssh_command_with_asset

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='app.tasks.config_backup_tasks.run_config_backup')
def run_config_backup(self, job_id: int):
    """执行配置备份任务：对匹配的资产逐一 SSH 拉取配置，保存快照并计算 diff"""
    with Session(engine) as session:
        job = session.get(ConfigBackupJob, job_id)
        if not job:
            return {'error': f'Job {job_id} not found'}
        command = job.command or 'show running-config'
        asset_filter = job.asset_filter  # 逗号分隔的 asset_id 列表，空则全部

    # 加载资产列表
    with Session(engine) as session:
        if asset_filter and asset_filter.strip():
            ids = [int(x.strip()) for x in asset_filter.split(',') if x.strip().isdigit()]
            if ids:
                assets = session.exec(
                    select(Asset).where(Asset.id.in_(ids), Asset.org_id == job.org_id)
                ).all()
            else:
                assets = session.exec(
                    select(Asset).where(Asset.status == 'active', Asset.org_id == job.org_id)
                ).all()
        else:
            assets = session.exec(
                select(Asset).where(Asset.status == 'active', Asset.org_id == job.org_id)
            ).all()

    if not assets:
        return {'error': '无匹配的资产', 'job_id': job_id}

    success_count = 0
    fail_count = 0
    unchanged_count = 0
    changed_count = 0

    for asset in assets:
        try:
            result = execute_ssh_command_with_asset(asset, command, timeout=60)
            now = datetime.utcnow()

            if not result['success']:
                # 创建失败快照
                snap = ConfigSnapshot(
                    job_id=job_id,
                    asset_id=asset.id,
                    asset_name=asset.name,
                    config_text='',
                    status='failed',
                    diff_summary=result.get('error', 'SSH 执行失败')[:500],
                )
                with Session(engine) as session:
                    session.add(snap)
                    session.commit()
                fail_count += 1
                continue

            config_text = result['output']
            content_hash = hashlib.sha256(config_text.encode('utf-8')).hexdigest()

            # 查找同资产的上一份成功快照，计算 diff
            diff_summary = None
            with Session(engine) as session:
                prev = session.exec(
                    select(ConfigSnapshot)
                    .where(ConfigSnapshot.asset_id == asset.id)
                    .where(ConfigSnapshot.status == 'captured')
                    .order_by(ConfigSnapshot.created_at.desc())
                    .limit(1)
                ).first()

                if prev and prev.config_text:
                    if prev.content_hash == content_hash:
                        # 配置无变化
                        unchanged_count += 1
                        diff_summary = None
                    else:
                        # 计算 unified diff
                        old_lines = prev.config_text.splitlines(keepends=True)
                        new_lines = config_text.splitlines(keepends=True)
                        diff_lines = list(difflib.unified_diff(
                            old_lines, new_lines,
                            fromfile=f'{asset.name} (prev)',
                            tofile=f'{asset.name} (current)',
                            lineterm='',
                        ))
                        diff_summary = ''.join(diff_lines)[:2000] if diff_lines else None
                        changed_count += 1
                else:
                    changed_count += 1  # 首次备份

            # 保存快照
            snap = ConfigSnapshot(
                job_id=job_id,
                asset_id=asset.id,
                asset_name=asset.name,
                config_text=config_text,
                content_hash=content_hash,
                diff_summary=diff_summary,
                status='captured',
            )
            with Session(engine) as session:
                session.add(snap)
                session.commit()
            success_count += 1

        except Exception as e:
            logger.error('Config backup failed for %s: %s', asset.name, e)
            snap = ConfigSnapshot(
                job_id=job_id,
                asset_id=asset.id,
                asset_name=asset.name,
                config_text='',
                status='failed',
                diff_summary=str(e)[:500],
            )
            with Session(engine) as session:
                session.add(snap)
                session.commit()
            fail_count += 1

    logger.info(
        'Config backup job %s completed: success=%d, failed=%d, changed=%d, unchanged=%d',
        job_id, success_count, fail_count, changed_count, unchanged_count,
    )
    return {
        'job_id': job_id,
        'success': success_count,
        'failed': fail_count,
        'changed': changed_count,
        'unchanged': unchanged_count,
    }


@celery_app.task(name='app.tasks.config_backup_tasks.run_config_backup_scheduled')
def run_config_backup_scheduled():
    """遍历所有启用的备份任务并触发执行"""
    with Session(engine) as session:
        jobs = session.exec(
            select(ConfigBackupJob).where(ConfigBackupJob.enabled == True)
        ).all()

    triggered = 0
    for job in jobs:
        try:
            run_config_backup.delay(job.id)
            triggered += 1
        except Exception as e:
            logger.error('Failed to trigger config backup for job %s: %s', job.id, e)

    return {'triggered': triggered, 'total': len(jobs)}
