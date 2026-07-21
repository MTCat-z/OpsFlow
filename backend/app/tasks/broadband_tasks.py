"""
宽带合同到期提醒 -- Celery Beat 定时任务
"""
import json
import logging
from datetime import date, datetime
from sqlmodel import Session, select
from app.tasks.worker import celery_app
from app.core.database import engine
from app.models.broadband import BroadbandContract
from app.services.broadband_renewal import get_renewal_deadlines
from app.services.dingtalk import send_renewal_reminder

logger = logging.getLogger(__name__)


@celery_app.task(name='app.tasks.broadband_tasks.check_broadband_renewals')
def check_broadband_renewals():
    today = date.today()
    today_str = today.isoformat()
    with Session(engine) as session:
        contracts = session.exec(
            select(BroadbandContract).where(BroadbandContract.status == 'active')
        ).all()
        for contract in contracts:
            _process_contract(session, contract, today, today_str)
        session.commit()
    return {'checked': len(contracts), 'date': today_str}


def _process_contract(session, contract, today, today_str):
    if (contract.contract_end - today).days < 0:
        contract.status = 'expired'
        contract.updated_at = datetime.utcnow()
        session.add(contract)
        return
    try:
        reminder_list = [int(d.strip()) for d in contract.reminder_days.split(',') if d.strip()]
    except (ValueError, AttributeError):
        reminder_list = [30, 15, 7]
    renewal_deadlines = get_renewal_deadlines(
        contract.contract_start, contract.contract_end, contract.renewal_cycle
    )
    nearest_deadline = None
    nearest_days = None
    deadline_type = None
    for dl in renewal_deadlines:
        dr = (dl - today).days
        if dr < 0:
            continue
        if dr in reminder_list:
            if nearest_deadline is None or dr < nearest_days:
                nearest_deadline = dl
                nearest_days = dr
                deadline_type = 'cycle' if dl != contract.contract_end else 'contract_end'
    if nearest_deadline is None:
        return
    notified = []
    if contract.notified_dates:
        try:
            notified = json.loads(contract.notified_dates)
        except (json.JSONDecodeError, TypeError):
            notified = []
    if today_str in notified:
        return
    ok = send_renewal_reminder(
        provider=contract.provider,
        circuit_id=contract.circuit_id,
        bandwidth_mbps=contract.bandwidth_mbps,
        location=contract.location,
        contract_end=contract.contract_end,
        renewal_deadline=nearest_deadline,
        days_remaining=nearest_days,
        contact_name=contract.contact_name,
        deadline_type=deadline_type,
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
            '宽带续费提醒已发送: %s (%s), 截止 %s, 剩余 %d 天',
            contract.provider, contract.circuit_id, nearest_deadline, nearest_days,
        )
    else:
        logger.warning(
            '宽带续费提醒发送失败: %s (%s)',
            contract.provider, contract.circuit_id,
        )
