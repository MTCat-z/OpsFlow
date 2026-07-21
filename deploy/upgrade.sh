#!/bin/bash
# ============================================================
#  内网运维集成工具平台 —— Linux 一键升级脚本
#  版本: 1.0
# ============================================================
#
#  用法:
#    bash upgrade.sh              # 交互式升级（默认自动）
#    bash upgrade.sh --dry-run    # 预览将要应用的变更，不实际操作
#    bash upgrade.sh --help       # 显示帮助
#
#  升级流程:
#    1. 备份数据库
#    2. 暂存本地修改，拉取最新代码
#    3. 根据变更类型执行最小化重启/重建
#    4. 健康检查确认服务正常
#
# ============================================================

set -euo pipefail

# ── 全局变量 ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_DIR="$PROJECT_DIR/deploy"
ENV_FILE="$PROJECT_DIR/backend/.env"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.linux.yml"
DRY_RUN=false

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
section() { echo -e "\n${CYAN}${BOLD}┌── $* ──┐${NC}"; }

# ============================================================
#  帮助信息
# ============================================================
show_help() {
    cat << 'EOF'
内网运维集成工具平台 —— Linux 一键升级脚本

用法:
  bash upgrade.sh [选项]

选项:
  --dry-run   预览将要应用的变更，不实际操作
  --help      显示此帮助信息

升级流程:
  1. 备份数据库
  2. 暂存本地修改，拉取最新代码
  3. 分析变更类型（代码 / 依赖 / 前端 / Compose）
  4. 按需重建或重启服务
  5. 健康检查确认升级成功

EOF
}

# ============================================================
#  前置检查
# ============================================================
check_prerequisites() {
    section "前置检查"

    local ok=true

    if [[ ! -f "$PROJECT_DIR/docker-compose.yml" ]]; then
        error "未找到项目文件: $PROJECT_DIR"
        error "请 cd 到项目根目录再执行此脚本"
        ok=false
    fi

    if [[ ! -f "$COMPOSE_FILE" ]]; then
        error "未找到 Linux Compose 文件: $COMPOSE_FILE"
        ok=false
    fi

    if ! command -v git &>/dev/null; then
        error "Git 未安装"
        ok=false
    fi

    if ! docker info &>/dev/null 2>&1; then
        error "Docker 未运行"
        ok=false
    fi

    if ! docker compose -f "$COMPOSE_FILE" ps -a --format '{{.Status}}' 2>/dev/null | grep -qv '^$'; then
        warn "当前没有部署的服务容器，将执行全新部署而非升级"
    fi

    if [[ "$ok" == "false" ]]; then
        error "前置检查未通过，请修复后重试"
        exit 1
    fi

    success "前置检查通过"
}

# ============================================================
#  备份数据库
# ============================================================
backup_database() {
    section "备份数据库"
    local db_src="$PROJECT_DIR/backend/data/ops_platform.db"

    if [[ -f "$db_src" ]]; then
        local ts
        ts=$(date +%Y%m%d_%H%M%S)
        local backup_path="$PROJECT_DIR/backend/data/backup_${ts}.db"
        cp "$db_src" "$backup_path"
        success "数据库已备份: backup_${ts}.db"
    else
        local vol_name
        vol_name=$(docker volume ls --format '{{.Name}}' | grep db_data | head -1)
        if [[ -n "$vol_name" ]]; then
            local ts
            ts=$(date +%Y%m%d_%H%M%S)
            local backup_path="$PROJECT_DIR/backend/data/backup_${ts}.db"
            mkdir -p "$PROJECT_DIR/backend/data"
            docker run --rm -v "$vol_name":/app/data -v "$PROJECT_DIR/backend/data":/backup alpine sh -c "test -f /app/data/ops_platform.db && cp /app/data/ops_platform.db /backup/backup_${ts}.db || true"
            success "数据库已备份 (from volume): backup_${ts}.db"
        else
            warn "未找到数据库文件，跳过备份"
        fi
    fi
}

# ============================================================
#  拉取最新代码
# ============================================================
pull_latest_code() {
    section "拉取最新代码"

    cd "$PROJECT_DIR"

    local has_changes=false
    if ! git diff --quiet HEAD 2>/dev/null; then
        has_changes=true
        warn "检测到本地未提交的修改"
        if [[ "$DRY_RUN" == "false" ]]; then
            local stash_msg="upgrade-auto-stash-$(date +%Y%m%d_%H%M%S)"
            git stash push -m "$stash_msg"
            success "本地修改已暂存 (git stash: $stash_msg)"
        fi
    fi

    local old_head
    old_head=$(git rev-parse HEAD)

    # 先 fetch 确保拿到远端最新引用
    git fetch origin 2>/dev/null || true

    if [[ "$DRY_RUN" == "true" ]]; then
        local behind_count
        behind_count=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
        if [[ "$behind_count" -gt 0 ]]; then
            info "[DRY-RUN] 远端有 $behind_count 个新提交待拉取"
        else
            info "[DRY-RUN] 已是最新"
        fi
        return 0
    fi

    if git pull --ff-only origin main; then
        local new_head
        new_head=$(git rev-parse HEAD)
        if [[ "$old_head" == "$new_head" ]]; then
            success "已是最新，无需升级"
            NO_UPDATE=true
            OLD_HEAD="$old_head"
            NEW_HEAD="$new_head"
        else
            success "代码已更新"
            OLD_HEAD="$old_head"
            NEW_HEAD="$new_head"
            local log_lines
            log_lines=$(git log --oneline "$old_head..$new_head" 2>/dev/null || echo "")
            if [[ -n "$log_lines" ]]; then
                echo ""
                echo "$log_lines" | while IFS= read -r line; do
                    echo "    $line"
                done
            fi
        fi
    else
        error "Git pull 失败，可能是存在冲突"
        if [[ "$has_changes" == "true" ]]; then
            echo "  尝试: git stash pop 恢复本地修改后重试"
        fi
        exit 1
    fi
}

# ============================================================
#  分析变更，判断升级策略
# ============================================================
analyze_changes() {
    section "分析变更类型"

    if [[ "${NO_UPDATE:-false}" == "true" ]]; then
        info "无需变更，跳过分析"
        NEED_RESTART_BACKEND=false
        NEED_REBUILD_BACKEND=false
        NEED_REBUILD_NGINX=false
        NEED_FULL_REBUILD=false
        return 0
    fi

    NEED_RESTART_BACKEND=false
    NEED_REBUILD_BACKEND=false
    NEED_REBUILD_NGINX=false
    NEED_FULL_REBUILD=false

    local changed_files
    # 使用 pull 前后的 HEAD 精确获取所有变更文件（支持多 commit 合并 pull）
    if [[ -n "${OLD_HEAD:-}" && -n "${NEW_HEAD:-}" && "$OLD_HEAD" != "$NEW_HEAD" ]]; then
        changed_files=$(git diff --name-only "$OLD_HEAD" "$NEW_HEAD" 2>/dev/null || echo "")
    else
        changed_files=$(git diff --name-only HEAD@{1} HEAD 2>/dev/null || git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")
    fi

    if [[ -z "$changed_files" ]]; then
        info "无法获取变更文件列表，将执行全量重建"
        NEED_FULL_REBUILD=true
        return 0
    fi

    local backend_py_changed=false
    local requirements_changed=false
    local dockerfile_changed=false
    local frontend_changed=false
    local compose_changed=false
    local nginx_conf_changed=false

    while IFS= read -r file; do
        case "$file" in
            backend/app/*.py|backend/app/**/*.py)
                backend_py_changed=true ;;
            backend/requirements.txt)
                requirements_changed=true ;;
            backend/Dockerfile)
                dockerfile_changed=true ;;
            frontend/*|frontend/**/*)
                frontend_changed=true ;;
            deploy/docker-compose.linux.yml|docker-compose.yml)
                compose_changed=true ;;
            deploy/nginx.linux.conf|deploy/Dockerfile.nginx)
                nginx_conf_changed=true ;;
            deploy/upgrade.sh|deploy/deploy.sh|deploy/README.md)
                ;;
            backend/.env|backend/.env.example)
                if [[ "$file" == "backend/.env.example" ]]; then
                    warn ".env.example 有变更，请检查是否有新增配置项"
                fi
                ;;
            *)
                if [[ "$file" != .* && "$file" != docs/* && "$file" != README* ]]; then
                    backend_py_changed=true
                fi
                ;;
        esac
    done <<< "$changed_files"

    info "变更文件:"
    echo "$changed_files" | while IFS= read -r line; do
        echo "    $line"
    done

    if [[ "$compose_changed" == "true" ]]; then
        NEED_FULL_REBUILD=true
        info "→ Compose 配置变更，执行全量重建"
    elif [[ "$requirements_changed" == "true" || "$dockerfile_changed" == "true" ]]; then
        NEED_REBUILD_BACKEND=true
        info "→ 后端依赖/Dockerfile 变更，需重建后端镜像"
        if [[ "$frontend_changed" == "true" || "$nginx_conf_changed" == "true" ]]; then
            NEED_REBUILD_NGINX=true
            info "→ 前端/Nginx 变更，需重建 Nginx 镜像"
        fi
    elif [[ "$frontend_changed" == "true" || "$nginx_conf_changed" == "true" ]]; then
        NEED_REBUILD_NGINX=true
        info "→ 前端/Nginx 变更，需重建 Nginx 镜像"
        if [[ "$backend_py_changed" == "true" ]]; then
            NEED_RESTART_BACKEND=true
            info "→ 后端代码变更，需重启后端服务"
        fi
    elif [[ "$backend_py_changed" == "true" ]]; then
        NEED_RESTART_BACKEND=true
        info "→ 仅后端 Python 代码变更，重启即可生效（无需重建）"
    fi
}

# ============================================================
#  执行升级
# ============================================================
apply_upgrade() {
    section "执行升级"

    if [[ "${NO_UPDATE:-false}" == "true" ]]; then
        success "已是最新版本，跳过升级"
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY-RUN] 将执行以下操作:"
        [[ "$NEED_FULL_REBUILD" == "true" ]] && echo "  · 全量重建所有服务"
        [[ "$NEED_REBUILD_BACKEND" == "true" ]] && echo "  · 重建后端镜像"
        [[ "$NEED_REBUILD_NGINX" == "true" ]] && echo "  · 重建 Nginx 镜像"
        [[ "$NEED_RESTART_BACKEND" == "true" ]] && echo "  · 重启后端服务"
        echo "  · 健康检查"
        return 0
    fi

    cd "$PROJECT_DIR"

    if [[ "$NEED_FULL_REBUILD" == "true" ]]; then
        info "全量重建中..."
        docker compose -f "$COMPOSE_FILE" up -d --build
    elif [[ "$NEED_REBUILD_BACKEND" == "true" ]]; then
        info "重建后端服务..."
        docker compose -f "$COMPOSE_FILE" build --no-cache backend celery_worker celery_beat
        docker compose -f "$COMPOSE_FILE" up -d backend celery_worker celery_beat
        if [[ "$NEED_REBUILD_NGINX" == "true" ]]; then
            info "重建 Nginx 服务..."
            docker compose -f "$COMPOSE_FILE" build --no-cache nginx
            docker compose -f "$COMPOSE_FILE" up -d nginx
        fi
    elif [[ "$NEED_REBUILD_NGINX" == "true" ]]; then
        info "重建 Nginx 服务..."
        docker compose -f "$COMPOSE_FILE" build --no-cache nginx
        docker compose -f "$COMPOSE_FILE" up -d nginx
        if [[ "$NEED_RESTART_BACKEND" == "true" ]]; then
            info "重启后端服务..."
            docker compose -f "$COMPOSE_FILE" restart backend celery_worker celery_beat
        fi
    elif [[ "$NEED_RESTART_BACKEND" == "true" ]]; then
        info "重启后端服务（代码变更直接通过卷挂载生效）..."
        docker compose -f "$COMPOSE_FILE" restart backend celery_worker celery_beat
    else
        info "未检测到服务变更，重启后端确保一致性..."
        docker compose -f "$COMPOSE_FILE" restart backend celery_worker celery_beat
    fi

    sleep 3
}

# ============================================================
#  健康检查
# ============================================================
health_check() {
    section "健康检查"

    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY-RUN] 将执行健康检查"
        return 0
    fi

    local max_retries=20 retry=0 health_ok=false

    echo -n "等待后端 API 就绪"
    while [[ $retry -lt $max_retries ]]; do
        retry=$((retry + 1))
        local response
        response=$(curl -sf --connect-timeout 3 --max-time 5 http://127.0.0.1:8000/api/health 2>/dev/null) || true
        if echo "$response" | grep -q '"status"'; then
            health_ok=true
            break
        fi
        echo -n "."
        sleep 2
    done
    echo ""

    if [[ "$health_ok" == "true" ]]; then
        success "后端 API 响应正常"
    else
        warn "后端健康检查超时，请手动检查: docker compose logs backend"
    fi

    echo ""
    docker compose -f "$COMPOSE_FILE" ps
}

# ============================================================
#  主流程
# ============================================================
main() {
    echo -e "${BOLD}"
    echo "  ┌──────────────────────────────────────┐"
    echo "  │  内网运维集成工具平台 —— 一键升级脚本 │"
    echo "  │             v1.0                      │"
    echo "  └──────────────────────────────────────┘"
    echo -e "${NC}"

    echo -e "  项目目录: ${CYAN}$PROJECT_DIR${NC}"
    echo -e "  升级时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    check_prerequisites
    backup_database
    pull_latest_code
    analyze_changes
    apply_upgrade
    health_check

    echo ""
    if [[ "$DRY_RUN" == "true" ]]; then
        info "预览完成，未执行任何实际操作。移除 --dry-run 执行升级。"
    elif [[ "${NO_UPDATE:-false}" == "true" ]]; then
        success "升级完成（无代码变更）"
    else
        success "升级完成"
        echo ""
        info "常用命令:"
        echo "   查看日志:   bash deploy/deploy.sh --logs"
        echo "   查看状态:   bash deploy/deploy.sh --status"
        echo "   回滚数据库: cp backend/data/backup_*.db backend/data/ops_platform.db"
    fi
}

case "${1:-}" in
    --help|-h)    show_help; exit 0 ;;
    --dry-run)    DRY_RUN=true; main ;;
    *)            main ;;
esac
