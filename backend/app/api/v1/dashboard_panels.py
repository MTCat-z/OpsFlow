"""仪表盘面板 API — Grafana 风格可配置面板

CRUD + 数据查询，按 org_id 隔离。
admin 可在查询参数里指定 org_id，普通用户自动绑定自身 org_id。
"""
import time
from datetime import datetime, timedelta
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.auth import get_current_user, get_current_org, check_org_access
from app.core.database import get_session
from app.models.dashboard_panel import (
    DashboardPanel, DashboardPanelCreate, DashboardPanelUpdate, DashboardPanelRead,
)
from app.models.user import User
from app.models.iperf_task import IperfTask
from app.models.scan_task import ScanTask
from app.models.organization import Organization

router = APIRouter()


# ────────────────────────────────────────────────────────────────────
# 面板 CRUD
# ────────────────────────────────────────────────────────────────────

def _resolve_org_id(user: User, org_id: Optional[int]) -> int:
    """解析面板归属的 org_id：admin 可显式指定，普通用户绑定自身 org_id"""
    if user.role == 'admin':
        if org_id is None:
            raise HTTPException(400, '管理员请指定目标组织 org_id')
        return org_id
    if org_id is not None and org_id != user.org_id:
        raise HTTPException(403, '无权操作其他组织的面板')
    return user.org_id


@router.get('', summary='列出组织面板配置')
def list_panels(
    org_id: Optional[int] = Query(None, description='管理员指定目标组织'),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """列出指定组织的所有面板配置（按 grid_position.y, x 排序）"""
    target_org = _resolve_org_id(user, org_id)
    rows = session.exec(
        select(DashboardPanel)
        .where(DashboardPanel.org_id == target_org)
        .order_by(DashboardPanel.id)
    ).all()
    return {'items': [DashboardPanelRead.model_validate(r).model_dump() for r in rows], 'total': len(rows)}


@router.post('', summary='新增面板', status_code=201)
def create_panel(
    data: DashboardPanelCreate,
    org_id: Optional[int] = Query(None, description='管理员指定目标组织'),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    target_org = _resolve_org_id(user, org_id)
    panel = DashboardPanel(
        org_id=target_org,
        title=data.title,
        source_type=data.source_type,
        source_config=data.source_config or {},
        chart_type=data.chart_type,
        grid_position=data.grid_position or {'x': 0, 'y': 0, 'w': 6, 'h': 4},
    )
    session.add(panel)
    session.commit()
    session.refresh(panel)
    return DashboardPanelRead.model_validate(panel).model_dump()


@router.put('/{panel_id}', summary='更新面板')
def update_panel(
    panel_id: int,
    data: DashboardPanelUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    panel = session.get(DashboardPanel, panel_id)
    if not panel:
        raise HTTPException(404, '面板不存在')
    if not check_org_access(panel, user):
        raise HTTPException(403, '无权操作其他组织的面板')
    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(panel, k, v)
    panel.updated_at = datetime.utcnow()
    session.add(panel)
    session.commit()
    session.refresh(panel)
    return DashboardPanelRead.model_validate(panel).model_dump()


@router.delete('/{panel_id}', summary='删除面板')
def delete_panel(
    panel_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    panel = session.get(DashboardPanel, panel_id)
    if not panel:
        raise HTTPException(404, '面板不存在')
    if not check_org_access(panel, user):
        raise HTTPException(403, '无权操作其他组织的面板')
    session.delete(panel)
    session.commit()
    return {'ok': True}


@router.put('/layout', summary='批量保存面板布局')
def save_layout(
    layout: List[Dict[str, Any]],
    org_id: Optional[int] = Query(None, description='管理员指定目标组织'),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """前端拖拽后批量更新面板的 grid_position。
    入参 layout: [{id, x, y, w, h}, ...]
    """
    target_org = _resolve_org_id(user, org_id)
    for item in layout:
        pid = item.get('id')
        if pid is None:
            continue
        panel = session.get(DashboardPanel, pid)
        if not panel or panel.org_id != target_org:
            continue
        panel.grid_position = {
            'x': int(item.get('x', 0)),
            'y': int(item.get('y', 0)),
            'w': int(item.get('w', panel.grid_position.get('w', 6))),
            'h': int(item.get('h', panel.grid_position.get('h', 4))),
        }
        panel.updated_at = datetime.utcnow()
        session.add(panel)
    session.commit()
    return {'ok': True, 'updated': len(layout)}


# ────────────────────────────────────────────────────────────────────
# 面板数据查询
# ────────────────────────────────────────────────────────────────────

@router.get('/{panel_id}/data', summary='查询单个面板数据')
def get_panel_data(
    panel_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """按面板 source_type 查数据，返回结构化结果供前端渲染"""
    panel = session.get(DashboardPanel, panel_id)
    if not panel:
        raise HTTPException(404, '面板不存在')
    if not check_org_access(panel, user):
        raise HTTPException(403, '无权访问其他组织的面板')

    st = panel.source_type
    cfg = panel.source_config or {}
    org_id = panel.org_id

    if st == 'zabbix_item':
        return _fetch_zabbix_item(org_id, cfg)
    if st == 'iperf_recent':
        return _fetch_iperf_recent(org_id, session)
    if st == 'scan_recent':
        return _fetch_scan_recent(org_id, session)
    if st == 'zabbix_problems':
        return _fetch_zabbix_problems(org_id)
    if st == 'probe_status':
        return _fetch_probe_status(org_id, session)
    raise HTTPException(400, f'未知数据源类型: {st}')


def _fetch_zabbix_item(org_id: int, cfg: Dict[str, Any]) -> dict:
    """Zabbix 监控项历史值 → 折线图数据"""
    from app.services.zabbix_service import ZabbixAPIError, get_zabbix_client_for_org
    host_id = cfg.get('host_id')
    item_key = cfg.get('item_key')
    period = cfg.get('period', '1h')
    if not host_id or not item_key:
        return {'series': [], 'error': '缺少 host_id 或 item_key'}
    try:
        client = get_zabbix_client_for_org(org_id)
        # 找到对应 item
        items = client.get_items(host_id)
        item = next((i for i in items if i.get('key_') == item_key), None)
        if not item:
            return {'series': [], 'error': f'未找到 item: {item_key}'}
        item_id = item['itemid']
        # 时间范围
        period_map = {'1h': 3600, '6h': 21600, '24h': 86400, '7d': 604800}
        seconds = period_map.get(period, 3600)
        now = int(time.time())
        history = client._rpc('history.get', {
            'itemids': [item_id],
            'time_from': now - seconds,
            'time_till': now,
            'sortfield': 'clock',
            'limit': 500,
        }) or []
        return {
            'series': [{'t': int(h['clock']), 'v': float(h['value'])} for h in history],
            'item_name': item.get('name', item_key),
            'period': period,
        }
    except ZabbixAPIError as e:
        return {'series': [], 'error': str(e)}
    except Exception as e:
        return {'series': [], 'error': f'Zabbix 查询失败: {e}'}


def _fetch_iperf_recent(org_id: int, session: Session) -> dict:
    """最近一条 iperf3 测速结果 → 数值卡"""
    row = session.exec(
        select(IperfTask)
        .where(IperfTask.org_id == org_id, IperfTask.status == 'completed')
        .order_by(IperfTask.finished_at.desc())
        .limit(1)
    ).first()
    if not row:
        return {'values': {}, 'empty': True}
    return {
        'values': {
            'bandwidth_mbps': row.bandwidth_mbps,
            'jitter_ms': row.jitter_ms,
            'lost_percent': row.lost_percent,
            'retransmits': row.retransmits,
        },
        'finished_at': row.finished_at.isoformat() if row.finished_at else None,
        'server_host': row.server_host,
        'protocol': row.protocol,
    }


def _fetch_scan_recent(org_id: int, session: Session) -> dict:
    """最近一条扫描任务结果 → 数值卡"""
    row = session.exec(
        select(ScanTask)
        .where(ScanTask.org_id == org_id, ScanTask.status == 'completed')
        .order_by(ScanTask.finished_at.desc())
        .limit(1)
    ).first()
    if not row:
        return {'values': {}, 'empty': True}
    return {
        'values': {
            'host_count': getattr(row, 'host_count', None),
            'port_count': getattr(row, 'port_count', None),
        },
        'finished_at': row.finished_at.isoformat() if row.finished_at else None,
        'target': getattr(row, 'target', ''),
    }


def _fetch_zabbix_problems(org_id: int) -> dict:
    """Zabbix 活跃告警 → 表格数据"""
    from app.services.zabbix_service import get_active_problems
    resp = get_active_problems(org_id=org_id)
    if resp.get('zabbix_status') != 'ok':
        return {'items': [], 'error': resp.get('error', 'Zabbix 不可用')}
    items = resp.get('data') or []
    return {'items': items[:50], 'total': len(items)}


def _fetch_probe_status(org_id: int, session: Session) -> dict:
    """探针状态 → 数值卡"""
    org = session.get(Organization, org_id)
    if not org:
        return {'values': {}, 'error': '组织不存在'}
    now = datetime.utcnow()
    online = bool(
        org.probe_last_heartbeat
        and (now - org.probe_last_heartbeat).total_seconds() <= 300
    )
    return {
        'values': {
            'online': 1 if online else 0,
            'configured': 1 if org.probe_key else 0,
        },
        'probe_last_heartbeat': org.probe_last_heartbeat.isoformat() if org.probe_last_heartbeat else None,
        'wg_tunnel_ip': org.wg_tunnel_ip,
    }


# ────────────────────────────────────────────────────────────────────
# 默认面板初始化
# ────────────────────────────────────────────────────────────────────

DEFAULT_PANELS = [
    {'title': '最近测速', 'source_type': 'iperf_recent', 'chart_type': 'stat', 'grid_position': {'x': 0, 'y': 0, 'w': 4, 'h': 4}},
    {'title': '最近扫描', 'source_type': 'scan_recent', 'chart_type': 'stat', 'grid_position': {'x': 4, 'y': 0, 'w': 4, 'h': 4}},
    {'title': '探针状态', 'source_type': 'probe_status', 'chart_type': 'stat', 'grid_position': {'x': 8, 'y': 0, 'w': 4, 'h': 4}},
    {'title': 'Zabbix 告警', 'source_type': 'zabbix_problems', 'chart_type': 'table', 'grid_position': {'x': 0, 'y': 4, 'w': 12, 'h': 6}},
]


@router.post('/defaults', summary='初始化默认面板')
def init_default_panels(
    org_id: Optional[int] = Query(None, description='管理员指定目标组织'),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """如果该组织还没有任何面板，创建一套默认面板配置"""
    target_org = _resolve_org_id(user, org_id)
    existing = session.exec(
        select(DashboardPanel).where(DashboardPanel.org_id == target_org)
    ).first()
    if existing:
        return {'created': 0, 'message': '组织已有面板配置，跳过初始化'}
    created = []
    for p in DEFAULT_PANELS:
        panel = DashboardPanel(
            org_id=target_org,
            title=p['title'],
            source_type=p['source_type'],
            source_config={},
            chart_type=p['chart_type'],
            grid_position=p['grid_position'],
        )
        session.add(panel)
        created.append(p['title'])
    session.commit()
    return {'created': len(created), 'panels': created}
