from datetime import datetime, date
from typing import Optional
from sqlmodel import Field, SQLModel


# 续费周期映射（月数）
RENEWAL_CYCLE_MONTHS = {
    'monthly': 1,
    'quarterly': 3,
    'semi_annual': 6,
    'annual': 12,
}

RENEWAL_CYCLE_LABELS = {
    'monthly': '每月',
    'quarterly': '每季度（3个月）',
    'semi_annual': '每半年（6个月）',
    'annual': '每年',
}


def calc_annual_cost(renewal_cost: Optional[float], renewal_cycle: str) -> Optional[float]:
    """根据续费金额和周期自动计算年费"""
    if renewal_cost is None:
        return None
    months = RENEWAL_CYCLE_MONTHS.get(renewal_cycle, 12)
    return round(renewal_cost * (12 / months), 2)


class BroadbandContractBase(SQLModel):
    provider: str = Field(..., max_length=100)
    circuit_id: Optional[str] = Field(default=None, max_length=100)
    bandwidth_mbps: int = Field(...)
    location: Optional[str] = Field(default=None, max_length=200)
    # 续费周期 & 金额
    renewal_cycle: str = Field(default='annual', max_length=20)  # monthly/quarterly/semi_annual/annual
    renewal_cost: Optional[float] = Field(default=None)  # 每周期续费金额
    annual_cost: Optional[float] = Field(default=None)   # 年度费用（可自动计算，也支持手动填写）
    monthly_cost: Optional[float] = Field(default=None)   # 保留，月费
    contract_start: date = Field(...)
    contract_end: date = Field(..., index=True)
    auto_renew: bool = Field(default=False)
    contact_name: Optional[str] = Field(default=None, max_length=50)
    contact_phone: Optional[str] = Field(default=None, max_length=30)
    reminder_days: str = Field(default='30,15,7', max_length=100)
    status: str = Field(default='active', max_length=20, index=True)
    notes: Optional[str] = Field(default=None, max_length=2000)


class BroadbandContract(BroadbandContractBase, table=True):
    __tablename__ = 'broadband_contracts'
    id: Optional[int] = Field(default=None, primary_key=True)
    notified_dates: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BroadbandContractCreate(BroadbandContractBase):
    pass


class BroadbandContractUpdate(SQLModel):
    provider: Optional[str] = None
    circuit_id: Optional[str] = None
    bandwidth_mbps: Optional[int] = None
    location: Optional[str] = None
    renewal_cycle: Optional[str] = None
    renewal_cost: Optional[float] = None
    annual_cost: Optional[float] = None
    monthly_cost: Optional[float] = None
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None
    auto_renew: Optional[bool] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    reminder_days: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class BroadbandContractRead(BroadbandContractBase):
    id: int
    created_at: datetime
    updated_at: datetime
