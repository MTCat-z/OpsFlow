"""
Zabbix JSON-RPC 2.0 API 客户端
"""
import logging
from typing import Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class ZabbixAPIError(Exception):
    def __init__(self, code: int, message: str, data: str = ''):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f'Zabbix API Error [{code}]: {message} - {data}')


class ZabbixClient:
    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        # 优先使用传入参数，未传则回退到全局 settings（保持单机版向后兼容）
        self.url = url if url is not None else settings.ZABBIX_URL
        self.api_token = token if token is not None else settings.ZABBIX_API_TOKEN
        self.user = user if user is not None else settings.ZABBIX_USER
        self.password = password if password is not None else settings.ZABBIX_PASSWORD
        self.verify_ssl = settings.ZABBIX_VERIFY_SSL
        self.timeout = settings.ZABBIX_TIMEOUT
        self._auth_token: Optional[str] = None
        self._request_id = 0

    def _is_configured(self) -> bool:
        return bool(self.url)

    def _get_client(self) -> httpx.Client:
        return httpx.Client(verify=self.verify_ssl, timeout=self.timeout)

    def _rpc(self, method: str, params: dict = None, no_auth: bool = False) -> dict:
        if not self._is_configured():
            raise ZabbixAPIError(-1, 'Zabbix 未配置', '请设置 ZABBIX_URL')

        self._request_id += 1
        payload = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params or {},
            'id': self._request_id,
        }

        headers = {'Content-Type': 'application/json-rpc'}

        # 认证方式 (no_auth 模式跳过认证头)
        if not no_auth:
            if self.api_token:
                headers['Authorization'] = f'Bearer {self.api_token}'
            elif self._auth_token:
                payload['auth'] = self._auth_token

        with self._get_client() as client:
            resp = client.post(self.url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        if 'error' in data:
            err = data['error']
            raise ZabbixAPIError(err.get('code', -1), err.get('message', ''), err.get('data', ''))

        return data.get('result')

    def _ensure_auth(self):
        """确保已认证（user.login 模式）"""
        if self.api_token or self._auth_token:
            return
        if self.user and self.password:
            self._auth_token = self._rpc('user.login', {
                'username': self.user,
                'password': self.password,
            })

    def test_connection(self) -> dict:
        if not self._is_configured():
            return {'available': False, 'error': 'Zabbix 未配置'}
        try:
            # Zabbix 7.x: apiinfo.version 不允许携带认证头
            version = self._rpc('apiinfo.version', no_auth=True)
            return {'available': True, 'version': version}
        except Exception as e:
            return {'available': False, 'error': str(e)}

    def get_hosts(self) -> list:
        self._ensure_auth()
        return self._rpc('host.get', {
            'output': ['hostid', 'host', 'name', 'status', 'available'],
            'selectInterfaces': ['ip'],
            'selectGroups': ['groupid', 'name'],
            'selectTags': ['tag', 'value'],
            'sortfield': 'name',
        }) or []

    def get_problems(self, recent: bool = False) -> list:
        self._ensure_auth()
        return self._rpc('problem.get', {
            'output': ['eventid', 'objectid', 'name', 'severity', 'clock', 'acknowledged'],
            'selectTags': 'extend',
            'recent': recent,
            'sortfield': ['eventid'],
            'sortorder': 'DESC',
            'limit': 100,
        }) or []

    def get_triggers(self, host_id: str = None) -> list:
        self._ensure_auth()
        params = {
            'output': ['triggerid', 'description', 'priority', 'lastchange', 'status', 'value'],
            'selectHosts': ['host', 'name'],
            'expandDescription': True,
            'filter': {'value': 1},
            'sortfield': 'priority',
            'sortorder': 'DESC',
        }
        if host_id:
            params['hostids'] = [host_id]
        return self._rpc('trigger.get', params) or []

    def get_events(self, host_id: str = None, limit: int = 50) -> list:
        self._ensure_auth()
        params = {
            'output': ['eventid', 'name', 'severity', 'clock', 'r_clock', 'acknowledged', 'value'],
            'selectHosts': ['host', 'name'],
            'sortfield': ['eventid'],
            'sortorder': 'DESC',
            'limit': limit,
        }
        if host_id:
            params['hostids'] = [host_id]
        return self._rpc('event.get', params) or []

    def get_host_metrics(self, host_id: str, period: str = '1h') -> dict:
        self._ensure_auth()
        import time
        now = int(time.time())
        period_map = {'1h': 3600, '6h': 21600, '24h': 86400, '7d': 604800}
        seconds = period_map.get(period, 3600)
        time_from = now - seconds

        metrics = {'cpu': [], 'memory': [], 'disk': {}, 'network': {'in': [], 'out': []}}

        # 获取 CPU 使用率
        items = self._rpc('item.get', {
            'hostids': [host_id],
            'search': {'key_': 'system.cpu.util'},
            'output': ['itemid', 'name'],
            'limit': 1,
        })
        if items:
            history = self._rpc('history.get', {
                'itemids': [items[0]['itemid']],
                'time_from': time_from,
                'time_till': now,
                'sortfield': 'clock',
                'limit': 500,
            })
            metrics['cpu'] = [{'t': h['clock'], 'v': round(float(h['value']), 2)} for h in (history or [])]

        # 获取内存
        mem_items = self._rpc('item.get', {
            'hostids': [host_id],
            'search': {'key_': 'vm.memory.size'},
            'output': ['itemid', 'key_'],
        })
        if mem_items:
            total_item = next((i for i in mem_items if 'total' in i['key_']), None)
            avail_item = next((i for i in mem_items if 'available' in i['key_'] or 'free' in i['key_']), None)
            if total_item and avail_item:
                for key, item in [('total', total_item), ('available', avail_item)]:
                    history = self._rpc('history.get', {
                        'itemids': [item['itemid']],
                        'time_from': time_from,
                        'time_till': now,
                        'sortfield': 'clock',
                        'limit': 500,
                    })
                    metrics['memory'].extend([{'t': h['clock'], 'v': round(float(h['value']) / 1073741824, 2)} for h in (history or [])])

        return metrics

    def get_items(self, host_id: str) -> list:
        """获取指定主机的监控项列表（用于面板编辑器级联选择 item）"""
        self._ensure_auth()
        return self._rpc('item.get', {
            'hostids': [host_id],
            'output': ['itemid', 'name', 'key_'],
            'sortfield': 'name',
        }) or []


_client: Optional[ZabbixClient] = None

def get_zabbix_client() -> ZabbixClient:
    """向后兼容：从全局 settings 读取配置创建单例客户端（单机版）"""
    global _client
    if _client is None:
        _client = ZabbixClient()
    return _client


# 多组织客户端实例缓存：{org_id: ZabbixClient}
_org_clients: dict = {}


def get_zabbix_client_for_org(org_id: Optional[int]) -> ZabbixClient:
    """
    多组织工厂函数：根据 org_id 从 Organization 表读取 zabbix 配置创建客户端。
    - org_id 为 None 时回退到单机版 get_zabbix_client()
    - 组织未配置 zabbix_url 时抛出 ZabbixAPIError，由调用方处理为 400
    """
    if not org_id:
        return get_zabbix_client()

    cached = _org_clients.get(org_id)
    if cached is not None:
        return cached

    from sqlmodel import Session
    from app.core.database import engine
    from app.models.organization import Organization

    with Session(engine) as session:
        org = session.get(Organization, org_id)
        if not org:
            raise ZabbixAPIError(-1, '组织不存在', f'org_id={org_id}')
        if not org.zabbix_url:
            raise ZabbixAPIError(-1, '该组织未配置 Zabbix', f'org_id={org_id}')
        client = ZabbixClient(
            url=org.zabbix_url,
            token=org.zabbix_api_token,
            user=getattr(org, 'zabbix_user', None),
            password=getattr(org, 'zabbix_password', None),
        )
    _org_clients[org_id] = client
    return client
