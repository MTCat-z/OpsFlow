from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, col, func, select

from app.core.database import get_session
from app.core.auth import get_current_org, get_current_user, check_org_access, require_org_admin
from app.models.user import User
from app.models.ipam import IpamAddress, IpamAddressCreate, IpamAddressRead, IpamAddressUpdate, IpamSubnet, IpamSubnetCreate, IpamSubnetRead, IpamSubnetUpdate

router = APIRouter()


@router.get("/dashboard")
def ipam_dashboard(session: Session = Depends(get_session)):
    subnet_count = session.exec(select(func.count(IpamSubnet.id))).one()
    dhcp_count = session.exec(select(func.count(IpamSubnet.id)).where(IpamSubnet.dhcp_enabled == True)).one()
    addr_count = session.exec(select(func.count(IpamAddress.id))).one()
    used_count = session.exec(select(func.count(IpamAddress.id)).where(IpamAddress.status == "used")).one()
    conflict_count = session.exec(select(func.count(IpamAddress.id)).where(IpamAddress.status == "conflict")).one()
    return {
        "subnets": subnet_count,
        "dhcp_subnets": dhcp_count,
        "addresses": addr_count,
        "used_addresses": used_count,
        "conflicts": conflict_count,
    }


@router.get("/subnets", response_model=dict)
def list_subnets(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    org_id: Optional[int] = Depends(get_current_org),
    session: Session = Depends(get_session),
):
    q = select(IpamSubnet)
    if org_id is not None:
        q = q.where(IpamSubnet.org_id == org_id)
    if keyword:
        q = q.where(col(IpamSubnet.name).contains(keyword) | col(IpamSubnet.cidr).contains(keyword))
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.offset((page - 1) * size).limit(size)).all()
    return {"total": total, "page": page, "size": size, "items": items}


@router.post("/subnets", response_model=IpamSubnetRead, status_code=201)
def create_subnet(data: IpamSubnetCreate, session: Session = Depends(get_session), org_id: Optional[int] = Depends(get_current_org)):
    subnet = IpamSubnet.model_validate(data)
    subnet.org_id = org_id
    session.add(subnet)
    session.commit()
    session.refresh(subnet)
    return subnet


@router.put("/subnets/{subnet_id}", response_model=IpamSubnetRead)
def update_subnet(subnet_id: int, data: IpamSubnetUpdate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    subnet = session.get(IpamSubnet, subnet_id)
    if not subnet or not check_org_access(subnet, current_user):
        raise HTTPException(404, "IPAM subnet not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(subnet, key, value)
    subnet.updated_at = datetime.utcnow()
    session.add(subnet)
    session.commit()
    session.refresh(subnet)
    return subnet


@router.delete("/subnets/{subnet_id}", status_code=204)
def delete_subnet(subnet_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    subnet = session.get(IpamSubnet, subnet_id)
    if not subnet or not check_org_access(subnet, current_user):
        raise HTTPException(404, "IPAM subnet not found")
    # 同时删除该子网下的地址
    addrs = session.exec(select(IpamAddress).where(IpamAddress.subnet_id == subnet_id)).all()
    for addr in addrs:
        session.delete(addr)
    session.delete(subnet)
    session.commit()


@router.post("/subnets/{subnet_id}/discover", status_code=201)
def discover_subnet(subnet_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user), admin: User = Depends(require_org_admin)):
    """手动触发子网 IP 发现"""
    subnet = session.get(IpamSubnet, subnet_id)
    if not subnet or not check_org_access(subnet, current_user):
        raise HTTPException(404, "IPAM subnet not found")

    def _send_task():
        try:
            from app.tasks.worker import celery_app
            celery_app.send_task('app.tasks.ipam_tasks.discover_ipam_subnet', args=[subnet.id], countdown=2)
        except Exception:
            pass

    import threading
    threading.Thread(target=_send_task, daemon=True).start()
    return {"subnet_id": subnet.id, "status": "discovery_queued"}


@router.get("/conflicts")
def list_conflicts(session: Session = Depends(get_session)):
    """获取所有冲突地址"""
    conflicts = session.exec(
        select(IpamAddress).where(IpamAddress.status == "conflict").order_by(IpamAddress.ip_address)
    ).all()
    return {"items": conflicts, "total": len(conflicts)}


@router.get("/addresses", response_model=dict)
def list_addresses(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    subnet_id: Optional[int] = None,
    status: Optional[str] = None,
    org_id: Optional[int] = Depends(get_current_org),
    session: Session = Depends(get_session),
):
    q = select(IpamAddress)
    if org_id is not None:
        q = q.where(IpamAddress.org_id == org_id)
    if keyword:
        q = q.where(
            col(IpamAddress.ip_address).contains(keyword)
            | col(IpamAddress.hostname).contains(keyword)
            | col(IpamAddress.mac_address).contains(keyword)
        )
    if subnet_id:
        q = q.where(IpamAddress.subnet_id == subnet_id)
    if status:
        q = q.where(IpamAddress.status == status)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(IpamAddress.ip_address).offset((page - 1) * size).limit(size)).all()
    return {"total": total, "page": page, "size": size, "items": items}


@router.post("/addresses", response_model=IpamAddressRead, status_code=201)
def create_address(data: IpamAddressCreate, session: Session = Depends(get_session), org_id: Optional[int] = Depends(get_current_org)):
    # IP 冲突检测
    existing = session.exec(
        select(IpamAddress).where(
            IpamAddress.ip_address == data.ip_address,
            IpamAddress.subnet_id == data.subnet_id,
        )
    ).first()
    if existing:
        raise HTTPException(400, f"IP {data.ip_address} 在该子网中已存在")

    address = IpamAddress.model_validate(data)
    address.org_id = org_id
    session.add(address)
    session.commit()
    session.refresh(address)
    return address


@router.put("/addresses/{address_id}", response_model=IpamAddressRead)
def update_address(address_id: int, data: IpamAddressUpdate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    address = session.get(IpamAddress, address_id)
    if not address or not check_org_access(address, current_user):
        raise HTTPException(404, "IPAM address not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(address, key, value)
    address.updated_at = datetime.utcnow()
    session.add(address)
    session.commit()
    session.refresh(address)
    return address


@router.delete("/addresses/{address_id}", status_code=204)
def delete_address(address_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    address = session.get(IpamAddress, address_id)
    if not address or not check_org_access(address, current_user):
        raise HTTPException(404, "IPAM address not found")
    session.delete(address)
    session.commit()
