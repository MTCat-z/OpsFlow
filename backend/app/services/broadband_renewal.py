"""
宽带续费周期计算工具

将续费截止日的计算从 broadband_tasks.py 抽离复用，
供定时任务、仪表盘、列表/详情、测试通知等共用同一套逻辑。
"""
import calendar
from datetime import date, timedelta

from app.models.broadband import RENEWAL_CYCLE_MONTHS


def _add_months(src: date, n: int) -> date:
    """给日期加 N 个月，月末自动修正（如 1-31 + 1 月 -> 2-28/29）"""
    total = src.month - 1 + n
    year = src.year + total // 12
    month = total % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(src.day, last_day))


def get_renewal_deadlines(
    contract_start: date, contract_end: date, renewal_cycle: str
) -> list[date]:
    """根据续费周期计算所有续费截止日期（含合同到期日）"""
    months = RENEWAL_CYCLE_MONTHS.get(renewal_cycle, 12)
    if months <= 0 or months >= 120:
        return [contract_end]
    deadlines = []
    cursor = contract_start
    while True:
        next_start = _add_months(cursor, months)
        dl = next_start - timedelta(days=1)
        if dl >= contract_end:
            if not deadlines or deadlines[-1] != contract_end:
                deadlines.append(contract_end)
            break
        deadlines.append(dl)
        cursor = next_start
    return deadlines


def get_next_renewal(contract, today: date = None) -> dict:
    """
    计算合同的下一个续费截止日。

    逻辑：
    - 如果已标记续费（last_renewed_date），从续费日开始加一个周期算截止日
    - 否则算出所有续费截止日，找下一个未过去的；若全过去则用 contract_end

    返回 dict:
        - next_deadline: 下一个续费截止日（date）
        - days_remaining: (next_deadline - today).days
        - deadline_type: 'cycle' 或 'contract_end'
    """
    if today is None:
        today = date.today()

    # 如果已标记续费，从续费日开始算下一个周期截止日
    last_renewed = getattr(contract, 'last_renewed_date', None)
    if last_renewed:
        months = RENEWAL_CYCLE_MONTHS.get(contract.renewal_cycle, 12)
        next_start = _add_months(last_renewed, months)
        next_deadline = next_start - timedelta(days=1)
        # 不能超过合同到期日
        if next_deadline >= contract.contract_end:
            next_deadline = contract.contract_end
            deadline_type = 'contract_end'
        else:
            deadline_type = 'cycle'
        days_remaining = (next_deadline - today).days
        return {
            'next_deadline': next_deadline,
            'days_remaining': days_remaining,
            'deadline_type': deadline_type,
        }

    # 未标记续费，按原逻辑从合同开始日算所有截止日
    deadlines = get_renewal_deadlines(
        contract.contract_start, contract.contract_end, contract.renewal_cycle
    )
    next_deadline = None
    for dl in deadlines:
        if dl >= today:
            next_deadline = dl
            break
    if next_deadline is None:
        next_deadline = contract.contract_end
    deadline_type = 'cycle' if next_deadline != contract.contract_end else 'contract_end'
    days_remaining = (next_deadline - today).days
    return {
        'next_deadline': next_deadline,
        'days_remaining': days_remaining,
        'deadline_type': deadline_type,
    }
