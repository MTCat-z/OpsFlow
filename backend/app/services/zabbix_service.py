"""
Zabbix 服务编排层 — 封装客户端调用，添加缓存和降级
"""
import logging
from typing import Optional
from app.services.zabbix_client import (
    get_zabbix_client,
    get_zabbix_client_for_org,
    ZabbixAPIError,
)
from app.services.zabbix_cache import get_cached, set_cached, get_stale

logger = logging.getLogger(__name__)


def _client_for(org_id: Optional[int]):
    """根据 org_id 选择客户端：有 org_id 走多组织工厂，否则走单机版"""
    if org_id is not None:
        return get_zabbix_client_for_org(org_id)
    return get_zabbix_client()


def _safe_call(method_name: str, func, params: dict = None, org_id: Optional[int] = None):
    """带缓存和降级的调用封装。缓存 key 带 org_id 前缀避免不同组织串缓存。"""
    cache_method = f'org{org_id}:{method_name}' if org_id is not None else method_name
    # 尝试缓存
    cached = get_cached(cache_method, params)
    if cached is not None:
        return {'zabbix_status': 'ok', 'data': cached}

    try:
        result = func()
        set_cached(cache_method, params, result)
        return {'zabbix_status': 'ok', 'data': result}
    except (ZabbixAPIError, Exception) as e:
        logger.warning('Zabbix 调用失败 [%s]: %s', cache_method, e)
        # 尝试 stale 缓存
        stale = get_stale(cache_method, params)
        if stale is not None:
            return {'zabbix_status': 'cached', 'data': stale}
        return {'zabbix_status': 'unavailable', 'data': None, 'error': str(e)}


def get_status(org_id: Optional[int] = None) -> dict:
    client = _client_for(org_id)
    return client.test_connection()


def get_monitored_hosts(org_id: Optional[int] = None) -> dict:
    client = _client_for(org_id)
    def fetch():
        hosts = client.get_hosts()
        return [{
            'host_id': h.get('hostid'),
            'name': h.get('name', h.get('host', '')),
            'host': h.get('host', ''),
            'status': 'active' if h.get('status') == '0' else 'inactive',
            'available': h.get('available', 0),
            'ip': next((i.get('ip', '') for i in h.get('interfaces', [])), ''),
            'groups': [g.get('name', '') for g in h.get('groups', [])],
        } for h in hosts]
    return _safe_call('hosts', fetch, org_id=org_id)


def get_host_detail(host_id: str, org_id: Optional[int] = None) -> dict:
    client = _client_for(org_id)
    def fetch():
        hosts = client.get_hosts()
        host = next((h for h in hosts if h.get('hostid') == host_id), None)
        if not host:
            return {}
        return {
            'host_id': host.get('hostid'),
            'name': host.get('name', host.get('host', '')),
            'host': host.get('host', ''),
            'status': 'active' if host.get('status') == '0' else 'inactive',
            'available': host.get('available', 0),
            'ip': next((i.get('ip', '') for i in host.get('interfaces', [])), ''),
            'groups': [g.get('name', '') for g in host.get('groups', [])],
        }
    return _safe_call(f'host:{host_id}', fetch, {'host_id': host_id}, org_id=org_id)


def get_host_metrics(host_id: str, period: str = '1h', org_id: Optional[int] = None) -> dict:
    client = _client_for(org_id)
    def fetch():
        return client.get_host_metrics(host_id, period)
    return _safe_call(f'metrics:{host_id}:{period}', fetch, {'host_id': host_id, 'period': period}, org_id=org_id)


def get_active_problems(org_id: Optional[int] = None) -> dict:
    client = _client_for(org_id)
    def fetch():
        problems = client.get_problems()
        return [{
            'event_id': p.get('eventid'),
            'name': p.get('name', ''),
            'severity': int(p.get('severity', 0)),
            'clock': p.get('clock', ''),
            'acknowledged': p.get('acknowledged', '0') == '1',
        } for p in problems]
    return _safe_call('problems', fetch, org_id=org_id)


def get_events(host_id: str = None, limit: int = 50, org_id: Optional[int] = None) -> dict:
    client = _client_for(org_id)
    def fetch():
        events = client.get_events(host_id=host_id, limit=limit)
        return [{
            'event_id': e.get('eventid'),
            'name': e.get('name', ''),
            'severity': int(e.get('severity', 0)),
            'clock': e.get('clock', ''),
            'hosts': [h.get('name', '') for h in e.get('hosts', [])],
        } for e in events]
    return _safe_call('events', fetch, {'host_id': host_id, 'limit': limit}, org_id=org_id)


def get_triggers(host_id: str = None, org_id: Optional[int] = None) -> dict:
    client = _client_for(org_id)
    def fetch():
        triggers = client.get_triggers(host_id=host_id)
        return [{
            'trigger_id': t.get('triggerid'),
            'description': t.get('description', ''),
            'priority': int(t.get('priority', 0)),
            'lastchange': t.get('lastchange', ''),
            'hosts': [h.get('name', '') for h in t.get('hosts', [])],
        } for t in triggers]
    return _safe_call('triggers', fetch, {'host_id': host_id}, org_id=org_id)


def get_dashboard_summary(org_id: Optional[int] = None) -> dict:
    hosts_resp = get_monitored_hosts(org_id=org_id)
    problems_resp = get_active_problems(org_id=org_id)

    hosts_data = hosts_resp.get('data') or []
    problems_data = problems_resp.get('data') or []

    severity_map = {0: 'info', 1: 'info', 2: 'warning', 3: 'warning', 4: 'high', 5: 'critical'}
    by_severity = {'critical': 0, 'high': 0, 'warning': 0, 'info': 0}
    for p in problems_data:
        s = severity_map.get(p.get('severity', 0), 'info')
        by_severity[s] += 1

    problem_hosts = set(p.get('name', '')[:20] for p in problems_data)

    worst_status = 'ok'
    if hosts_resp['zabbix_status'] != 'ok' or problems_resp['zabbix_status'] != 'ok':
        worst_status = hosts_resp['zabbix_status'] if hosts_resp['zabbix_status'] != 'ok' else problems_resp['zabbix_status']

    return {
        'zabbix_status': worst_status,
        'data': {
            'total_hosts': len(hosts_data),
            'active_hosts': len([h for h in hosts_data if h.get('status') == 'active']),
            'total_problems': len(problems_data),
            'problems_by_severity': by_severity,
            'problem_host_count': len(problem_hosts),
        },
    }
