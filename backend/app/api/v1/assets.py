from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, col
import io
from app.core.database import get_session
from app.core.security import encrypt, decrypt
from app.core.auth import get_current_org
from app.models.asset import Asset, AssetCreate, AssetRead, AssetUpdate, AssetCredentials

router = APIRouter()

_CRED_FIELDS = [
    ('username', 'username_encrypted'),
    ('password', 'password_encrypted'),
    ('enable_password', 'enable_password_encrypted'),
    ('ssh_private_key', 'ssh_private_key_encrypted'),
]

def _asset_to_read(asset: Asset) -> AssetRead:
    r = AssetRead.model_validate(asset)
    r.has_credentials = bool(asset.username_encrypted)
    r.has_ssh_key = bool(asset.ssh_private_key_encrypted)
    return r

@router.get('', response_model=dict, summary='分页查询资产列表')
def list_assets(page: int=Query(1,ge=1), size: int=Query(20,ge=1,le=100), keyword: Optional[str]=None, device_type: Optional[str]=None, status: Optional[str]=None, org_id: Optional[int]=Depends(get_current_org), session: Session=Depends(get_session)):
    q = select(Asset)
    if org_id is not None: q = q.where(Asset.org_id == org_id)
    if keyword: q = q.where(col(Asset.name).contains(keyword)|col(Asset.ip_address).contains(keyword)|col(Asset.location).contains(keyword))
    if device_type: q = q.where(Asset.device_type==device_type)
    if status: q = q.where(Asset.status==status)
    total = len(session.exec(q).all())
    assets = session.exec(q.offset((page-1)*size).limit(size)).all()
    return {'total': total, 'page': page, 'size': size, 'items': [_asset_to_read(a) for a in assets]}

@router.post('', response_model=AssetRead, status_code=201)
def create_asset(asset_in: AssetCreate, session: Session=Depends(get_session), org_id: Optional[int]=Depends(get_current_org)):
    asset = Asset.model_validate(asset_in)
    asset.org_id = org_id
    for pf, ef in _CRED_FIELDS:
        v = getattr(asset_in, pf, None)
        if v: setattr(asset, ef, encrypt(v))
    session.add(asset); session.commit(); session.refresh(asset)
    return _asset_to_read(asset)

@router.get('/{asset_id}', response_model=AssetRead)
def get_asset(asset_id: int, session: Session=Depends(get_session)):
    asset = session.get(Asset, asset_id)
    if not asset: raise HTTPException(404, '资产不存在')
    return _asset_to_read(asset)

@router.put('/{asset_id}', response_model=AssetRead)
def update_asset(asset_id: int, asset_in: AssetUpdate, session: Session=Depends(get_session)):
    asset = session.get(Asset, asset_id)
    if not asset: raise HTTPException(404, '资产不存在')
    data = asset_in.model_dump(exclude_unset=True)
    for pf, ef in _CRED_FIELDS:
        if pf in data:
            v = data.pop(pf); setattr(asset, ef, encrypt(v) if v else None)
    for k, v in data.items(): setattr(asset, k, v)
    asset.updated_at = datetime.utcnow()
    session.add(asset); session.commit(); session.refresh(asset)
    return _asset_to_read(asset)

@router.delete('/{asset_id}', status_code=204)
def delete_asset(asset_id: int, session: Session=Depends(get_session)):
    asset = session.get(Asset, asset_id)
    if not asset: raise HTTPException(404, '资产不存在')
    session.delete(asset); session.commit()

@router.get('/{asset_id}/credentials', response_model=AssetCredentials)
def get_credentials(asset_id: int, session: Session=Depends(get_session)):
    asset = session.get(Asset, asset_id)
    if not asset: raise HTTPException(404, '资产不存在')
    return AssetCredentials(
        username=decrypt(asset.username_encrypted) if asset.username_encrypted else None,
        password=decrypt(asset.password_encrypted) if asset.password_encrypted else None,
        enable_password=decrypt(asset.enable_password_encrypted) if asset.enable_password_encrypted else None,
        ssh_private_key=decrypt(asset.ssh_private_key_encrypted) if asset.ssh_private_key_encrypted else None,
        auth_type=asset.auth_type,
        ssh_port=asset.ssh_port,
        protocol=asset.protocol,
    )

@router.get('/export/excel')
def export_assets(session: Session=Depends(get_session)):
    import openpyxl; from openpyxl.styles import Font, PatternFill
    assets = session.exec(select(Asset)).all()
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = '资产台账'
    ws.append(['ID','设备名称','IP地址','设备类型','型号','位置','负责人','操作系统','协议','端口','认证方式','状态','备注','创建时间'])
    for a in assets: ws.append([a.id,a.name,a.ip_address,a.device_type or '',a.model or '',a.location or '',a.owner or '',a.os or '',a.protocol,a.ssh_port,a.auth_type,a.status,a.notes or '',a.created_at.strftime('%Y-%m-%d')])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': 'attachment; filename=assets.xlsx'})
