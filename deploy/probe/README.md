# OpsFlow 探针部署指南

本指南面向各分公司/场地的 IT 运维人员，指导如何在本地网络部署 OpsFlow 探针。

探针是一个轻量级容器，部署在分公司内网中，负责本地执行 nmap 网络扫描和 iperf3 带宽测速，通过 WireGuard VPN 隧道与中心服务器通信。

## 架构说明

```
分公司内网                         中心服务器（公网）
┌─────────────────────┐           ┌─────────────────────┐
│  探针容器            │           │  OpsFlow 平台        │
│  ┌────────────────┐ │   VPN     │  ┌────────────────┐ │
│  │ nmap / iperf3  │─┼──隧道─────┼──│  FastAPI 后端   │ │
│  │ Python Agent   │ │ 10.99.x.x │  │  10.99.0.1     │ │
│  └────────────────┘ │           │  └────────────────┘ │
│  WireGuard 客户端    │           │  WireGuard 服务端    │
└─────────────────────┘           └─────────────────────┘
```

- **Pull 模式**：探针主动轮询中心服务器获取任务，执行后将结果回传，无需在分公司开放入站端口
- **本地执行**：nmap/iperf3 在分公司内网直接运行，扫描结果反映真实网络拓扑
- **VPN 加密**：所有通信走 WireGuard 加密隧道，不暴露在公网

## 前置要求

### 系统要求

| 项目 | 最低要求 | 说明 |
|------|---------|------|
| 操作系统 | Linux（内核 5.6+） | WireGuard 自 5.6 起内置内核支持 |
| 推荐发行版 | Ubuntu 22.04 LTS / Debian 12 | 内核版本满足要求，开箱即用 |
| Docker | 20.10+ | |
| Docker Compose | v2 | |
| 内存 | 512 MB | 探针非常轻量 |
| 磁盘 | 1 GB | |

> **内核版本检查**：WireGuard 需要内核 5.6 以上。执行 `uname -r` 确认。
> 如果内核低于 5.6，探针镜像内置了 `wireguard-go`（用户态实现）作为后备方案，但性能略差。

### 网络要求

- 分公司网络需能访问中心服务器的公网 IP，UDP 51820 端口可达
- 如果分公司防火墙拦截 UDP 51820，请联系中心 IT 协调放行
- 探针使用 `host` 网络模式，直接使用宿主机网卡进行本地扫描

### 需要从中心 IT 获取的信息

部署前请向中心 IT 管理员索取以下信息：

1. **探针密钥**（PROBE_KEY）- 格式如 `pk_xxxxxxxxxxxx`
2. **组织编码**（ORG_CODE）- 如 `BJ-HQ`
3. **WireGuard 配置文件**（wg0.conf）- 包含探针私钥、中心公钥、隧道 IP 等

## 部署步骤

### 1. 安装 Docker（如尚未安装）

```bash
# 一键安装 Docker
curl -fsSL https://get.docker.com | sh

# 启动 Docker 并设置开机自启
sudo systemctl enable --now docker

# 将当前用户加入 docker 组（免 sudo）
sudo usermod -aG docker $USER
newgrp docker
```

### 2. 获取探针部署包

从中心 IT 获取探针部署包（`opsflow-probe.tar.gz`），上传至分公司服务器：

```bash
# 上传到服务器（在本地执行）
scp opsflow-probe.tar.gz user@分公司服务器IP:/opt/

# 登录分公司服务器
ssh user@分公司服务器IP
```

### 3. 解压部署包

```bash
cd /opt
tar xzf opsflow-probe.tar.gz
cd opsflow-probe
```

解压后目录结构：

```
opsflow-probe/
├── docker-compose.yml      # Docker Compose 配置
├── Dockerfile              # 探针镜像构建文件
├── entrypoint.sh           # 探针启动脚本
├── .env.template           # 环境变量模板
├── wg0.conf.template       # WireGuard 配置模板
└── README.md               # 本文档
```

### 4. 配置环境变量

```bash
# 从模板创建 .env 文件
cp .env.template .env

# 编辑配置
vi .env
```

填入中心 IT 提供的信息：

```env
# 中心服务器地址（VPN 隧道 IP，通常无需修改）
OPSFLOW_URL=http://10.99.0.1:8000

# 探针认证密钥（从中心 IT 获取）
PROBE_KEY=pk_你获取的密钥

# 组织编码（从中心 IT 获取）
ORG_CODE=BJ-HQ

# 轮询间隔（秒，默认 10 秒）
POLL_INTERVAL=10
```

### 5. 配置 WireGuard VPN

将中心 IT 提供的 WireGuard 配置文件放到当前目录，命名为 `wg0.conf`：

```bash
# 如果中心 IT 提供的是文件，直接上传覆盖
# 如果需要手动创建：
cp wg0.conf.template wg0.conf
vi wg0.conf
```

填入中心 IT 提供的密钥和地址：

```ini
[Interface]
PrivateKey = <中心IT提供的探针私钥>
Address = <中心IT分配的隧道IP>/24

[Peer]
PublicKey = <中心IT提供的中心公钥>
Endpoint = <中心服务器公网IP>:51820
AllowedIPs = 10.99.0.0/24
PersistentKeepalive = 25
```

> **安全提示**：`wg0.conf` 包含私钥，请妥善保管，不要泄露或上传到公共代码仓库。

### 6. 构建并启动探针

```bash
docker compose up -d --build
```

首次构建需要下载基础镜像和安装依赖，约 3-5 分钟。

### 7. 查看启动日志

```bash
docker compose logs -f
```

正常启动日志如下：

```
[Probe] OpsFlow 探针启动中...
[VPN] 启动 WireGuard...
[VPN] 等待隧道连通...
[VPN] WireGuard 已连接
[Probe] 启动 Agent...
2026-01-15 10:00:00 [INFO] OpsFlow 探针已启动
2026-01-15 10:00:00 [INFO] 中心地址: http://10.99.0.1:8000
2026-01-15 10:00:00 [INFO] 组织编码: BJ-HQ
```

看到 `心跳已发送` 且无报错即表示部署成功。按 `Ctrl+C` 退出日志查看。

## 验证方法

### 1. 检查容器运行状态

```bash
docker compose ps
```

确认 `opsflow-probe` 状态为 `Up`。

### 2. 检查 VPN 隧道连通性

```bash
# 进入容器检查 WireGuard 接口
docker compose exec probe wg show

# 应看到 wg0 接口信息，包含最新的握手时间（latest handshake）
```

```bash
# 测试到中心服务器的连通性
docker compose exec probe ping -c 3 10.99.0.1
```

### 3. 检查探针心跳

在中心服务器的 OpsFlow 平台上，进入「组织管理」页面，确认本组织探针状态为「在线」，且 `最后心跳时间` 持续更新。

### 4. 手动触发测试任务

在 OpsFlow 平台上对本组织创建一个简单的 nmap 扫描任务（如扫描 `127.0.0.1`），查看探针日志是否收到并执行任务：

```bash
docker compose logs -f | grep "收到"
```

应看到类似 `收到 1 个任务` 的日志，随后在平台上可查看扫描结果。

## 常见问题排查

### Q: 启动时报错「缺少 PROBE_KEY 或 ORG_CODE」

检查 `.env` 文件是否已正确填写 `PROBE_KEY` 和 `ORG_CODE`：

```bash
cat .env
```

确认两个变量均已填入有效值（非空、非模板默认值）。

### Q: VPN 隧道未连通

日志显示 `[WARN] VPN 隧道未连通，尝试直连中心...` 时，按以下步骤排查：

1. **检查 wg0.conf 配置**：确认 `Endpoint` 填写的是中心服务器公网 IP 和端口 51820
2. **检查防火墙放行**：确认分公司出站 UDP 51820 未被拦截

```bash
# 测试到中心服务器的 UDP 51820 连通性
docker compose exec probe ping -c 3 <中心服务器公网IP>
```

3. **检查密钥匹配**：确认 `wg0.conf` 中的私钥和公钥与中心服务器配置一致（联系中心 IT 核对）
4. **查看 WireGuard 详细状态**：

```bash
docker compose exec probe wg show
```

如果 `latest handshake` 显示为 `(none)` 或很久以前，说明握手未成功。

### Q: 心跳失败，HTTP 502 / 连接被拒绝

VPN 隧道可能未连通，或中心服务器未启动。先确认 VPN 正常（见上一条），再确认 `OPSFLOW_URL` 地址正确。

### Q: 容器不断重启

```bash
# 查看详细错误日志
docker compose logs --tail 50
```

常见原因：
- `.env` 文件缺失或变量为空
- `wg0.conf` 文件不存在（如果不需要 VPN，请确认中心服务器可通过直连访问并移除 volumes 中的 wg0.conf 挂载）

### Q: nmap 扫描结果不准确

探针使用 `host` 网络模式，nmap 直接通过宿主机物理网卡发送探测包。如果扫描结果异常：
- 确认宿主机未运行防火墙（如 ufw / firewalld）拦截了 nmap 的探测包
- 确认 Docker 使用的是 `host` 网络模式（检查 docker-compose.yml 中 `network_mode: host`）

### Q: 如何更新探针

收到中心 IT 的更新通知后：

```bash
cd /opt/opsflow-probe
docker compose down
# 替换更新后的文件
docker compose up -d --build
```

### Q: 如何完全卸载探针

```bash
cd /opt/opsflow-probe
docker compose down
docker rmi $(docker images -q opsflow-probe*) 2>/dev/null
cd /opt
rm -rf opsflow-probe
```

## 日常运维

### 查看实时日志

```bash
docker compose logs -f
```

### 重启探针

```bash
docker compose restart
```

### 停止探针

```bash
docker compose down
```

### 设置开机自启

`docker-compose.yml` 中已配置 `restart: unless-stopped`，只要 Docker 服务设置了开机自启，探针容器会自动随系统启动恢复：

```bash
sudo systemctl enable docker
```

## 联系支持

如遇到本指南未覆盖的问题，请联系中心 IT 管理员，并提供以下信息以便排查：

1. 探针日志输出（`docker compose logs --tail 100`）
2. WireGuard 状态（`docker compose exec probe wg show`）
3. 宿主机系统信息（`uname -a`）
4. 组织编码和探针部署时间
