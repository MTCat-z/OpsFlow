import time
import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

# 公共 iperf3 服务器列表源
_PUBLIC_SOURCE_URL = (
    "https://raw.githubusercontent.com/R0GGER/public-iperf3-servers/main/public-servers.json"
)
_CACHE_TTL = 24 * 60 * 60  # 24 小时内存缓存
_FETCH_TIMEOUT = 10.0

# 模块级内存缓存
_cache_data: Optional[List[Dict[str, Any]]] = None
_cache_time: float = 0.0

# 内置 fallback 列表（公共源不可达时使用，参考前端 IperfPage.vue 的 publicNodes）
_FALLBACK_SERVERS: List[Dict[str, Any]] = [
    {
        "host": "speedtest.hkg12.hk.leaseweb.net",
        "port": 5201,
        "location": "香港 LeaseWeb (10G)",
        "country": "Hong Kong",
        "city": "Hong Kong",
        "lat": 22.3193,
        "lng": 114.1694,
    },
    {
        "host": "84.17.57.129",
        "port": 5201,
        "location": "香港 DATAPACKET (2x10G)",
        "country": "Hong Kong",
        "city": "Hong Kong",
        "lat": 22.3193,
        "lng": 114.1694,
    },
    {
        "host": "23.249.60.154",
        "port": 30000,
        "location": "日本 FortiSASE (10G)",
        "country": "Japan",
        "city": "Tokyo",
        "lat": 35.6762,
        "lng": 139.6503,
    },
    {
        "host": "speedtest.sgp1.digitalocean.com",
        "port": 5201,
        "location": "新加坡 DigitalOcean",
        "country": "Singapore",
        "city": "Singapore",
        "lat": 1.3521,
        "lng": 103.8198,
    },
    {
        "host": "speedtest.tele2.net",
        "port": 5201,
        "location": "洛杉矶 Tele2",
        "country": "United States",
        "city": "Los Angeles",
        "lat": 34.0522,
        "lng": -118.2437,
    },
    {
        "host": "speedtest.nyc1.digitalocean.com",
        "port": 5201,
        "location": "纽约 DigitalOcean",
        "country": "United States",
        "city": "New York",
        "lat": 40.7128,
        "lng": -74.0060,
    },
    {
        "host": "speedtest.fra1.digitalocean.com",
        "port": 5201,
        "location": "法兰克福 DigitalOcean",
        "country": "Germany",
        "city": "Frankfurt",
        "lat": 50.1109,
        "lng": 8.6821,
    },
    {
        "host": "iperf.he.net",
        "port": 5201,
        "location": "Hurricane Electric (IPv6)",
        "country": "United States",
        "city": "Fremont",
        "lat": 37.5485,
        "lng": -121.9886,
    },
]


def _normalize_server(item: Any) -> Optional[Dict[str, Any]]:
    """将公共源的原始条目归一化为统一字段结构；无法解析 host 时返回 None。"""
    if not isinstance(item, dict):
        logger.debug("归一化跳过：条目非 dict 类型，type=%s", type(item).__name__)
        return None
    host = item.get("host") or item.get("hostname") or item.get("address")
    if not host:
        logger.debug("归一化跳过：条目缺少 host 字段，keys=%s", list(item.keys()))
        return None
    port = item.get("port") or 5201
    location = item.get("location") or item.get("label") or item.get("name") or ""
    country = item.get("country") or ""
    city = item.get("city") or ""
    lat = item.get("lat") if item.get("lat") is not None else item.get("latitude")
    lng = item.get("lng") if item.get("lng") is not None else item.get("longitude") or item.get("lon")
    try:
        port = int(port)
    except (TypeError, ValueError):
        logger.debug("归一化端口解析失败，回退默认 5201，原始值=%r，host=%s", port, host)
        port = 5201
    return {
        "host": host,
        "port": port,
        "location": location,
        "country": country,
        "city": city,
        "lat": lat,
        "lng": lng,
    }


def _fetch_public_servers() -> Optional[List[Dict[str, Any]]]:
    """从公共源拉取并归一化；失败返回 None。"""
    logger.info("开始从公共源拉取 iperf3 服务器列表: url=%s, timeout=%.1fs", _PUBLIC_SOURCE_URL, _FETCH_TIMEOUT)
    try:
        resp = httpx.get(_PUBLIC_SOURCE_URL, timeout=_FETCH_TIMEOUT)
        logger.info(
            "公共源响应: status_code=%s, content_length=%s, elapsed=%.3fs",
            resp.status_code,
            resp.headers.get("content-length", "unknown"),
            resp.elapsed.total_seconds() if resp.elapsed else 0.0,
        )
        resp.raise_for_status()
        payload = resp.json()
    except httpx.TimeoutException as e:
        logger.warning("拉取公共 iperf3 服务器列表超时: %s (timeout=%.1fs)", e, _FETCH_TIMEOUT)
        return None
    except httpx.HTTPStatusError as e:
        # e.request / e.response 均为 property，未设置时 raise RuntimeError
        try:
            status = e.response.status_code
        except (RuntimeError, AttributeError):
            status = "unknown"
        try:
            req_url = e.request.url
        except (RuntimeError, AttributeError):
            req_url = _PUBLIC_SOURCE_URL
        try:
            body = e.response.text[:200] if e.response and e.response.text else ""
        except (RuntimeError, AttributeError):
            body = ""
        logger.warning(
            "拉取公共 iperf3 服务器列表 HTTP 错误: status=%s, url=%s, body=%s",
            status,
            req_url,
            body,
        )
        return None
    except httpx.RequestError as e:
        # httpx 的 RequestError.request 是 property，未设置时会 raise RuntimeError
        # （不是 AttributeError），getattr 默认值兜不住，必须 try/except
        try:
            req_url = e.request.url
        except (RuntimeError, AttributeError):
            req_url = _PUBLIC_SOURCE_URL
        logger.warning(
            "拉取公共 iperf3 服务器列表网络错误: type=%s, url=%s, msg=%s",
            type(e).__name__,
            req_url,
            e,
        )
        return None
    except ValueError as e:
        logger.warning("公共源响应 JSON 解析失败: %s", e)
        return None
    except Exception as e:
        logger.warning("拉取公共 iperf3 服务器列表未知异常: type=%s, msg=%s", type(e).__name__, e, exc_info=True)
        return None

    # 兼容顶层数组或 {"servers": [...]} / {"data": [...]} 两种结构
    payload_type = type(payload).__name__
    if isinstance(payload, dict):
        raw_list = payload.get("servers") or payload.get("data") or []
        logger.info(
            "公共源 payload 为 dict (keys=%s)，提取字段后得到 %d 条原始记录",
            list(payload.keys()),
            len(raw_list),
        )
        if not raw_list:
            logger.warning("公共源 dict payload 中未找到 servers/data 字段或字段为空: keys=%s", list(payload.keys()))
    elif isinstance(payload, list):
        raw_list = payload
        logger.info("公共源 payload 为 list，直接使用，共 %d 条原始记录", len(raw_list))
    else:
        raw_list = []
        logger.warning("公共源 payload 类型不支持: type=%s，返回空列表", payload_type)

    servers: List[Dict[str, Any]] = []
    skipped = 0
    for item in raw_list:
        norm = _normalize_server(item)
        if norm is not None:
            servers.append(norm)
        else:
            skipped += 1
    logger.info(
        "公共源归一化完成: 成功 %d 条, 跳过 %d 条, 原始共 %d 条",
        len(servers),
        skipped,
        len(raw_list),
    )
    if not servers:
        logger.warning("公共源归一化后服务器列表为空（原始 %d 条全部被跳过）", len(raw_list))
        return None
    return servers


@router.get("/public-servers")
def list_public_servers():
    """返回公共 iperf3 服务器列表。

    - 首次调用从公共源拉取，24 小时内后续调用走内存缓存；
    - 缓存过期后重新拉取；
    - 公共源不可达时返回内置 fallback 列表（不报错）。
    - 返回 source 字段标识数据来源：cache | fresh | fallback
    """
    global _cache_data, _cache_time

    now = time.time()
    cache_age = now - _cache_time if _cache_data is not None else None
    # 缓存命中（未过期）
    if _cache_data is not None and (now - _cache_time) < _CACHE_TTL:
        logger.info(
            "缓存命中: %d 台服务器, 缓存年龄=%.1fs (TTL=%ds)",
            len(_cache_data),
            cache_age,
            _CACHE_TTL,
        )
        return {"servers": _cache_data, "source": "cache"}

    # 缓存为空或已过期
    if _cache_data is None:
        logger.info("缓存为空，首次拉取公共 iperf3 服务器列表")
    else:
        logger.info(
            "缓存已过期: 年龄=%.1fs, TTL=%ds, 缓存内服务器数=%d，重新拉取",
            cache_age,
            _CACHE_TTL,
            len(_cache_data),
        )

    # 尝试从公共源拉取
    fresh = _fetch_public_servers()
    if fresh:
        _cache_data = fresh
        _cache_time = now
        logger.info(
            "公共源拉取成功，已更新缓存: %d 台服务器, 下次过期时间 %.1f 秒后",
            len(fresh),
            _CACHE_TTL,
        )
        return {"servers": fresh, "source": "fresh"}

    # 公共源不可达
    logger.warning(
        "公共源拉取失败，返回内置 fallback 列表: %d 台服务器",
        len(_FALLBACK_SERVERS),
    )
    # 若存在旧缓存，记录额外上下文以便排查
    if _cache_data is not None:
        logger.warning(
            "注意：公共源失败但仍有旧缓存可用（年龄=%.1fs），但本次按规范返回 fallback；旧缓存未清空",
            cache_age,
        )
    return {"servers": _FALLBACK_SERVERS, "source": "fallback"}
