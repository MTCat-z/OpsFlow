#!/bin/bash
# ============================================================
# WireGuard Peer 管理 - 为分公司探针生成密钥和配置
# 在中心服务器上执行
# ============================================================

set -e

WG_DIR="/etc/wireguard"
SERVER_PRIV="$WG_DIR/server_private.key"
SERVER_PUB="$WG_DIR/server_public.key"

# 隧道网段前缀
WG_NET="10.99.0"

# 检查中心密钥是否存在
if [ ! -f "$SERVER_PRIV" ]; then
    echo "[错误] 中心密钥不存在，请先完成 WireGuard 安装和中心配置"
    echo "       缺少文件: $SERVER_PRIV"
    exit 1
fi

# 获取中心公网 IP
PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "")
if [ -z "$PUBLIC_IP" ]; then
    echo "[警告] 无法自动获取公网 IP，请手动输入"
    read -p "中心服务器公网 IP: " PUBLIC_IP
fi

SERVER_PUB_KEY=$(cat "$SERVER_PUB")

echo ""
echo "============================================"
echo "  WireGuard Peer 管理"
echo "============================================"
echo "  中心公网IP: $PUBLIC_IP"
echo "  中心公钥:   ${SERVER_PUB_KEY:0:20}..."
echo "============================================"
echo ""
echo "  1. 添加分公司 Peer"
echo "  2. 查看所有 Peer"
echo "  3. 删除 Peer"
echo "  4. 保存配置到 wg0.conf（重启不丢）"
echo "  5. 退出"
echo ""

read -p "请选择 [1-5]: " choice

case $choice in
    1)
        # === 添加分公司 Peer ===
        read -p "分公司名称（如: 北京）: " org_name
        read -p "分公司编码（如: BJ-HQ）: " org_code

        # 分配隧道 IP
        echo ""
        echo "正在分配隧道 IP..."
        USED_IPS=$(wg show wg0 allowed-ips 2>/dev/null | awk '{print $3}' | sed 's|/32||' | sort -t. -k4 -n)
        NEXT_OCTET=2
        while echo "$USED_IPS" | grep -q "${WG_NET}.${NEXT_OCTET}"; do
            NEXT_OCTET=$((NEXT_OCTET + 1))
        done
        TUNNEL_IP="${WG_NET}.${NEXT_OCTET}"

        echo "  分配的隧道 IP: $TUNNEL_IP"

        # 生成密钥对
        echo "正在生成密钥对..."
        PRIV_KEY=$(wg genkey)
        PUB_KEY=$(echo "$PRIV_KEY" | wg pubkey)

        # 保存密钥到文件（备份用）
        echo "$PRIV_KEY" > "$WG_DIR/${org_code}_private.key"
        echo "$PUB_KEY" > "$WG_DIR/${org_code}_public.key"
        chmod 600 "$WG_DIR/${org_code}_private.key"

        # 添加到 WireGuard
        wg set wg0 peer "$PUB_KEY" allowed-ips "${TUNNEL_IP}/32"
        echo "[OK] Peer 已添加到 WireGuard"

        # 生成分公司配置文件
        CONF_FILE="/tmp/wg0-${org_code}.conf"
        cat > "$CONF_FILE" << EOF
[Interface]
PrivateKey = ${PRIV_KEY}
Address = ${TUNNEL_IP}/24

[Peer]
PublicKey = ${SERVER_PUB_KEY}
Endpoint = ${PUBLIC_IP}:51820
AllowedIPs = ${WG_NET}.0/24
PersistentKeepalive = 25
EOF

        # 显示结果
        echo ""
        echo "============================================"
        echo "  添加成功！"
        echo "============================================"
        echo "  分公司:     ${org_name} (${org_code})"
        echo "  隧道 IP:    ${TUNNEL_IP}"
        echo "  探针公钥:   ${PUB_KEY}"
        echo ""
        echo "  分公司配置文件: ${CONF_FILE}"
        echo "  请将此文件发送给分公司 IT 人员"
        echo "  放到分公司服务器的 /etc/wireguard/wg0.conf"
        echo "============================================"
        echo ""

        # 显示配置内容
        echo "--- 配置文件内容 ---"
        cat "$CONF_FILE"
        echo "--------------------"

        # 提示保存
        echo ""
        echo "[提示] 执行选项 4 保存配置，否则重启后 Peer 会丢失"

        # 询问是否保存
        read -p "是否立即保存到 wg0.conf？[Y/n]: " save_now
        if [[ "$save_now" != "n" && "$save_now" != "N" ]]; then
            wg-quick save wg0
            echo "[OK] 配置已保存到 /etc/wireguard/wg0.conf"
        fi
        ;;

    2)
        # === 查看所有 Peer ===
        echo ""
        echo "============================================"
        echo "  当前 WireGuard Peer 列表"
        echo "============================================"
        echo ""
        wg show wg0
        echo ""

        # 列出已保存的分公司密钥文件
        echo "--- 已生成的分公司配置 ---"
        for f in /tmp/wg0-*.conf; do
            if [ -f "$f" ]; then
                echo "  $f"
            fi
        done
        echo ""
        ;;

    3)
        # === 删除 Peer ===
        echo ""
        echo "当前 Peer 列表:"
        wg show wg0 peers | head -20
        echo ""
        read -p "输入要删除的 Peer 公钥（完整）: " del_pubkey
        wg set wg0 peer "$del_pubkey" remove
        echo "[OK] Peer 已删除"

        # 询问是否保存
        read -p "是否立即保存到 wg0.conf？[Y/n]: " save_now
        if [[ "$save_now" != "n" && "$save_now" != "N" ]]; then
            wg-quick save wg0
            echo "[OK] 配置已保存"
        fi
        ;;

    4)
        # === 保存配置 ===
        wg-quick save wg0
        echo "[OK] 配置已保存到 /etc/wireguard/wg0.conf"
        echo ""
        echo "当前配置内容:"
        cat /etc/wireguard/wg0.conf
        ;;

    5)
        echo "退出"
        exit 0
        ;;

    *)
        echo "无效选择"
        ;;
esac
