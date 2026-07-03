# Linux 部署指南

## 快速开始

将整个项目目录复制到目标 Linux 服务器，然后执行一键部署脚本：

```bash
# 复制项目到服务器
scp -r ops-platform/ user@server:/opt/

# SSH 登录服务器
ssh user@server

# 一键部署
cd /opt/ops-platform
bash deploy/deploy.sh
```

部署脚本会自动完成环境检查、配置生成、镜像构建和服务启动。

## 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 操作系统 | CentOS 7+ / Ubuntu 18.04+ / Debian 10+ | Ubuntu 22.04 LTS |
| CPU | 2 核 | 4 核 |
| 内存 | 2 GB | 4 GB |
| 磁盘 | 10 GB | 20 GB |
| Docker | 20.10+ | 24.x |
| Docker Compose | v2 | v2.23+ |

## 部署模式说明

### Linux 模式（推荐）

在 Linux 上部署时，脚本自动使用 `deploy/docker-compose.linux.yml` 覆盖配置，核心区别是**所有容器使用 host 网络模式**：

- nmap 直接通过物理网卡发送探测包，扫描结果准确
- iperf3 直接使用物理网络接口，测速无损耗
- Redis、后端、Nginx 全部绑定宿主机端口，无需端口映射

这意味着容器直接使用宿主机的 80（Nginx）、6379（Redis）、8000（后端）端口，请确保这些端口未被其他服务占用。

### 默认模式（Windows/Mac 开发）

使用原始 `docker-compose.yml`，容器通过 bridge 网络通信。nmap 扫描受 Docker 网桥代理 ARP 影响，可能产生误报（已用 `-PE` 参数缓解）。

## 部署文件说明

```
deploy/
├── deploy.sh                    # 一键部署脚本（主入口）
├── upgrade.sh                   # 一键升级脚本（已有服务快速更新）
├── docker-compose.linux.yml     # Linux 覆盖配置（host 网络模式）
├── Dockerfile.nginx             # Nginx 多阶段构建（自动编译前端）
├── nginx.linux.conf             # Linux 专用 Nginx 配置
└── README.md                    # 本文档
```

## 手动部署步骤

如果不想使用一键脚本，可以手动执行以下步骤：

```bash
# 1. 安装 Docker（如尚未安装）
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

# 2. 重新登录使 docker 组生效
newgrp docker

# 3. 安装可选工具（宿主机 nmap 扫描更准确）
sudo apt install -y nmap iperf3    # Debian/Ubuntu
sudo yum install -y nmap iperf3    # CentOS/RHEL

# 4. 进入项目目录
cd /opt/ops-platform

# 5. 创建配置文件
cp backend/.env.example backend/.env

# 6. 编辑配置（至少修改密钥）
vim backend/.env

# 7. Linux 模式部署（使用独立 compose 文件，无需合并基础配置）
docker compose -f deploy/docker-compose.linux.yml up -d --build

# 8. 检查状态
docker compose -f deploy/docker-compose.linux.yml ps
curl http://127.0.0.1:8000/api/health
```

## 配置说明

### 必须修改的配置项

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `FERNET_KEY` | 数据加密密钥 | 自动生成或 `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `SECRET_KEY` | JWT 签名密钥 | 任意 32+ 位随机字符串 |

### 可选配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `CORS_ORIGINS` | 允许的前端域名 | 部署脚本自动生成 |
| `ZABBIX_URL` | Zabbix API 地址 | 空（不启用） |
| `ZABBIX_API_TOKEN` | Zabbix API Token | 空 |
| `DINGTALK_WEBHOOK_URL` | 钉钉机器人 Webhook | 空（不启用） |
| `DINGTALK_SECRET` | 钉钉签名密钥 | 空（不启用） |
| `NMAP_PATH` | nmap 二进制路径 | `nmap` |
| `IPERF3_PATH` | iperf3 二进制路径 | `iperf3` |

## 部署后操作

### 访问平台

```
Linux 模式:  http://<服务器IP>        (端口 80，host 网络)
其他模式:    http://<服务器IP>:8080    (端口 8080，bridge 网络)
API 文档:    http://<服务器IP>/api/docs (或 :8080/api/docs)
默认账号:    admin / admin123
```

首次登录会强制修改密码。

### 脚本命令

```bash
bash deploy/deploy.sh              # 重新部署
bash deploy/deploy.sh --status     # 查看服务状态
bash deploy/deploy.sh --logs       # 查看实时日志
bash deploy/deploy.sh --restart    # 重启服务
bash deploy/deploy.sh --backup     # 备份数据库
bash deploy/deploy.sh --uninstall  # 卸载所有服务
```

### 数据备份

SQLite 数据库文件位于 `backend/data/ops_platform.db`，定期备份即可：

```bash
# 手动备份
cp backend/data/ops_platform.db backend/data/ops_platform_$(date +%Y%m%d).db.bak

# 或使用脚本
bash deploy/deploy.sh --backup

# 定时备份（添加到 crontab）
crontab -e
# 每天凌晨 2 点备份
0 2 * * * cp /opt/ops-platform/backend/data/ops_platform.db /opt/backup/ops_$(date +\%Y\%m\%d).db
```

## 防火墙配置

```bash
# Linux 模式（host 网络，端口 80）
# Ubuntu/Debian (ufw)
sudo ufw allow 80/tcp      # 平台 Web
sudo ufw allow 22/tcp      # SSH
sudo ufw enable

# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --reload

# Bridge 模式（Windows/Mac 开发，端口 8080）
# 将上面的 80/tcp 替换为 8080/tcp

# 注意：6379 (Redis) 和 8000 (后端) 不建议对外暴露
```


## 一键升级

对已部署的服务器，每次迭代后只需：

`ash
cd /opt/ops-platform
bash deploy/upgrade.sh
`

脚本会自动完成：

1. **备份数据库** — 升级前自动创建 ackend/data/backup_*.db
2. **暂存本地修改** — 如果有未提交的代码改动，先 git stash
3. **拉取最新代码** — git pull --ff-only
4. **智能分析变更** — 判断是纯代码、依赖、还是前端变更
5. **最小化操作** — 纯后端代码只重启（卷挂载即时生效），依赖变更才重建
6. **健康检查** — 确认后端 API 和 Nginx 正常返回

升级前想预览操作可以加 --dry-run：

`ash
bash deploy/upgrade.sh --dry-run
`

| 变更类型 | 操作 | 耗时 |
|---------|------|------|
| 仅后端 .py 文件 | 重启容器 | ~10s |
| 
equirements.txt / Dockerfile | 重建后端镜像 | ~2min |
| 前端文件 / 
ginx.conf | 重建 Nginx 镜像 | ~2min |
| docker-compose.yml 变更 | 全量重建 | ~3min |

## 常见问题


**Q: 部署时提示端口被占用？**
检查宿主机 80、6379、8000 端口：`ss -tlnp | grep -E '(80|6379|8000)'`。可以停止冲突服务，或修改 docker-compose 中的端口映射。

**Q: 前端构建失败（npm install 超时）？**
Dockerfile.nginx 已配置淘宝镜像源 `registry.npmmirror.com`。如果仍然失败，检查服务器是否能访问外网。

**Q: nmap 扫描结果全是主机在线？**
确认使用的是 Linux 模式部署（host 网络）。可在 Celery Worker 日志中看到是否使用了 host 网络：`docker logs ops_celery | grep network`。

**Q: 如何升级到新版本？**
```bash
cd /opt/ops-platform
git pull
bash deploy/deploy.sh --backup     # 先备份
docker compose -f deploy/docker-compose.linux.yml up -d --build
```

**Q: 如何更换为 PostgreSQL/MySQL？**
修改 `.env` 中的 `DATABASE_URL`，例如 `postgresql://user:pass@host:5432/ops_platform`，并在 requirements.txt 中添加对应驱动（psycopg2 / pymysql）。首次启动需要运行 Alembic 迁移。
