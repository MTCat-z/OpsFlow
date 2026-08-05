from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.core.auth import get_current_user, get_current_org
from app.core.database import get_session
from app.models.user import User
from app.models.organization import Organization
from app.services import zabbix_service
from app.services.zabbix_cache import clear_cache
from app.services.zabbix_client import get_zabbix_client_for_org

router = APIRouter()

# 级联查询用独立 router，挂载到 /organizations 前缀下
org_zabbix_router = APIRouter(prefix='/organizations', tags=['组织 Zabbix 级联查询'])


def resolve_zabbix_org(
    org_id: Optional[int] = Query(None, description='目标组织ID（仅 admin 可指定，普通用户自动用自身 org_id）'),
    current_org: Optional[int] = Depends(get_current_org),
    session: Session = Depends(get_session),
) -> Optional[int]:
    """
    解析目标组织 ID 并校验 Zabbix 配置。
    - 普通用户：强制使用自身 org_id
    - admin：使用 query 传入的 org_id；未传则回退到单机版（返回 None）
    - 组织未配置 zabbix_url 时抛 400
    """
    if current_org is not None:
        # 普通用户，强制使用自身 org_id，忽略 query 参数
        effective = current_org
    else:
        # admin，使用 query 参数（可能为 None = 单机模式）
        effective = org_id

    if effective is not None:
        org = session.get(Organization, effective)
        if not org or not org.zabbix_url:
            raise HTTPException(status_code=400, detail='该组织未配置 Zabbix')
    return effective


@router.get('/status', summary='Zabbix 连接状态')
def status(org_id: Optional[int] = Depends(resolve_zabbix_org)):
    return zabbix_service.get_status(org_id=org_id)


@router.get('/hosts', summary='主机列表')
def hosts(org_id: Optional[int] = Depends(resolve_zabbix_org)):
    return zabbix_service.get_monitored_hosts(org_id=org_id)


@router.get('/hosts/{host_id}', summary='主机详情')
def host_detail(host_id: str, org_id: Optional[int] = Depends(resolve_zabbix_org)):
    return zabbix_service.get_host_detail(host_id, org_id=org_id)


@router.get('/hosts/{host_id}/metrics', summary='主机指标')
def host_metrics(
    host_id: str,
    period: str = Query('1h', description='时间段: 1h/6h/24h/7d'),
    org_id: Optional[int] = Depends(resolve_zabbix_org),
):
    return zabbix_service.get_host_metrics(host_id, period, org_id=org_id)


@router.get('/problems', summary='活跃问题')
def problems(org_id: Optional[int] = Depends(resolve_zabbix_org)):
    return zabbix_service.get_active_problems(org_id=org_id)


@router.get('/events', summary='近期事件')
def events(
    host_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    org_id: Optional[int] = Depends(resolve_zabbix_org),
):
    return zabbix_service.get_events(host_id=host_id, limit=limit, org_id=org_id)


@router.get('/triggers', summary='活跃触发器')
def triggers(
    host_id: Optional[str] = None,
    org_id: Optional[int] = Depends(resolve_zabbix_org),
):
    return zabbix_service.get_triggers(host_id=host_id, org_id=org_id)


@router.get('/dashboard', summary='仪表盘汇总')
def dashboard(org_id: Optional[int] = Depends(resolve_zabbix_org)):
    return zabbix_service.get_dashboard_summary(org_id=org_id)


@router.post('/cache/clear', summary='清除缓存')
def cache_clear():
    clear_cache()
    return {'cleared': True}


def _check_org_zabbix_access(org_id: int, user: User, session: Session) -> Organization:
    """校验用户对目标组织的访问权及 Zabbix 配置，返回 Organization"""
    if user.role != 'admin' and user.org_id != org_id:
        raise HTTPException(status_code=403, detail='无权访问该组织')
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail='组织不存在')
    if not org.zabbix_url:
        raise HTTPException(status_code=400, detail='该组织未配置 Zabbix')
    return org


@org_zabbix_router.get(
    '/{org_id}/zabbix/hosts',
    summary='组织 Zabbix 主机列表（级联查询）',
)
def org_zabbix_hosts(
    org_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """返回该组织 Zabbix 的主机列表，用于面板编辑器选主机"""
    _check_org_zabbix_access(org_id, user, session)
    client = get_zabbix_client_for_org(org_id)
    hosts = client.get_hosts()
    return {
        'items': [{
            'host_id': h.get('hostid'),
            'name': h.get('name', h.get('host', '')),
            'host': h.get('host', ''),
            'ip': next((i.get('ip', '') for i in h.get('interfaces', [])), ''),
        } for h in hosts],
        'total': len(hosts),
    }


@org_zabbix_router.get(
    '/{org_id}/zabbix/items',
    summary='组织 Zabbix 主机监控项列表（级联查询）',
)
def org_zabbix_items(
    org_id: int,
    host_id: str = Query(..., description='Zabbix 主机 ID'),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """返回指定主机的监控项列表，用于面板编辑器选 item"""
    _check_org_zabbix_access(org_id, user, session)
    client = get_zabbix_client_for_org(org_id)
    items = client.get_items(host_id)
    return {
        'items': [{
            'item_id': i.get('itemid'),
            'name': i.get('name', ''),
            'key_': i.get('key_', ''),
        } for i in items],
        'total': len(items),
    }
