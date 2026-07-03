import pathlib

content = pathlib.Path('D:/OpsFlow/deploy/upgrade.sh').read_text(encoding='utf-8')

# Fix 1: services check — use container status check instead of --services
old1 = (
    'if ! docker compose -f "$COMPOSE_FILE" ps --services 2>/dev/null | grep -q .; then\n'
    '        warn "当前没有运行中的服务，将执行全新部署而非升级"\n'
    '    fi'
)
new1 = (
    'if ! docker compose -f "$COMPOSE_FILE" ps -a --format \'{{.Status}}\' 2>/dev/null | grep -qv \'^$\'; then\n'
    '        warn "当前没有部署的服务容器，将执行全新部署而非升级"\n'
    '    fi'
)
content = content.replace(old1, new1)

# Fix 2: backup volume mount path — /data -> /app/data
content = content.replace(':/data -v "$PROJECT_DIR/backend/data":/backup alpine cp /data/ops_platform.db', ':/app/data -v "$PROJECT_DIR/backend/data":/backup alpine cp /app/data/ops_platform.db')

pathlib.Path('D:/OpsFlow/deploy/upgrade.sh').write_text(content, encoding='utf-8')
print('Fixed upgrade.sh')
