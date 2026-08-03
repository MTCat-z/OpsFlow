import logging
from datetime import datetime

from sqlmodel import Session, select

from app.tasks.worker import celery_app
from app.core.database import engine
from app.models.asset import Asset
from app.models.command import CommandBatch, CommandResult
from app.services.command_guard import check_dangerous_commands
from app.services.ssh_executor import execute_ssh_command_with_asset

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='app.tasks.command_tasks.run_command_batch')
def run_command_batch(self, batch_id: int):
    """执行批量命令：安全检查 → 遍历资产 → SSH 执行 → 保存结果"""
    with Session(engine) as session:
        batch = session.get(CommandBatch, batch_id)
        if not batch:
            return {'error': f'Batch {batch_id} not found'}

        commands_text = batch.commands
        asset_ids_str = batch.asset_ids
        celery_task_id = self.request.id

        # 更新状态为 running
        batch.status = 'running'
        batch.started_at = datetime.utcnow()
        batch.celery_task_id = celery_task_id
        session.add(batch)
        session.commit()

    # 二次安全检查（防止绕过 API 直接调用）
    guard = check_dangerous_commands(commands_text)
    if not guard['safe']:
        with Session(engine) as session:
            batch = session.get(CommandBatch, batch_id)
            if batch:
                batch.status = 'blocked'
                batch.summary = f"危险命令被拦截: {'; '.join(guard['reasons'][:3])}"
                batch.finished_at = datetime.utcnow()
                session.add(batch)
                session.commit()
        return {'error': 'dangerous commands blocked', 'reasons': guard['reasons']}

    # 加载资产列表（按 batch.org_id 过滤，防止跨租户执行）
    with Session(engine) as session:
        if asset_ids_str and asset_ids_str.strip():
            ids = [int(x.strip()) for x in asset_ids_str.split(',') if x.strip().isdigit()]
            if ids:
                assets = session.exec(
                    select(Asset).where(Asset.id.in_(ids), Asset.org_id == batch.org_id)
                ).all()
                logger.info(
                    'Command batch %s asset filter: requested=%d, matched=%d (org_id=%s)',
                    batch_id, len(ids), len(assets), batch.org_id,
                )
            else:
                assets = []
        else:
            assets = []

    if not assets:
        with Session(engine) as session:
            batch = session.get(CommandBatch, batch_id)
            if batch:
                batch.status = 'failed'
                batch.summary = '无可执行的目标资产'
                batch.finished_at = datetime.utcnow()
                session.add(batch)
                session.commit()
        return {'error': 'no target assets'}

    success_count = 0
    fail_count = 0

    for asset in assets:
        try:
            result = execute_ssh_command_with_asset(asset, commands_text, timeout=60)

            cmd_result = CommandResult(
                batch_id=batch_id,
                asset_id=asset.id,
                asset_name=asset.name,
                status='success' if result['success'] else 'failed',
                output=result.get('output', '')[:10000],
                error_message=result.get('error', '')[:500] if not result['success'] else None,
            )
            with Session(engine) as session:
                session.add(cmd_result)
                session.commit()

            if result['success']:
                success_count += 1
            else:
                fail_count += 1

        except Exception as e:
            logger.error('Command execution failed for %s: %s', asset.name, e)
            cmd_result = CommandResult(
                batch_id=batch_id,
                asset_id=asset.id,
                asset_name=asset.name,
                status='failed',
                output='',
                error_message=str(e)[:500],
            )
            with Session(engine) as session:
                session.add(cmd_result)
                session.commit()
            fail_count += 1

    # 更新批次状态
    with Session(engine) as session:
        batch = session.get(CommandBatch, batch_id)
        if batch:
            batch.status = 'completed' if fail_count == 0 else 'partial'
            batch.finished_at = datetime.utcnow()
            batch.summary = f'执行完成: 成功 {success_count}, 失败 {fail_count}, 共 {len(assets)} 台设备'
            session.add(batch)
            session.commit()

    logger.info(
        'Command batch %s completed: success=%d, failed=%d, total=%d',
        batch_id, success_count, fail_count, len(assets),
    )
    return {
        'batch_id': batch_id,
        'success': success_count,
        'failed': fail_count,
        'total': len(assets),
    }
