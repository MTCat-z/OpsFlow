import json
import logging
from datetime import datetime, date

from sqlmodel import Session, select

from app.tasks.worker import celery_app
from app.core.database import engine
from app.models.inspection import InspectionPlan, InspectionRun
from app.models.asset import Asset
from app.models.broadband import BroadbandContract
from app.services.diagnostics import run_ping, run_port_check
from app.services.dingtalk import send_inspection_report

logger = logging.getLogger(__name__)


def _check_ping(ip: str) -> dict:
    result = run_ping(ip, count=2, timeout=5)
    return {
        'target': ip,
        'check': 'ping',
        'status': 'ok' if result['success'] else 'error',
        'detail': result.get('output', '')[:200],
    }


def _check_port(ip: str, port: int = 22) -> dict:
    result = run_port_check(ip, port, timeout=5)
    return {
        'target': ip,
        'check': f'port:{port}',
        'status': 'ok' if result.get('open') else ('warning' if result['success'] else 'error'),
        'detail': result.get('output', '')[:200],
    }


def _check_broadband_expiry() -> list[dict]:
    """检查即将到期的宽带合同"""
    results = []
    today = date.today()
    with Session(engine) as session:
        contracts = session.exec(
            select(BroadbandContract).where(BroadbandContract.status == 'active')
        ).all()
        for c in contracts:
            days = (c.contract_end - today).days
            if days <= 30:
                status = 'error' if days <= 7 else 'warning'
                results.append({
                    'target': f'{c.provider} ({c.circuit_id or c.id})',
                    'check': 'broadband_expiry',
                    'status': status,
                    'detail': f'到期日 {c.contract_end}，剩余 {days} 天',
                })
    return results


# 检查项注册表
CHECK_REGISTRY = {
    'ping': lambda asset: _check_ping(asset.ip_address),
    'port': lambda asset: _check_port(asset.ip_address, asset.ssh_port or 22),
    'broadband_expiry': lambda asset: None,  # 全局检查，不针对单个资产
}


@celery_app.task(bind=True, name='app.tasks.inspection_tasks.run_inspection')
def run_inspection(self, plan_id: int, run_id: int = None):
    """执行巡检方案"""
    with Session(engine) as session:
        plan = session.get(InspectionPlan, plan_id)
        if not plan:
            return {'error': f'Plan {plan_id} not found'}

        # 如果没有传入 run_id，创建一个
        if not run_id:
            run = InspectionRun(plan_id=plan.id, status='pending')
            session.add(run)
            session.commit()
            session.refresh(run)
            run_id = run.id

        run = session.get(InspectionRun, run_id)
        if not run:
            return {'error': f'Run {run_id} not found'}

        run.status = 'running'
        run.started_at = datetime.utcnow()
        run.celery_task_id = self.request.id
        session.add(run)
        session.commit()

        # 解析检查项
        checks = [c.strip() for c in plan.checks.split(',') if c.strip()]
        scope = plan.scope

    try:
        # 获取目标资产
        with Session(engine) as session:
            assets = session.exec(select(Asset).where(Asset.status == 'active')).all()

        report_items = []
        exception_count = 0
        summary_lines = []

        for asset in assets:
            for check_name in checks:
                if check_name == 'broadband_expiry':
                    continue  # 全局检查，后面单独处理
                checker = CHECK_REGISTRY.get(check_name)
                if not checker:
                    continue
                try:
                    result = checker(asset)
                    if result:
                        result['asset'] = f'{asset.name} ({asset.ip_address})'
                        report_items.append(result)
                        if result['status'] in ('error', 'warning'):
                            exception_count += 1
                            summary_lines.append(f"{asset.name}: {result['check']} — {result['detail'][:80]}")
                except Exception as e:
                    report_items.append({
                        'asset': f'{asset.name} ({asset.ip_address})',
                        'check': check_name,
                        'status': 'error',
                        'detail': str(e)[:200],
                    })
                    exception_count += 1

        # 宽带到期检查（全局）
        if 'broadband_expiry' in checks:
            bb_results = _check_broadband_expiry()
            for r in bb_results:
                report_items.append(r)
                exception_count += 1
                summary_lines.append(f"{r['target']}: {r['detail']}")

        # 写入结果
        with Session(engine) as session:
            run = session.get(InspectionRun, run_id)
            run.status = 'completed'
            run.finished_at = datetime.utcnow()
            run.exception_count = exception_count
            run.report_json = json.dumps(report_items, ensure_ascii=False)
            run.summary = f'检查 {len(assets)} 台资产，{len(checks)} 项检查，发现 {exception_count} 个异常'
            session.add(run)

            # 钉钉通知
            plan = session.get(InspectionPlan, plan_id)
            if plan and plan.notify_dingtalk and exception_count > 0:
                try:
                    send_inspection_report(plan.name, exception_count, summary_lines)
                    run.notified = True
                    session.add(run)
                except Exception as e:
                    logger.warning('DingTalk notification failed: %s', e)

            session.commit()

        return {
            'run_id': run_id,
            'status': 'completed',
            'exception_count': exception_count,
            'assets_checked': len(assets),
        }

    except Exception as e:
        with Session(engine) as session:
            run = session.get(InspectionRun, run_id)
            if run:
                run.status = 'failed'
                run.finished_at = datetime.utcnow()
                run.summary = str(e)[:500]
                session.add(run)
                session.commit()
        logger.error('Inspection failed: %s', e)
        raise


@celery_app.task(name='app.tasks.inspection_tasks.run_inspection_scheduled')
def run_inspection_scheduled():
    """遍历所有启用的巡检方案并触发执行"""
    with Session(engine) as session:
        plans = session.exec(
            select(InspectionPlan).where(InspectionPlan.enabled == True)
        ).all()

    triggered = 0
    for plan in plans:
        try:
            run_inspection.delay(plan.id)
            triggered += 1
        except Exception as e:
            logger.error('Failed to trigger inspection for plan %s: %s', plan.id, e)

    return {'triggered': triggered, 'total': len(plans)}
