#!/bin/bash
set -e

echo "[Probe] OpsFlow 探针启动中..."

# 检查环境变量
if [ -z "$PROBE_KEY" ] || [ -z "$ORG_CODE" ]; then
    echo "[ERROR] 缺少 PROBE_KEY 或 ORG_CODE，请检查 .env"
    exit 1
fi

# 检测隧道是否已连通（宿主机已运行 WireGuard 的情况，容器用 host 网络共享）
if ping -c 1 -W 2 10.99.0.1 >/dev/null 2>&1; then
    echo "[VPN] 隧道已连通（宿主机 WireGuard），跳过容器内 VPN 启动"
else
    echo "[VPN] 隧道未连通，尝试在容器内启动 WireGuard..."
    if [ -f /etc/wireguard/wg0.conf ]; then
        wg-quick up /etc/wireguard/wg0.conf 2>/dev/null || {
            echo "[VPN] wg-quick 失败，尝试 wireguard-go..."
            wireguard-go wg0 2>/dev/null && wg setconf wg0 /etc/wireguard/wg0.conf
        }
        echo "[VPN] 等待隧道连通..."
        for i in $(seq 1 10); do
            if ping -c 1 -W 2 10.99.0.1 >/dev/null 2>&1; then
                echo "[VPN] WireGuard 已连接"
                break
            fi
            sleep 2
        done
    fi
fi

# 启动 iperf3 服务端守护进程（探针兼作测速服务端，供其他探针/中心互测）
echo "[iperf3] 启动服务端守护进程..."
iperf3 -s -D 2>/dev/null || echo "[iperf3] 服务端启动失败（仅影响被测速能力）"

# 启动探针 Agent
echo "[Probe] 启动 Agent..."
exec python /app/agent.py
