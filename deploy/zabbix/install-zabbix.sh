#!/bin/bash
# ============================================================
#  OpsFlow 分站 Zabbix 一键部署脚本
#  版本: 1.0
#
#  用途:
#    在分公司服务器上部署 Zabbix 监控站，采集本站设备数据，
#    中心 OpsFlow 平台通过 WireGuard 隧道访问本站 Zabbix API 拉取数据。
#
#  部署内容:
#    - MySQL 8.0          (Zabbix 数据库, 数据卷持久化)
#    - Zabbix Server 7.0  (轮询采集, 端口 10051)
#    - Zabbix Web         (Web 界面, 端口 8081)
#    - Zabbix Agent2      (宿主机自监控, CPU/内存/网络为真实值)
#
#  用法:
#    sudo bash install-zabbix.sh                          # 自动探测 wg0 隧道 IP
#    sudo bash install-zabbix.sh --tunnel-ip 10.99.0.2    # 手动指定隧道 IP
#    sudo bash install-zabbix.sh --web-port 8082          # Web 端口冲突时
#
#  完成后脚本自动:
#    1. 更换 Admin 默认密码为随机密码（打印并保存到 .env）
#    2. 创建 API Token（名称 opsflow-central，永不过期，中心平台对接用）
#    3. 配置自监控（内置 "Zabbix server" 主机 -> 本机 Agent + Linux 模板）
#    4. 打印中心平台对接信息（填入 中心 -> 组织管理 -> 编辑）
#
#  可重复执行（幂等）：密码/Token 持久化在部署目录 .env，数据不丢
# ============================================================

set -euo pipefail

# ── 默认参数 ──
TUNNEL_IP=""
WEB_PORT="8081"
INSTALL_DIR="/opt/zabbix"
ZBX_TAG="ubuntu-7.0-latest"     # Zabbix 7.0 LTS；可改 alpine-7.0-latest（更小）

# ── 颜色输出 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
section() { echo -e "\n${CYAN}${BOLD}┌── $* ──┐${NC}"; }

# ── 参数解析 ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --tunnel-ip) TUNNEL_IP="$2"; shift 2 ;;
        --web-port)  WEB_PORT="$2"; shift 2 ;;
        --dir)       INSTALL_DIR="$2"; shift 2 ;;
        --help|-h)   grep '^#' "$0" | sed 's/^# \{0,2\}//' | head -30; exit 0 ;;
        *)           error "未知参数: $1"; exit 1 ;;
    esac
done

# ============================================================
#  1. 前置检查
# ============================================================
section "前置检查"

if [[ $EUID -ne 0 ]]; then
    error "请用 root 或 sudo 执行: sudo bash $0"
    exit 1
fi

for cmd in docker curl python3; do
    if ! command -v "$cmd" &>/dev/null; then
        error "缺少 $cmd 命令，请先安装"
        exit 1
    fi
done
success "docker / curl / python3 就绪"

if ! docker compose version &>/dev/null; then
    error "缺少 docker compose 插件（docker compose version 无输出）"
    exit 1
fi

if ss -tln | grep -q ":${WEB_PORT} "; then
    error "端口 ${WEB_PORT} 已被占用，换端口重试: sudo bash $0 --web-port <其他端口>"
    exit 1
fi

# 隧道 IP 探测（中心平台经它访问本站 Zabbix API）
if [[ -z "$TUNNEL_IP" ]]; then
    TUNNEL_IP=$(ip -4 addr show wg0 2>/dev/null | grep -oE '10\.99\.[0-9]+\.[0-9]+' | head -1 || true)
fi
if [[ -z "$TUNNEL_IP" ]]; then
    warn "未探测到 WireGuard 隧道 IP（wg0 不存在）"
    warn "仍会完成部署，但中心对接地址需手动指定（重跑: --tunnel-ip <IP>）"
    TUNNEL_IP="NONE"
fi
success "隧道 IP: ${TUNNEL_IP}"

API_LOCAL="http://127.0.0.1:${WEB_PORT}/api_jsonrpc.php"
API_CENTRAL="http://${TUNNEL_IP}:${WEB_PORT}/api_jsonrpc.php"

# ============================================================
#  2. 生成部署文件（.env + docker-compose.yml，幂等复用）
# ============================================================
section "生成部署文件"

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

gen_pass() { python3 -c "import secrets; print(secrets.token_hex(12))"; }

if [[ -f .env ]]; then
    success "复用已有 .env（密码/Token 保持不变，数据不丢）"
else
    cat > .env <<EOF
MYSQL_ROOT_PASSWORD=$(gen_pass)
MYSQL_PASSWORD=$(gen_pass)
ZABBIX_ADMIN_PASSWORD=$(gen_pass)
EOF
    chmod 600 .env
    success "已生成 .env（随机密码）"
fi
ADMIN_PASS=$(grep '^ZABBIX_ADMIN_PASSWORD=' .env | cut -d= -f2)

if [[ -f docker-compose.yml && $(grep -c 'opsflow-zabbix' docker-compose.yml 2>/dev/null || true) != "0" ]]; then
    success "复用已有 docker-compose.yml"
else
    cat > docker-compose.yml <<'EOF'
# OpsFlow 分站 Zabbix 7.0（由 install-zabbix.sh 生成）
name: opsflow-zabbix

services:
  zabbix-mysql:
    image: mysql:8.0
    container_name: zabbix-mysql
    restart: unless-stopped
    command: mysqld --character-set-server=utf8mb4 --collation-server=utf8mb4_bin
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: zabbix
      MYSQL_USER: zabbix
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1", "-uzabbix", "-p${MYSQL_PASSWORD}"]
      interval: 10s
      timeout: 5s
      retries: 30
      start_period: 60s

  zabbix-server:
    image: zabbix/zabbix-server-mysql:TAG_PLACEHOLDER
    container_name: zabbix-server
    restart: unless-stopped
    ports:
      - "10051:10051"           # 供本站设备 Agent 主动上报
    environment:
      DB_SERVER_HOST: zabbix-mysql
      MYSQL_DATABASE: zabbix
      MYSQL_USER: zabbix
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      ZBX_CACHESIZE: 128M
    depends_on:
      zabbix-mysql:
        condition: service_healthy

  zabbix-web:
    image: zabbix/zabbix-web-nginx-mysql:TAG_PLACEHOLDER
    container_name: zabbix-web
    restart: unless-stopped
    ports:
      - "8081:8080"             # Web 界面 + API 端点（/api_jsonrpc.php）
    environment:
      DB_SERVER_HOST: zabbix-mysql
      MYSQL_DATABASE: zabbix
      MYSQL_USER: zabbix
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      ZBX_SERVER_HOST: zabbix-server
      ZBX_SERVER_NAME: "OpsFlow 分站监控"
      PHP_TZ: Asia/Shanghai
      TZ: Asia/Shanghai
    depends_on:
      zabbix-mysql:
        condition: service_healthy
      zabbix-server:
        condition: service_started

  zabbix-agent2:
    image: zabbix/zabbix-agent2:TAG_PLACEHOLDER
    container_name: zabbix-agent2
    restart: unless-stopped
    network_mode: host           # CPU/内存/网络指标 = 宿主机真实值
    pid: host
    environment:
      ZBX_HOSTNAME: "Zabbix server"
      ZBX_SERVER_HOST: 127.0.0.1
      ZBX_SERVER_ACTIVE: 127.0.0.1:10051
      TZ: Asia/Shanghai
    volumes:
      - /:/rootfs:ro             # 磁盘容量指标覆盖宿主机根分区（key 为 /rootfs）
    depends_on:
      zabbix-server:
        condition: service_started

volumes:
  mysql_data:
EOF
    sed -i "s/TAG_PLACEHOLDER/${ZBX_TAG}/g; s/\"8081:8080\"/\"${WEB_PORT}:8080\"/" docker-compose.yml
    success "已生成 docker-compose.yml（Web 端口 ${WEB_PORT}）"
fi

# ============================================================
#  3. 拉取镜像（国内网络自动走镜像加速站，可重复执行）
# ============================================================
section "拉取镜像"

MIRRORS=("" "docker.m.daocloud.io/" "docker.1ms.run/" "dockerpull.org/")
IMAGES=(
    "mysql:8.0"
    "zabbix/zabbix-server-mysql:${ZBX_TAG}"
    "zabbix/zabbix-web-nginx-mysql:${ZBX_TAG}"
    "zabbix/zabbix-agent2:${ZBX_TAG}"
)

pull_one() {
    local img="$1" m full
    for m in "${MIRRORS[@]}"; do
        full="${m}${img}"
        if docker pull "$full" >/dev/null 2>&1; then
            if [[ -n "$m" ]]; then
                docker tag "$full" "$img" >/dev/null 2>&1 || true
                docker rmi "$full" >/dev/null 2>&1 || true
                info "  $img <- 镜像站 ${m%%/*}"
            else
                info "  $img <- Docker Hub"
            fi
            return 0
        fi
    done
    return 1
}

for img in "${IMAGES[@]}"; do
    if docker image inspect "$img" >/dev/null 2>&1; then
        info "  $img 已存在，跳过"
        continue
    fi
    info "  拉取 $img ..."
    if ! pull_one "$img"; then
        error "拉取失败: $img（请检查分公司网络后重跑本脚本）"
        exit 1
    fi
done
success "镜像就绪"

# ============================================================
#  4. 启动服务并等待就绪（首次初始化数据库约 2-5 分钟）
# ============================================================
section "启动服务"

docker compose up -d
info "等待 Zabbix 完成初始化（最长 10 分钟）..."

# ── API 辅助函数 ──
rpc() {
    # $1=method  $2=params(json)  $3=auth(可选)
    python3 -c "
import json, sys
payload = {'jsonrpc': '2.0', 'method': sys.argv[1], 'params': json.loads(sys.argv[2]), 'id': 1}
if sys.argv[3]:
    payload['auth'] = sys.argv[3]
print(json.dumps(payload))
" "$1" "$2" "${3:-}" | curl -s -m 30 -X POST \
        -H 'Content-Type: application/json-rpc' -d @- "$API_LOCAL" 2>/dev/null || true
}
rpc_result() { python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('result') if 'result' in d else json.dumps(d.get('error', {}), ensure_ascii=False))
except Exception:
    print('')
" 2>/dev/null || true; }
try_login() { rpc user.login "{\"username\":\"Admin\",\"password\":\"$1\"}" | rpc_result; }

# 就绪标准：Admin 能真实登录（数据库 schema 已建好），而不是仅 HTTP 200
ready=""
for i in $(seq 1 120); do
    r=$(try_login "$ADMIN_PASS")
    if [[ "$r" =~ ^[0-9a-f]{32}$ ]]; then ready="$r"; break; fi
    r=$(try_login "zabbix")
    if [[ "$r" =~ ^[0-9a-f]{32}$ ]]; then ready="$r"; break; fi
    sleep 5
done
if [[ -z "$ready" ]]; then
    error "Zabbix 等待超时。请稍后重跑本脚本继续配置："
    echo "    cd $INSTALL_DIR && sudo bash $0"
    echo "  查看日志: docker compose -f $INSTALL_DIR/docker-compose.yml logs zabbix-server"
    exit 1
fi
success "Zabbix 已就绪"

# ============================================================
#  5. 初始化（Admin 密码 / API Token / 自监控）
# ============================================================
section "初始化（Admin 密码 / API Token / 自监控）"

INITIALIZED=$(grep -c '^ZABBIX_ADMIN_INITIALIZED=1' .env || true)

# ── 登录；默认密码有效则立即改为随机密码并重新登录 ──
AUTH=$(try_login "$ADMIN_PASS")
if ! [[ "$AUTH" =~ ^[0-9a-f]{32}$ ]]; then
    AUTH=$(try_login "zabbix")
    if ! [[ "$AUTH" =~ ^[0-9a-f]{32}$ ]]; then
        error "Admin 登录失败。若忘记密码可重置（清空数据后重新部署）："
        echo "    cd $INSTALL_DIR && docker compose down -v && rm .env && sudo bash $0"
        exit 1
    fi
    if [[ "$INITIALIZED" == "0" ]]; then
        rpc user.update "{\"userid\":\"1\",\"passwd\":\"${ADMIN_PASS}\"}" "$AUTH" | grep -q error \
            && { error "修改 Admin 密码失败"; exit 1; } || true
        echo "ZABBIX_ADMIN_INITIALIZED=1" >> .env
        chmod 600 .env
        AUTH=$(try_login "$ADMIN_PASS")
        [[ "$AUTH" =~ ^[0-9a-f]{32}$ ]] || { error "新密码登录失败"; exit 1; }
        success "Admin 默认密码已更换为随机密码（保存在 .env）"
    fi
fi
success "Admin 登录成功"

# ── 创建 API Token（幂等；明文需从数据库读取）──
TOKEN_NAME="opsflow-central"
TOKEN=""
if grep -q '^ZABBIX_API_TOKEN=' .env; then
    TOKEN=$(grep '^ZABBIX_API_TOKEN=' .env | cut -d= -f2)
    success "复用已保存的 API Token"
else
    existing=$(rpc token.get "{\"output\":[\"tokenid\"],\"filter\":{\"name\":\"${TOKEN_NAME}\"}}" "$AUTH" | rpc_result)
    if [[ "$existing" == "[]" || -z "$existing" ]]; then
        rpc token.create "{\"name\":\"${TOKEN_NAME}\",\"userid\":\"1\",\"expires_at\":0,\"description\":\"OpsFlow 中心平台集成，勿删\"}" "$AUTH" >/dev/null
    fi
    # token.create 只返回 ID 不返回明文，从数据库读取
    MYSQL_PASS=$(grep '^MYSQL_PASSWORD=' .env | cut -d= -f2)
    TOKEN=$(docker exec zabbix-mysql mysql -uzabbix -p"${MYSQL_PASS}" zabbix \
        -N -e "SELECT token FROM tokens WHERE name='${TOKEN_NAME}' ORDER BY tokenid DESC LIMIT 1" 2>/dev/null || true)
    if [[ -n "$TOKEN" ]]; then
        echo "ZABBIX_API_TOKEN=${TOKEN}" >> .env
        chmod 600 .env
        success "API Token 已创建（名称 ${TOKEN_NAME}，永不过期）"
    else
        warn "API Token 读取失败，可登录 Web 界面手动创建（用户设置 -> API 令牌）"
    fi
fi

# ── 自监控：内置 "Zabbix server" 主机（hostid 10084）指向本机 agent2 ──
if [[ "$TUNNEL_IP" != "NONE" ]]; then
    # 1) 接口 IP 改为隧道 IP（agent2 为 host 网络，server 经 NAT 访问）
    IFACE=$(rpc hostinterface.get "{\"output\":[\"interfaceid\",\"ip\"],\"hostids\":\"10084\"}" "$AUTH" | rpc_result)
    IFACE_ID=$(echo "$IFACE" | python3 -c "import json,sys; r=json.load(sys.stdin); print(r[0]['interfaceid'] if isinstance(r,list) and r else '')" 2>/dev/null || true)
    if [[ -n "$IFACE_ID" ]]; then
        R=$(rpc hostinterface.update "{\"interfaceid\":\"${IFACE_ID}\",\"ip\":\"${TUNNEL_IP}\"}" "$AUTH")
        if echo "$R" | grep -q 'interfaceids'; then
            success "自监控接口 -> ${TUNNEL_IP}:10050"
        else
            warn "自监控接口更新失败: $R（不影响核心功能）"
        fi
    fi
    # 2) 挂 "Linux by Zabbix agent" 模板（保留原有模板）
    CUR_TPL=$(rpc host.get "{\"output\":[\"hostid\"],\"selectParentTemplates\":[\"templateid\"],\"filter\":{\"hostid\":[\"10084\"]}}" "$AUTH" | rpc_result)
    LINUX_TPL=$(rpc template.get "{\"output\":[\"templateid\"],\"filter\":{\"host\":\"Linux by Zabbix agent\"}}" "$AUTH" | rpc_result)
    TPL_JSON=$(python3 -c "
import json, sys
try:
    cur = json.loads(sys.argv[1]); assert isinstance(cur, list) and cur
    tpls = [str(t['templateid']) for t in cur[0].get('parentTemplates', [])]
except Exception:
    print('SKIP'); sys.exit()
lid = ''
try:
    r = json.loads(sys.argv[2])
    if isinstance(r, list) and r: lid = str(r[0]['templateid'])
except Exception: pass
if lid and lid not in tpls: tpls.append(lid)
print(json.dumps([{'templateid': t} for t in tpls]))
" "$CUR_TPL" "$LINUX_TPL" 2>/dev/null || echo "SKIP")
    if [[ "$TPL_JSON" != "SKIP" && "$TPL_JSON" != "[]" ]]; then
        R=$(rpc host.update "{\"hostid\":\"10084\",\"templates\":${TPL_JSON}}" "$AUTH")
        if echo "$R" | grep -q 'hostids'; then
            success "已挂载 Linux 监控模板（CPU/内存/网络指标立即可用）"
        else
            warn "模板挂载失败: $R（可稍后在 Web 界面手动添加）"
        fi
    fi
fi

# ============================================================
#  6. 输出对接信息
# ============================================================
section "部署完成"

LOCAL_IP=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' | grep -v '^10\.99\.' | head -1)
[[ -z "$LOCAL_IP" ]] && LOCAL_IP="<本站内网IP>"

echo ""
echo -e "${BOLD}════════════════════════════════════════════════════${NC}"
echo -e "  Zabbix 分站监控已就绪"
echo -e "${BOLD}════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Web 界面${NC}    http://${LOCAL_IP}:${WEB_PORT}   （本站局域网浏览器访问）"
echo -e "  ${CYAN}登录账号${NC}    Admin"
echo -e "  ${CYAN}登录密码${NC}    ${ADMIN_PASS}   （已保存 $INSTALL_DIR/.env）"
echo ""
if [[ -n "$TOKEN" ]]; then
    echo -e "  ${CYAN}API Token${NC}   ${TOKEN}"
    echo -e "               （opsflow-central，永不过期，已保存 .env）"
fi
echo ""
echo -e "  ${CYAN}── 中心平台对接（组织管理 -> 编辑该分公司）──${NC}"
echo -e "  Zabbix API 地址: ${API_CENTRAL}"
echo -e "  Zabbix Token:    ${TOKEN:-<见上方>}"
echo ""
echo -e "  ${CYAN}── 添加本站其他设备监控 ──${NC}"
echo -e "  1. 浏览器打开 Web 界面 -> 数据采集 -> 主机 -> 创建主机"
echo -e "  2. 设备侧 Agent 的 Server 填: ${TUNNEL_IP}:10051"
echo -e "     交换机走 SNMP（模板: Template Net Cisco/Generic SNMP）"
echo ""
echo -e "  ${CYAN}── 常用运维命令（目录 $INSTALL_DIR）──${NC}"
echo -e "  状态:   docker compose ps"
echo -e "  日志:   docker compose logs -f zabbix-server"
echo -e "  重启:   docker compose restart"
echo -e "${BOLD}════════════════════════════════════════════════════${NC}"
