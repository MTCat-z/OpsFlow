"""
iperf_public API 本地集成测试脚本

演示 /api/v1/iperf/public-servers 三条返回路径与对应日志：
  1. fresh  — 公共源可达，首次拉取
  2. cache  — 缓存命中
  3. fallback — 公共源不可达（网络异常 / HTTP 500 / JSON 解析失败）

使用 FastAPI TestClient，不依赖数据库、不需要 .env、不需要启动服务。
日志会直接打印到 stdout，便于排查。

运行：
    cd d:\\OpsFlow\\backend
    python scripts\\test_iperf_public.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from unittest import mock

# 将 backend 目录加入 sys.path，保证可 import app.*
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from fastapi.testclient import TestClient


# ── 日志配置：把 app.api.v1.iperf_public 的日志打到 stdout，级别 DEBUG ──
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# 降低 httpx / httpcore 的噪声
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)


def _reset_module_cache():
    """重置 iperf_public 模块的内存缓存，便于多次场景独立测试"""
    from app.api.v1 import iperf_public
    iperf_public._cache_data = None
    iperf_public._cache_time = 0.0


def _mock_servers_payload():
    """构造一份假的公共源返回数据（模拟 raw.githubusercontent.com 的格式）"""
    return {
        "servers": [
            {
                "host": "test-hk.example.com",
                "port": 5201,
                "location": "香港测试节点 (10G)",
                "country": "Hong Kong",
                "city": "Hong Kong",
                "lat": 22.3193,
                "lng": 114.1694,
            },
            {
                "host": "test-tokyo.example.com",
                "port": 5201,
                "location": "东京测试节点",
                "country": "Japan",
                "city": "Tokyo",
                "lat": 35.6762,
                "lng": 139.6503,
            },
            {
                # 故意缺 host 字段，演示归一化跳过
                "port": 5201,
                "location": "无效节点",
            },
            {
                # 故意 port 非数字，演示端口回退
                "host": "test-sg.example.com",
                "port": "abc",
                "location": "新加坡测试节点",
                "country": "Singapore",
                "city": "Singapore",
            },
        ]
    }


def _section(title: str):
    print()
    print("=" * 78)
    print(f"  场景：{title}")
    print("=" * 78)


def _print_response_summary(resp):
    print("-" * 78)
    print(f"HTTP {resp.status_code}")
    body = resp.json()
    source = body.get("source")
    servers = body.get("servers", [])
    print(f"source = {source}")
    print(f"servers count = {len(servers)}")
    for i, s in enumerate(servers[:5], 1):
        print(f"  [{i}] {s.get('host')}:{s.get('port')}  {s.get('location')}")
    if len(servers) > 5:
        print(f"  ... 共 {len(servers)} 条，仅展示前 5 条")
    print("-" * 78)


def main():
    from app.api.v1 import iperf_public
    from fastapi import FastAPI

    # 只挂载 iperf_public 路由，避免触发其他模块依赖（sqlmodel 等）
    app = FastAPI()
    app.include_router(iperf_public.router, prefix="/api/v1/iperf")

    client = TestClient(app)
    url = "/api/v1/iperf/public-servers"

    # ─────────────────────────────────────────────────────────────────────
    # 场景 1：公共源可达，返回测试数据 → source=fresh
    # ─────────────────────────────────────────────────────────────────────
    _section("1. 公共源可达 — 首次拉取，期望 source=fresh")
    _reset_module_cache()
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-length": "512"}
    mock_resp.elapsed = mock.MagicMock()
    mock_resp.elapsed.total_seconds.return_value = 0.342
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = _mock_servers_payload()

    with mock.patch.object(iperf_public.httpx, "get", return_value=mock_resp) as m_get:
        resp = client.get(url)
        m_get.assert_called_once()
    _print_response_summary(resp)

    # ─────────────────────────────────────────────────────────────────────
    # 场景 2：第二次调用，缓存命中 → source=cache
    # ─────────────────────────────────────────────────────────────────────
    _section("2. 第二次调用 — 缓存命中，期望 source=cache（不应再调用 httpx.get）")
    with mock.patch.object(iperf_public.httpx, "get") as m_get:
        resp = client.get(url)
        m_get.assert_not_called()  # 不应再发请求
    _print_response_summary(resp)

    # ─────────────────────────────────────────────────────────────────────
    # 场景 3：缓存过期 + 公共源网络异常 → source=fallback
    # ─────────────────────────────────────────────────────────────────────
    _section("3. 缓存过期 + 公共源网络异常 — 期望 source=fallback")
    # 手动把缓存时间设到很久以前，模拟过期
    iperf_public._cache_time = time.time() - iperf_public._CACHE_TTL - 1
    import httpx as _httpx
    with mock.patch.object(
        iperf_public.httpx,
        "get",
        side_effect=_httpx.ConnectError("Failed to connect to raw.githubusercontent.com"),
    ) as m_get:
        resp = client.get(url)
        m_get.assert_called_once()
    _print_response_summary(resp)

    # ─────────────────────────────────────────────────────────────────────
    # 场景 4：公共源 HTTP 500 → source=fallback
    # ─────────────────────────────────────────────────────────────────────
    _section("4. 公共源 HTTP 500 — 期望 source=fallback")
    _reset_module_cache()
    bad_resp = mock.MagicMock()
    bad_resp.status_code = 503
    bad_resp.headers = {"content-length": "0"}
    bad_resp.elapsed = mock.MagicMock()
    bad_resp.elapsed.total_seconds.return_value = 0.1
    bad_resp.text = "<html>Service Unavailable</html>"
    import httpx as _httpx2
    bad_resp.raise_for_status.side_effect = _httpx2.HTTPStatusError(
        "Server Error", request=mock.MagicMock(url=iperf_public._PUBLIC_SOURCE_URL), response=bad_resp,
    )

    with mock.patch.object(iperf_public.httpx, "get", return_value=bad_resp):
        resp = client.get(url)
    _print_response_summary(resp)

    # ─────────────────────────────────────────────────────────────────────
    # 场景 5：公共源返回非 JSON → source=fallback
    # ─────────────────────────────────────────────────────────────────────
    _section("5. 公共源返回非 JSON — 期望 source=fallback")
    _reset_module_cache()
    non_json_resp = mock.MagicMock()
    non_json_resp.status_code = 200
    non_json_resp.headers = {"content-length": "100"}
    non_json_resp.elapsed = mock.MagicMock()
    non_json_resp.elapsed.total_seconds.return_value = 0.2
    non_json_resp.raise_for_status.return_value = None
    non_json_resp.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")

    with mock.patch.object(iperf_public.httpx, "get", return_value=non_json_resp):
        resp = client.get(url)
    _print_response_summary(resp)

    # ─────────────────────────────────────────────────────────────────────
    # 场景 6：真实网络调用（不 mock）— 看本机能否真正拉到公共源
    # ─────────────────────────────────────────────────────────────────────
    _section("6. 真实网络调用（不 mock）— 期望 fresh 或 fallback")
    _reset_module_cache()
    try:
        resp = client.get(url)
        _print_response_summary(resp)
    except Exception as e:
        print(f"TestClient 调用异常: {type(e).__name__}: {e}")

    print()
    print("=" * 78)
    print("  所有场景测试完成")
    print("=" * 78)


if __name__ == "__main__":
    main()
