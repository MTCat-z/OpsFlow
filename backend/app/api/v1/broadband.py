from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, col
from app.core.database import get_session
from app.models.broadband import (
    BroadbandContract, BroadbandContractCreate,
    BroadbandContractUpdate, BroadbandContractRead,
    RENEWAL_CYCLE_MONTHS, calc_annual_cost,
)
from app.services.dingtalk import send_renewal_reminder, send_test_message

router = APIRouter()


@router.get('/dashboard', summary='宽带合同仪表盘')
def broadband_dashboard(session: Session = Depends(get_session)):
    today = date.today()
    all_contracts = session.exec(select(BroadbandContract)).all()
    active = [c for c in all_contracts if c.status == 'active']
    expired = [c for c in all_contracts if c.status == 'expired']
    expiring_30 = [c for c in active if (c.contract_end - today).days <= 30 and (c.contract_end - today).days >= 0]
    expiring_7 = [c for c in active if (c.contract_end - today).days <= 7 and (c.contract_end - today).days >= 0]
    total_annual = sum(c.annual_cost or 0 for c in active)
    return {
        'total': len(all_contracts),
        'active': len(active),
        'expired': len(expired),
        'expiring_30d': len(expiring_30),
        'expiring_7d': len(expiring_7),
        'total_annual_cost': round(total_annual, 2),
    }


@router.get('', response_model=dict, summary='分页查询宽带合同')
def list_contracts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    session: Session = Depends(get_session),
):
    q = select(BroadbandContract)
    if keyword:
        q = q.where(
            col(BroadbandContract.provider).contains(keyword)
            | col(BroadbandContract.circuit_id).contains(keyword)
            | col(BroadbandContract.location).contains(keyword)
            | col(BroadbandContract.contact_name).contains(keyword)
        )
    if status:
        q = q.where(BroadbandContract.status == status)
    total = len(session.exec(q).all())
    items = session.exec(q.offset((page - 1) * size).limit(size)).all()
    return {'total': total, 'page': page, 'size': size, 'items': items}


@router.post('', response_model=BroadbandContractRead, status_code=201)
def create_contract(data: BroadbandContractCreate, session: Session = Depends(get_session)):
    # 如果 renewal_cost 有值但 annual_cost 没填，自动计算年费
    if data.renewal_cost is not None and data.annual_cost is None:
        data.annual_cost = calc_annual_cost(data.renewal_cost, data.renewal_cycle or 'annual')
    contract = BroadbandContract.model_validate(data)
    session.add(contract)
    session.commit()
    session.refresh(contract)
    return contract


@router.get('/{contract_id}', response_model=BroadbandContractRead)
def get_contract(contract_id: int, session: Session = Depends(get_session)):
    contract = session.get(BroadbandContract, contract_id)
    if not contract:
        raise HTTPException(404, '合同不存在')
    return contract


@router.put('/{contract_id}', response_model=BroadbandContractRead)
def update_contract(contract_id: int, data: BroadbandContractUpdate, session: Session = Depends(get_session)):
    contract = session.get(BroadbandContract, contract_id)
    if not contract:
        raise HTTPException(404, '合同不存在')
    update_data = data.model_dump(exclude_unset=True)
    
    # 如果更新了 renewal_cost 或 renewal_cycle 但没更新 annual_cost，自动计算
    cost_changed = 'renewal_cost' in update_data or 'renewal_cycle' in update_data
    if cost_changed and 'annual_cost' not in update_data:
        new_cost = update_data.get('renewal_cost', contract.renewal_cost)
        new_cycle = update_data.get('renewal_cycle', contract.renewal_cycle)
        if new_cost is not None:
            update_data['annual_cost'] = calc_annual_cost(new_cost, new_cycle)
    
    for k, v in update_data.items():
        setattr(contract, k, v)
    contract.updated_at = datetime.utcnow()
    session.add(contract)
    session.commit()
    session.refresh(contract)
    return contract


@router.delete('/{contract_id}', status_code=204)
def delete_contract(contract_id: int, session: Session = Depends(get_session)):
    contract = session.get(BroadbandContract, contract_id)
    if not contract:
        raise HTTPException(404, '合同不存在')
    session.delete(contract)
    session.commit()


@router.post('/{contract_id}/test-notify', summary='发送测试钉钉通知')
def test_notify(contract_id: int, session: Session = Depends(get_session)):
    contract = session.get(BroadbandContract, contract_id)
    if not contract:
        raise HTTPException(404, '合同不存在')
    today = date.today()
    days_remaining = (contract.contract_end - today).days
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
        return {'success': True, 'message': '通知已发送'}
    else:
        raise HTTPException(500, '通知发送失败，请检查钉钉 Webhook 配置')
