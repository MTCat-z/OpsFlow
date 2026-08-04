"""
探针任务超时检查 -- Celery Beat 定时任务

- pending 超 30 分钟 -> failed（探针未拉取）
- running 超 30 分钟 -> failed（探针拉走未回传）
心跳离线由前端按 probe_last_heartbeat 实时计算，无需此处处理。
"""
import logging
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.tasks.worker import celery_app
from app.core.database import engine
from app.models.scan_task import ScanTask
from app.models.iperf_task import IperfTask

logger = logging.getLogger(__name__)

TIMEOUT_MINUTES = 30
TIMEOUT_MESSAGE = '探针未响应，请检查探针状态'


@celery_app.task(name='app.tasks.probe_tasks.check_probe_task_timeout')
def check_probe_task_timeout():
    """每 5 分钟检查一次扫描/测速任务是否超时"""
    threshold = datetime.utcnow() - timedelta(minutes=TIMEOUT_MINUTES)
    timed_out = 0
    with Session(engine) as session:
        # 扫描任务：pending 未被拉取 / running 未回传
        scan_stale = session.exec(
            select(ScanTask).where(
                ScanTask.status.in_(['pending', 'running']),
            )
        ).all()
        for t in scan_stale:
            ref = t.started_at if t.status == 'running' else t.created_at
            if ref and ref < threshold:
                t.status = 'failed'
                t.error_message = TIMEOUT_MESSAGE
                t.finished_at = datetime.utcnow()
                session.add(t)
                timed_out += 1
                logger.warning('扫描任务 #%d 超时（%s 自 %s）', t.id, t.status, ref)

        # 测速任务：同上
        iperf_stale = session.exec(
            select(IperfTask).where(
                IperfTask.status.in_(['pending', 'running']),
            )
        ).all()
        for t in iperf_stale:
            ref = t.started_at if t.status == 'running' else t.created_at
            if ref and ref < threshold:
                t.status = 'failed'
                t.error_message = TIMEOUT_MESSAGE
                t.finished_at = datetime.utcnow()
                session.add(t)
                timed_out += 1
                logger.warning('测速任务 #%d 超时（%s 自 %s）', t.id, t.status, ref)

        session.commit()
    return {'timed_out': timed_out, 'threshold_minutes': TIMEOUT_MINUTES}
