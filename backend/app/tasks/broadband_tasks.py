"""
宽带合同到期提醒 — Celery Beat 定时任务
"""
import json
import logging
from datetime import date, datetime
from sqlmodel import Session, select
from app.tasks.worker import celery_app
from app.core.database import engine
from app.models.broadband import BroadbandContract
from app.services.dingtalk import send_renewal_reminder

logger = logging.getLogger(__name__)


@celery_app.task(name='app.tasks.broadband_tasks.check_broadband_renewals')
def check_broadband_renewals():
    """每日检查宽带合同到期情况并发送提醒"""
    today = date.today()
    today_str = today.isoformat()

    with Session(engine) as session:
        contracts = session.exec(
            select(BroadbandContract).where(BroadbandContract.status == 'active')
        ).all()

        for contract in contracts:
            days_remaining = (contract.contract_end - today).days

            # 标记已过期合同
            if days_remaining < 0:
                contract.status = 'expired'
                contract.updated_at = datetime.utcnow()
                session.add(contract)
                continue

            # 解析提醒天数
            try:
                reminder_list = [int(d.strip()) for d in contract.reminder_days.split(',') if d.strip()]
            except (ValueError, AttributeError):
                reminder_list = [30, 15, 7]

            # 检查是否需要发送提醒
            if days_remaining not in reminder_list:
                continue

            # 检查今天是否已发送过
            notified = []
            if contract.notified_dates:
                try:
                    notified = json.loads(contract.notified_dates)
                except (json.JSONDecodeError, TypeError):
                    notified = []

            if today_str in notified:
                continue

            # 发送提醒
            ok = send_renewal_reminder(
                provider=contract.provider,
                circuit_id=contract.circuit_id,
                bandwidth_mbps=contract.bandwidth_mbps,
                location=contract.location,
                contract_end=contract.contract_end,
                days_remaining=days_remaining,
                contact_name=contract.contact_name,
                renewal_cycle=contract.renewal_cycle,
                renewal_cost=contract.renewal_cost,
                annual_cost=contract.annual_cost,
            )

            if ok:
                notified.append(today_str)
                contract.notified_dates = json.dumps(notified)
                contract.updated_at = datetime.utcnow()
                session.add(contract)
                logger.info(
                    '宽带续费提醒已发送: %s (%s), 剩余 %d 天',
                    contract.provider, contract.circuit_id, days_remaining,
                )
            else:
                logger.warning(
                    '宽带续费提醒发送失败: %s (%s)',
                    contract.provider, contract.circuit_id,
                )

        session.commit()

    return {'checked': len(contracts), 'date': today_str}
