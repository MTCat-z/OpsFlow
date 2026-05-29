#!/bin/bash
# ============================================================
#  内网运维集成工具平台 — Linux 一键部署脚本
#  版本: 1.0
# ============================================================
#
#  用法:
#    bash deploy.sh              # 交互式部署
#    bash deploy.sh --auto       # 自动模式（全部默认值）
#    bash deploy.sh --uninstall  # 卸载所有服务
#    bash deploy.sh --status     # 查看服务状态
#    bash deploy.sh --logs       # 查看实时日志
#    bash deploy.sh --help       # 显示帮助
#
#  前置要求:
#    - Linux x86_64 / ARM64
#    - Docker Engine 20+
#    - Docker Compose v2 (docker compose 命令)
#    - Git（首次部署时需要）
#
# ============================================================

set -euo pipefail

# ── 全局变量 ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 项目根目录推断逻辑：
#   1. 脚本在 deploy/ 子目录内 → 项目根 = deploy 的上一级
#   2. 当前目录包含 docker-compose.yml → 项目根 = 当前目录
#   3. 都不满足 → 留空，由 setup_project() 引导用户克隆或指定
PROJECT_DIR=""
if [[ -f "$SCRIPT_DIR/../docker-compose.yml" && -d "$SCRIPT_DIR/../backend" ]]; then
    PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [[ -f "$PWD/docker-compose.yml" && -d "$PWD/backend" ]]; then
    PROJECT_DIR="$PWD"
fi
DEPLOY_DIR=""
ENV_FILE=""
IS_LINUX=false
USE_LOCAL_REDIS=false
AUTO_MODE=false
GIT_REPO=""
WEB_PORT=8080       # bridge 模式默认端口；Linux host 模式会自动切换为 80

# 根据 PROJECT_DIR 刷新所有派生路径
refresh_paths() {
    DEPLOY_DIR="$PROJECT_DIR/deploy"
    ENV_FILE="$PROJECT_DIR/backend/.env"
}

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ============================================================
#  工具函数
# ============================================================
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
section() { echo -e "\n${CYAN}${BOLD}━━━ $* ━━━${NC}"; }

# 读取用户输入（支持 auto 模式默认值）
prompt_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    if [[ "$AUTO_MODE" == "true" ]]; then
        printf -v "$var_name" '%s' "$default"
        info "$prompt: $default (自动)"
    else
        read -rp "$(echo -e "${YELLOW}$prompt${NC} [$default]: ")" value
        printf -v "$var_name" '%s' "${value:-$default}"
    fi
}

# ============================================================
#  帮助信息
# ============================================================
show_help() {
    cat << 'EOF'
内网运维集成工具平台 — Linux 部署脚本

用法:
  bash deploy.sh [选项]

选项:
  --auto        自动模式，全部使用默认值（适合快速体验）
  --uninstall   停止并移除所有服务、容器和镜像
  --status      查看各服务运行状态
  --logs        查看所有服务的实时日志
  --restart     重启所有服务
  --backup      备份 SQLite 数据库
  --help        显示此帮助信息

部署流程:
  1. 检查前置条件（Docker、Docker Compose、Git）
  2. 获取项目代码（Git 克隆或本地复制）
  3. 生成配置文件（自动产生密钥，交互式填写关键参数）
  4. 构建并启动所有容器服务
  5. 健康检查确认部署成功

部署后访问:
  Linux 模式:  http://<服务器IP>      (端口 80)
  其他模式:    http://<服务器IP>:8080
  默认账号:    admin / admin123

EOF
}

# ============================================================
#  服务管理命令
# ============================================================
compose_cmd() {
    local files="-f $PROJECT_DIR/docker-compose.yml"
    if [[ "$IS_LINUX" == "true" ]]; then
        files="$files -f $DEPLOY_DIR/docker-compose.linux.yml"
    fi
    docker compose --project-directory "$PROJECT_DIR" $files "$@"
}

do_status() {
    detect_os
    section "服务状态"
    compose_cmd ps
    echo ""
    info "健康检查: $(curl -sf http://127.0.0.1:8000/api/health 2>/dev/null || echo '未响应')"
}

do_logs() {
    detect_os
    compose_cmd logs -f
}

do_restart() {
    detect_os
    section "重启服务"
    compose_cmd restart
    success "所有服务已重启"
}

do_uninstall() {
    detect_os
    section "卸载服务"
    warn "即将停止并移除所有容器，已构建的镜像也将删除。"
    if [[ "$AUTO_MODE" != "true" ]]; then
        read -rp "$(echo -e "${YELLOW}确认卸载？(y/N)${NC} ")" confirm
        [[ "$confirm" != "y" && "$confirm" != "Y" ]] && { info "已取消"; exit 0; }
    fi
    compose_cmd down --rmi all --volumes 2>/dev/null || true
    success "所有服务和镜像已清除"
}

do_backup() {
    section "备份数据库"
    local db_file="$PROJECT_DIR/backend/data/ops_platform.db"
    if [[ -f "$db_file" ]]; then
        local backup_file="$PROJECT_DIR/backend/data/ops_platform_$(date +%Y%m%d_%H%M%S).db.bak"
        cp "$db_file" "$backup_file"
        success "数据库已备份: $backup_file"
    else
        # Docker volume 场景
        local vol_name
        vol_name=$(docker volume ls --format '{{.Name}}' | grep db_data | head -1)
        if [[ -n "$vol_name" ]]; then
            local backup_file="$PROJECT_DIR/backend/data/ops_platform_$(date +%Y%m%d_%H%M%S).db.bak"
            mkdir -p "$PROJECT_DIR/backend/data"
            docker run --rm -v "$vol_name":/data -v "$PROJECT_DIR/backend/data":/backup alpine \
                cp /data/ops_platform.db "/backup/$(basename "$backup_file")"
            success "数据库已备份: $backup_file"
        else
            error "未找到数据库文件或数据卷"
        fi
    fi
}

# ============================================================
#  检测操作系统
# ============================================================
detect_os() {
    if [[ "$(uname -s)" == "Linux" ]]; then
        IS_LINUX=true
        WEB_PORT=80   # host 网络模式下 nginx 直接监听 80 端口
    fi
}

# ============================================================
#  阶段 1: 检查前置条件
# ============================================================
check_prerequisites() {
    section "1/5  检查前置条件"

    local missing=0

    # Docker
    if command -v docker &>/dev/null; then
        success "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
    else
        error "Docker 未安装"
        echo "  安装命令: curl -fsSL https://get.docker.com | sh"
        echo "  或参考:   https://docs.docker.com/engine/install/"
        missing=1
    fi

    # Docker Compose v2
    if docker compose version &>/dev/null 2>&1; then
        success "Docker Compose $(docker compose version --short 2>/dev/null || echo 'v2')"
    else
        error "Docker Compose v2 未安装"
        echo "  安装命令: apt install docker-compose-plugin"
        missing=1
    fi

    # Git
    if command -v git &>/dev/null; then
        success "Git $(git --version | awk '{print $3}')"
    else
        warn "Git 未安装（首次部署需要克隆代码）"
    fi

    # nmap（可选，宿主机安装效果更好）
    if command -v nmap &>/dev/null; then
        success "nmap $(nmap --version 2>/dev/null | head -1)"
    else
        warn "nmap 未安装（容器内已包含，但宿主机安装扫描更准确）"
        if [[ "$IS_LINUX" == "true" && "$AUTO_MODE" != "true" ]]; then
            read -rp "$(echo -e "${YELLOW}是否自动安装 nmap？(y/N)${NC} ")" install_nmap
            if [[ "$install_nmap" == "y" || "$install_nmap" == "Y" ]]; then
                install_system_tools
            fi
        fi
    fi

    # iperf3（可选）
    if command -v iperf3 &>/dev/null; then
        success "iperf3 $(iperf3 --version 2>/dev/null | head -1)"
    else
        warn "iperf3 未安装（容器内已包含，可选安装）"
    fi

    # Docker 守护进程
    if docker info &>/dev/null 2>&1; then
        success "Docker 守护进程运行中"
    else
        error "Docker 守护进程未运行"
        echo "  启动命令: sudo systemctl start docker"
        missing=1
    fi

    if [[ $missing -eq 1 ]]; then
        error "前置条件检查未通过，请先安装缺失组件"
        exit 1
    fi
}

# 安装宿主机工具（需 root 或 sudo）
install_system_tools() {
    info "正在安装系统工具..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq nmap iperf3
    elif command -v yum &>/dev/null; then
        sudo yum install -y -q epel-release
        sudo yum install -y -q nmap iperf3
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y -q nmap iperf3
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm nmap iperf3
    else
        warn "无法自动安装，请手动安装: nmap iperf3"
        return
    fi
    success "系统工具安装完成"
}

# ============================================================
#  阶段 2: 获取项目代码
# ============================================================
setup_project() {
    section "2/5  获取项目代码"

    # ── 情况 1: 已经定位到项目目录 ──
    if [[ -n "$PROJECT_DIR" && -f "$PROJECT_DIR/docker-compose.yml" && -d "$PROJECT_DIR/backend" && -d "$PROJECT_DIR/frontend" ]]; then
        success "项目文件已就绪: $PROJECT_DIR"
        refresh_paths
        return 0
    fi

    # ── 情况 2: 项目不存在，需要获取 ──
    echo ""
    info "未检测到项目文件，请选择获取方式:"
    echo "  1) 从 Git 仓库克隆"
    echo "  2) 指定已有的项目目录"
    echo ""

    local choice=""
    if [[ "$AUTO_MODE" == "true" ]]; then
        choice="1"
    else
        read -rp "$(echo -e "${YELLOW}请选择 (1/2)${NC} [1]: ")" choice
        choice="${choice:-1}"
    fi

    if [[ "$choice" == "2" ]]; then
        # 用户指定已有目录
        local user_path=""
        read -rp "$(echo -e "${YELLOW}请输入项目目录绝对路径${NC}: ")" user_path
        if [[ -z "$user_path" ]]; then
            error "路径不能为空"
            exit 1
        fi
        # 展开 ~ 为 home
        user_path="${user_path/#\~/$HOME}"
        if [[ ! -f "$user_path/docker-compose.yml" || ! -d "$user_path/backend" ]]; then
            error "$user_path 下未找到完整的项目文件"
            exit 1
        fi
        PROJECT_DIR="$(cd "$user_path" && pwd)"
        success "使用已有项目: $PROJECT_DIR"
    else
        # Git 克隆
        local repo_url=""
        if [[ -n "$GIT_REPO" ]]; then
            repo_url="$GIT_REPO"
        else
            read -rp "$(echo -e "${YELLOW}请输入 Git 仓库地址${NC}: ")" repo_url
        fi
        if [[ -z "$repo_url" ]]; then
            error "仓库地址不能为空"
            exit 1
        fi

        # 从仓库 URL 提取项目名
        local repo_name
        repo_name=$(basename "$repo_url" .git)

        # 默认安装到 /opt 下，如果 /opt 不可写则用当前目录
        local install_base="/opt"
        if [[ ! -w "$install_base" ]]; then
            install_base="$PWD"
        fi
        local install_dir="$install_base/$repo_name"

        # 如果目标目录已存在且非空，让用户确认
        if [[ -d "$install_dir" && "$(ls -A "$install_dir" 2>/dev/null)" ]]; then
            warn "目录已存在: $install_dir"
            if [[ "$AUTO_MODE" != "true" ]]; then
                read -rp "$(echo -e "${YELLOW}是否删除后重新克隆？(y/N)${NC} ")" confirm
                if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
                    rm -rf "$install_dir"
                else
                    # 检查已有目录是否包含完整项目
                    if [[ -f "$install_dir/docker-compose.yml" && -d "$install_dir/backend" ]]; then
                        info "已有目录包含完整项目文件，跳过克隆"
                        PROJECT_DIR="$install_dir"
                        refresh_paths
                        success "使用已有项目: $PROJECT_DIR"
                        return 0
                    fi
                    error "已有目录不包含项目文件，请手动处理"
                    exit 1
                fi
            fi
        fi

        info "克隆项目到: $install_dir"
        git clone "$repo_url" "$install_dir"
        PROJECT_DIR="$install_dir"
        success "项目已克隆到: $PROJECT_DIR"
    fi

    # 复制 deploy 脚本到项目内部（如果不存在）
    refresh_paths
    if [[ ! -f "$DEPLOY_DIR/deploy.sh" ]]; then
        mkdir -p "$DEPLOY_DIR"
        cp "$SCRIPT_DIR/deploy.sh" "$DEPLOY_DIR/deploy.sh" 2>/dev/null || true
        # 同时复制其他 deploy 文件
        for f in docker-compose.linux.yml Dockerfile.nginx nginx.linux.conf README.md; do
            [[ -f "$SCRIPT_DIR/$f" ]] && cp "$SCRIPT_DIR/$f" "$DEPLOY_DIR/" 2>/dev/null || true
        done
    fi

    refresh_paths
    success "项目就绪: $PROJECT_DIR"
}

# ============================================================
#  阶段 3: 配置环境变量
# ============================================================
configure_env() {
    section "3/5  配置环境变量"

    if [[ -f "$ENV_FILE" ]]; then
        warn "配置文件已存在: $ENV_FILE"
        if [[ "$AUTO_MODE" != "true" ]]; then
            read -rp "$(echo -e "${YELLOW}是否重新生成？(y/N)${NC} ")" regen
            if [[ "$regen" != "y" && "$regen" != "Y" ]]; then
                success "保留现有配置"
                return 0
            fi
        fi
        cp "$ENV_FILE" "${ENV_FILE}.bak.$(date +%s)"
        info "已备份原配置"
    fi

    # 从模板创建
    if [[ -f "$PROJECT_DIR/backend/.env.example" ]]; then
        cp "$PROJECT_DIR/backend/.env.example" "$ENV_FILE"
    else
        error "未找到 .env.example 模板文件"
        exit 1
    fi

    # ── 生成安全密钥 ──
    info "生成安全密钥..."

    local fernet_key=""
    # 尝试用 Python 生成 Fernet 密钥
    for py in python3 python; do
        if command -v "$py" &>/dev/null; then
            fernet_key=$("$py" -c "
try:
    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())
except ImportError:
    import base64, os
    print(base64.urlsafe_b64encode(os.urandom(32)).decode())
" 2>/dev/null) || true
            break
        fi
    done
    # 兜底: openssl
    if [[ -z "$fernet_key" ]]; then
        fernet_key=$(openssl rand -base64 32)
    fi

    local secret_key
    secret_key=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | xxd -p | tr -d '\n')

    # 替换密钥
    sed -i "s|your-fernet-key-here|$fernet_key|g" "$ENV_FILE"
    sed -i "s|change-me-to-a-long-random-string|$secret_key|g" "$ENV_FILE"
    success "密钥已自动生成"

    # ── Redis 配置 ──
    section "  Redis 配置"
    if ss -tlnp 2>/dev/null | grep -q ":6379 " || netstat -tlnp 2>/dev/null | grep -q ":6379 "; then
        warn "检测到宿主机 Redis 已在 6379 端口运行"
        USE_LOCAL_REDIS=true
    fi
    prompt_input "是否使用宿主机已有 Redis" "$([ "$USE_LOCAL_REDIS" == "true" ] && echo 'Y' || echo 'N')" "use_redis"
    if [[ "$use_redis" == "Y" || "$use_redis" == "y" ]]; then
        USE_LOCAL_REDIS=true
    fi

    # ── 网络配置 ──
    section "  网络配置"
    local server_ip
    server_ip=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "0.0.0.0")
    prompt_input "服务器 IP 地址" "$server_ip" "SERVER_IP"

    # CORS 需要包含部署后的访问地址（Linux host 模式用 80 端口，bridge 模式用 8080）
    local cors_origins="http://${SERVER_IP}:${WEB_PORT},http://localhost:${WEB_PORT},http://127.0.0.1:${WEB_PORT}"
    prompt_input "CORS 允许的域名（逗号分隔）" "$cors_origins" "CORS_ORIGINS"

    # ── 可选配置 ──
    section "  可选集成"
    local zabbix_url="" zabbix_token="" dingtalk_webhook="" dingtalk_secret=""
    prompt_input "Zabbix API 地址（回车跳过）" "" "zabbix_url"
    if [[ -n "$zabbix_url" ]]; then
        prompt_input "Zabbix API Token" "" "zabbix_token"
    fi
    prompt_input "钉钉 Webhook URL（回车跳过）" "" "dingtalk_webhook"
    if [[ -n "$dingtalk_webhook" ]]; then
        prompt_input "钉钉签名密钥（回车跳过）" "" "dingtalk_secret"
    fi

    # ── 应用所有配置到 .env ──
    # CORS（追加或替换）
    if grep -q "^CORS_ORIGINS" "$ENV_FILE"; then
        sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=$CORS_ORIGINS|" "$ENV_FILE"
    else
        echo "CORS_ORIGINS=$CORS_ORIGINS" >> "$ENV_FILE"
    fi

    # Zabbix
    if [[ -n "$zabbix_url" ]]; then
        sed -i "s|^ZABBIX_URL=.*|ZABBIX_URL=$zabbix_url|" "$ENV_FILE"
        sed -i "s|^ZABBIX_API_TOKEN=.*|ZABBIX_API_TOKEN=$zabbix_token|" "$ENV_FILE"
    fi

    # DingTalk
    if [[ -n "$dingtalk_webhook" ]]; then
        sed -i "s|^DINGTALK_WEBHOOK_URL=.*|DINGTALK_WEBHOOK_URL=$dingtalk_webhook|" "$ENV_FILE"
        sed -i "s|^DINGTALK_SECRET=.*|DINGTALK_SECRET=$dingtalk_secret|" "$ENV_FILE"
    fi

    success "配置文件已生成: $ENV_FILE"
}

# ============================================================
#  Docker 镜像加速配置
# ============================================================
configure_docker_mirror() {
    local daemon_json="/etc/docker/daemon.json"

    # 备份现有配置
    if [[ -f "$daemon_json" ]]; then
        cp "$daemon_json" "${daemon_json}.bak.$(date +%s)"
        info "已备份原配置: ${daemon_json}.bak.*"
    fi

    info "写入国内 Docker 镜像加速源..."
    mkdir -p /etc/docker
    cat > "$daemon_json" << 'MIRROR_EOF'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://hub-mirror.c.163.com",
    "https://mirror.ccs.tencentyun.com"
  ]
}
MIRROR_EOF

    info "重启 Docker 守护进程..."
    systemctl daemon-reload
    systemctl restart docker
    sleep 3

    # 验证 Docker 已恢复
    local retry=0
    while ! docker info &>/dev/null 2>&1; do
        retry=$((retry + 1))
        if [[ $retry -ge 15 ]]; then
            error "Docker 重启超时"
            exit 1
        fi
        sleep 2
    done
    success "Docker 已重启，镜像加速已生效"
}

# ============================================================
#  阶段 4: 构建并启动服务
# ============================================================
deploy_services() {
    section "4/5  构建并启动服务"

    # 确保数据目录存在
    mkdir -p "$PROJECT_DIR/backend/data"

    # 检测 Docker Compose 文件
    if [[ ! -f "$PROJECT_DIR/docker-compose.yml" ]]; then
        error "docker-compose.yml 未找到"
        exit 1
    fi

    # 构建 Compose 命令
    local compose_files="-f docker-compose.yml"
    if [[ "$IS_LINUX" == "true" && -f "$DEPLOY_DIR/docker-compose.linux.yml" ]]; then
        compose_files="$compose_files -f deploy/docker-compose.linux.yml"
        info "使用 Linux 优化配置 (host 网络模式)"
    fi

    cd "$PROJECT_DIR"

    # 尝试预拉取基础镜像（非关键，失败不影响后续构建）
    info "尝试拉取基础镜像（失败可忽略，构建时会自动拉取）..."
    for img in redis:7-alpine python:3.11-slim node:18-alpine; do
        docker pull "$img" 2>/dev/null && success "$img 就绪" || warn "$img 预拉取失败，构建时重试"
    done

    # 构建 & 启动
    info "构建镜像并启动服务（首次可能需要 5-10 分钟）..."
    if ! docker compose $compose_files up -d --build; then
        error "构建失败，可能是 Docker 镜像源限流"
        echo ""
        info "尝试配置国内 Docker 镜像加速..."
        configure_docker_mirror
        info "重新构建..."
        docker compose $compose_files up -d --build
    fi

    success "所有服务已启动"

    # 等待服务就绪
    info "等待服务初始化..."
    sleep 5
}

# ============================================================
#  阶段 5: 健康检查
# ============================================================
verify_deployment() {
    section "5/5  健康检查"

    local max_retries=20
    local retry=0
    local health_ok=false

    while [[ $retry -lt $max_retries ]]; do
        retry=$((retry + 1))
        local response
        response=$(curl -sf --connect-timeout 3 --max-time 5 http://127.0.0.1:8000/api/health 2>/dev/null) || true
        if echo "$response" | grep -q '"ok"'; then
            health_ok=true
            break
        fi
        printf "."
        sleep 3
    done
    echo ""

    if [[ "$health_ok" == "true" ]]; then
        success "后端 API 响应正常"

        # 检查前端
        local nginx_ok=false
        local nginx_response
        nginx_response=$(curl -sf --connect-timeout 3 --max-time 5 -o /dev/null -w "%{http_code}" "http://127.0.0.1:${WEB_PORT}/" 2>/dev/null) || true
        if [[ "$nginx_response" == "200" ]]; then
            success "前端页面加载正常"
            nginx_ok=true
        else
            warn "前端页面返回 $nginx_response（可能正在构建中）"
        fi

        # 检查容器状态
        echo ""
        cd "$PROJECT_DIR"
        compose_cmd ps

        local server_ip
        server_ip=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

        echo ""
        echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}${BOLD}║           部署完成！                                ║${NC}"
        echo -e "${GREEN}${BOLD}╠══════════════════════════════════════════════════════╣${NC}"
        echo -e "${GREEN}${BOLD}║${NC}                                                      ${GREEN}${BOLD}║${NC}"
        echo -e "${GREEN}${BOLD}║${NC}  平台地址:  ${CYAN}http://${server_ip}:${WEB_PORT}${NC}              ${GREEN}${BOLD}║${NC}"
        echo -e "${GREEN}${BOLD}║${NC}  API 文档:  ${CYAN}http://${server_ip}:${WEB_PORT}/api/docs${NC}     ${GREEN}${BOLD}║${NC}"
        echo -e "${GREEN}${BOLD}║${NC}                                                      ${GREEN}${BOLD}║${NC}"
        echo -e "${GREEN}${BOLD}║${NC}  默认账号:  ${YELLOW}admin${NC}                                   ${GREEN}${BOLD}║${NC}"
        echo -e "${GREEN}${BOLD}║${NC}  默认密码:  ${YELLOW}admin123${NC}                                ${GREEN}${BOLD}║${NC}"
        echo -e "${GREEN}${BOLD}║${NC}  ${RED}⚠ 首次登录请立即修改密码！${NC}                         ${GREEN}${BOLD}║${NC}"
        echo -e "${GREEN}${BOLD}║${NC}                                                      ${GREEN}${BOLD}║${NC}"
        echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
        echo ""

        # 后续步骤
        echo -e "${BOLD}常用操作:${NC}"
        echo "  查看日志:    bash deploy.sh --logs"
        echo "  查看状态:    bash deploy.sh --status"
        echo "  重启服务:    bash deploy.sh --restart"
        echo "  备份数据:    bash deploy.sh --backup"
        echo "  卸载服务:    bash deploy.sh --uninstall"
        echo ""
        echo -e "${BOLD}配置文件:${NC} $ENV_FILE"
        echo -e "${BOLD}数据目录:${NC} $PROJECT_DIR/backend/data/"
    else
        error "后端健康检查超时，请检查日志:"
        echo "  docker compose logs backend"
        echo "  docker compose logs celery_worker"
        echo ""
        echo "常见问题:"
        echo "  1. 端口被占用:  ss -tlnp | grep -E '(${WEB_PORT}|8000|6379)'"
        echo "  2. 内存不足:    free -h"
        echo "  3. 磁盘空间:    df -h"
        exit 1
    fi
}

# ============================================================
#  主流程
# ============================================================
main() {
    echo -e "${BOLD}"
    echo "  ┌─────────────────────────────────────────┐"
    echo "  │     内网运维集成工具平台 — 部署脚本     │"
    echo "  │              v1.0                       │"
    echo "  └─────────────────────────────────────────┘"
    echo -e "${NC}"

    detect_os
    if [[ "$IS_LINUX" == "true" ]]; then
        info "检测到 Linux 系统，将使用 host 网络模式（nmap 扫描更准确）"
    else
        warn "未检测到 Linux 系统，将使用默认 bridge 网络模式"
    fi

    # 如果已定位到项目，刷新路径变量
    [[ -n "$PROJECT_DIR" ]] && refresh_paths

    check_prerequisites
    setup_project
    configure_env
    deploy_services
    verify_deployment
}

# 管理命令前置检查：确保项目目录已定位
ensure_project() {
    if [[ -z "$PROJECT_DIR" ]]; then
        # 尝试当前目录
        if [[ -f "$PWD/docker-compose.yml" && -d "$PWD/backend" ]]; then
            PROJECT_DIR="$PWD"
            refresh_paths
        else
            error "未找到项目目录，请 cd 到项目根目录后再执行此命令"
            exit 1
        fi
    fi
    refresh_paths
}

# 解析命令行参数
case "${1:-}" in
    --help|-h)    show_help; exit 0 ;;
    --auto)       AUTO_MODE=true; main ;;
    --uninstall)  detect_os; ensure_project; do_uninstall ;;
    --status)     detect_os; ensure_project; do_status ;;
    --logs)       detect_os; ensure_project; do_logs ;;
    --restart)    detect_os; ensure_project; do_restart ;;
    --backup)     ensure_project; do_backup ;;
    *)            main ;;
esac
