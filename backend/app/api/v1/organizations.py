"""
组织管理 API - 多租户场地隔离
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.auth import get_current_user, require_admin, audit
from app.models.user import User
from app.models.organization import (
    Organization, OrganizationCreate, OrganizationUpdate, OrganizationRead,
)

router = APIRouter(prefix='/organizations', tags=['组织管理'])


@router.get('', summary='组织列表')
def list_organizations(
    keyword: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    q = select(Organization)
    if keyword:
        q = q.where(Organization.name.contains(keyword) | Organization.code.contains(keyword))
    orgs = session.exec(q.order_by(Organization.id)).all()
    # 附带用户数和资产数
    from app.models.asset import Asset
    result = []
    for org in orgs:
        user_count = len(session.exec(select(User).where(User.org_id == org.id)).all())
        asset_count = len(session.exec(select(Asset).where(Asset.org_id == org.id)).all())
        result.append({
            **OrganizationRead.model_validate(org).model_dump(),
            'user_count': user_count,
            'asset_count': asset_count,
        })
    return {'items': result, 'total': len(result)}


@router.post('', summary='创建组织')
def create_organization(
    data: OrganizationCreate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    existing = session.exec(select(Organization).where(Organization.code == data.code)).first()
    if existing:
        raise HTTPException(400, f'组织编码 {data.code} 已存在')
    org = Organization(**data.model_dump())
    session.add(org)
    session.commit()
    session.refresh(org)
    audit(request, 'create', 'organization', org.id, f'创建组织: {org.name}', session)
    return OrganizationRead.model_validate(org).model_dump()


@router.put('/{org_id}', summary='更新组织')
def update_organization(
    org_id: int,
    data: OrganizationUpdate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, '组织不存在')
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(org, k, v)
    org.updated_at = datetime.utcnow()
    session.add(org)
    session.commit()
    session.refresh(org)
    audit(request, 'update', 'organization', org.id, f'更新组织: {org.name}', session)
    return OrganizationRead.model_validate(org).model_dump()


@router.delete('/{org_id}', summary='删除组织')
def delete_organization(
    org_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, '组织不存在')
    # 检查是否有关联用户
    users = session.exec(select(User).where(User.org_id == org_id)).all()
    if users:
        raise HTTPException(400, f'组织下还有 {len(users)} 个用户，请先转移或删除用户')
    audit(request, 'delete', 'organization', org.id, f'删除组织: {org.name}', session)
    session.delete(org)
    session.commit()
    return {'success': True}


@router.get('/all', summary='获取所有可用组织（下拉选择用）')
def list_all_organizations(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """获取所有活跃组织列表，用于创建用户/资产时选择"""
    orgs = session.exec(select(Organization).where(Organization.is_active == True).order_by(Organization.name)).all()
    return [{'id': o.id, 'name': o.name, 'code': o.code} for o in orgs]
