#!/bin/bash
set -e

echo "[Probe] OpsFlow 探针启动中..."

# 检查环境变量
if [ -z "$PROBE_KEY" ] || [ -z "$ORG_CODE" ]; then
    echo "[ERROR] 缺少 PROBE_KEY 或 ORG_CODE，请检查 .env"
    exit 1
fi

# 如果有 WireGuard 配置，启动 VPN
if [ -f /etc/wireguard/wg0.conf ]; then
    echo "[VPN] 启动 WireGuard..."
    wg-quick up /etc/wireguard/wg0.conf 2>/dev/null || {
        echo "[VPN] wg-quick 失败，尝试 wireguard-go..."
        wireguard-go wg0 2>/dev/null && wg setconf wg0 /etc/wireguard/wg0.conf
    }

    # 等待 VPN 连通
    echo "[VPN] 等待隧道连通..."
    for i in $(seq 1 10); do
        if ping -c 1 -W 2 10.99.0.1 >/dev/null 2>&1; then
            echo "[VPN] WireGuard 已连接"
            break
        fi
        sleep 2
    done

    if ! ping -c 1 -W 2 10.99.0.1 >/dev/null 2>&1; then
        echo "[WARN] VPN 隧道未连通，尝试直连中心..."
    fi
fi

# 安装 python-nmap（如果没有）
pip install python-nmap httpx 2>/dev/null

# 启动探针 Agent
echo "[Probe] 启动 Agent..."
exec python /app/agent.py
