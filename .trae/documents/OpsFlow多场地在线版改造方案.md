# OpsFlow 多场地在线版改造方案

## 概述

将 OpsFlow 从单机内网工具改造为支持多分公司/多场地的在线平台。中心平台部署在信息中心，通过站点到站点 VPN 与各分公司内网打通。各分公司部署探针执行本地网络扫描和测速，Zabbix 负责持续监控告警，中心平台聚合展示。

## 架构总览

```
信息中心（10.10.0.0/24）
  └── 中心平台 10.10.0.10（OpsFlow 中心 + 本地探针）
        ├── FastAPI 后端
        ├── PostgreSQL
        ├── Redis
        ├── Celery Worker + Beat（调度，不执行 nmap/iperf3）
        └── Nginx（前端 + API 网关）

  ←── WireGuard 站点到站点 VPN ──->

北京分公司（10.20.0.0/24）
  ├── 探针 10.20.0.10（nmap + iperf3，本地执行）
  └── Zabbix Server（已有，持续监控）

上海分公司（10.30.0.0/24）
  ├── 探针 10.30.0.10（nmap + iperf3，本地执行）
  └── Zabbix Server（已有，持续监控）
```

## 已确认的设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 探针职责 | 仅 nmap + iperf3 | SSH 类操作从中心发起即可，探针越轻越好 |
| 通信模式 | Pull（探针主动拉取） | 分公司防火墙通常只允许出站，探针无需开端口 |
| 认证方式 | 预共享密钥（probe_key） | 场地数量少，管理员手动分发 key 可控 |
| 部署形态 | Docker Compose | 与现有项目一致，镜像自带 nmap/iperf3/WireGuard |
| 执行模式 | 纯探针模式，无探针则拒绝 | 中心不再直接执行 nmap/iperf3，职责清晰 |
| 单机兼容 | 单机自带本地探针 | 现有服务器加一个 probe 服务即可 |
| VPN 方案 | 探针自带 WireGuard 客户端 | 不是所有分公司路由器能配 VPN，探针自己解决 |
| VPN 角色 | 探针通过 VPN 隧道与中心通信 | 无公网域名，走 VPN 隧道 IP 访问中心 API |
| VPN 密钥管理 | 中心预生成，管理员分发 | 场地 IT 零 WireGuard 知识，只需 docker compose up |
| VPN 配置同步 | 后端直接操作 wg 命令 | 创建组织自动生效，重置密钥秒断旧探针 |
| WireGuard 内核 | 宿主机内核 5.6+ 自带 | 探针镜像装 wireguard-tools + wireguard-go fallback |
| HTTPS 预留 | 未来可 fallback 到公网 HTTPS | 如果分公司封 UDP 51820，需要域名+证书 |
| 监控分工 | Zabbix 实时 + 探针按需 | Zabbix 已部署，两者互补不重叠 |
| 分支策略 | 新分支开发，单机版保留 | 不影响现有部署 |

---

## 项目进度

### 第 1 期：基础设施升级 -- 已完成

| 任务 | 状态 | 说明 |
|------|------|------|
| PostgreSQL 支持 | 已完成 | `database.py` 兼容双数据库，`requirements.txt` 已加 psycopg2-binary |
| 数据库迁移逻辑 | 已完成 | `_migrate_columns()` 兼容 SQLite PRAGMA 和 PostgreSQL information_schema |
| .env.example 更新 | 已完成 | 增加 PostgreSQL 连接示例 |
| 中心部署架构（online compose） | 待开始 | 等 VPN 打通后部署 |

### 第 2 期：多租户数据隔离 -- 已完成

| 任务 | 状态 | 说明 |
|------|------|------|
| Organization 模型 | 已完成 | 含 probe_key/probe_url/zabbix_url/dingtalk_webhook 字段 |
| User 模型扩展 | 已完成 | 加 org_id 字段，新增 org_admin 角色 |
| 14 张业务表加 org_id | 已完成 | 资产/宽带/扫描/测速/拓扑/IPAM/巡检/配置备份/批量命令 |
| JWT 扩展 org_id | 已完成 | token 中携带 org_id |
| 查询自动过滤 | 已完成 | get_current_org 依赖函数，所有 API list 接口按 org 过滤 |
| 组织管理 API | 已完成 | CRUD + 用户数/资产数统计 + 下拉列表 |
| 前端组织管理页面 | 已完成 | 统计卡片 + 表格 + 增删改查 |
| 前端路由 + 侧栏菜单 | 已完成 | /organizations 路由，admin 可见 |
| 用户管理增强 | 已完成 | 创建用户时选择组织，列表显示组织列 |

### 第 3 期：分布式探针 -- 待开始（等 VPN 打通）

| 任务 | 状态 | 说明 |
|------|------|------|
| 探针认证 API（probes.py） | 待开始 | 拉取任务/回传结果/心跳 |
| 任务路由改造 | 待开始 | scan/iperf 不再调 Celery，等待探针拉取 |
| 探针 Agent（agent.py） | 待开始 | 纯 Python 轮询 + 本地执行 nmap/iperf3 |
| 超时处理 | 待开始 | 30 分钟超时标记 failed，5 分钟无心跳标记离线 |
| 探针部署包 | 待开始 | Docker Compose + Dockerfile + README |
| VPN 打通 | 进行中 | WireGuard 站点到站点，信息中心 <-> 各分公司 |

### 第 4 期：前端增强 -- 待开始

| 任务 | 状态 | 说明 |
|------|------|------|
| 中心大屏聚合展示 | 待开始 | 按组织分组，探针状态 + Zabbix 告警 |
| 探针状态页面 | 待开始 | 在线/离线 + 最后心跳 + 重置 key |
| 扫描/测速页面增强 | 待开始 | 探针离线警告 + 等待执行状态 |
| Zabbix 多组织支持 | 待开始 | 按 org_id 查询对应 Zabbix URL |
| iperf3 公共测试点 | 待开始 | 见下方新增章节 |

---

## 改造方案（分 4 期）

### 第 1 期：基础设施升级

#### 1.1 SQLite -> PostgreSQL

**已完成**：`database.py` 已兼容双数据库，`requirements.txt` 已加 psycopg2-binary。

#### 1.2 中心部署架构

**新增文件**：`deploy/docker-compose.online.yml`

```yaml
services:
  postgres:     # PostgreSQL 数据库
  redis:        # Redis（消息队列 + 结果后端）
  backend:      # FastAPI（不含 nmap/iperf3）
  celery_worker: # Celery Worker（调度，不消费 scan/iperf 队列）
  celery_beat:  # 定时任务
  nginx:        # 前端 + API 网关
  probe:        # 本地探针（中心自带，同机部署）
```

注意：中心 Celery Worker **不再消费** scan 和 iperf 队列，这两个队列由探针消费。

### 第 2 期：多租户数据隔离

**已完成**：
- Organization 模型 + 组织管理 API
- User 模型加 org_id + org_admin 角色
- 14 张业务表加 org_id
- JWT 扩展 org_id
- 所有 API 查询自动按 org 过滤
- 前端组织管理页面 + 路由 + 侧栏菜单

### 第 3 期：分布式探针

#### 3.1 探针认证 API

**新增文件**：`backend/app/api/v1/probes.py`

```
GET  /probes/tasks           # 探针拉取待执行任务（Header: X-Probe-Key, X-Org-Code）
POST /probes/tasks/{id}/result  # 探针回传结果
POST /probes/heartbeat       # 探针心跳上报
```

认证流程：
1. 管理员创建组织时自动生成 `probe_key`（`pk_` + 32 位随机字符串）
2. 管理员在组织管理页面查看/重置 key
3. 探针 `.env` 配置 `PROBE_KEY` 和 `ORG_CODE`
4. 每次请求中心 API 携带 `X-Probe-Key` 和 `X-Org-Code` Header
5. 中心验证 key 与 org_code 匹配后放行

#### 3.2 任务路由改造

**文件**：`backend/app/api/v1/scan.py`、`iperf.py`

创建扫描/测速任务时：
1. 检查当前用户的组织是否配置了探针（`probe_key` 非空）
2. 无探针 -> 拒绝创建，提示"请先配置探针"
3. 有探针 -> 入库 `status=pending`，等待探针拉取
4. **不再调用** `celery_app.send_task()` 分发给本地 Celery

#### 3.3 探针拉取与执行

**新增目录**：`backend/app/probe/`

探针核心逻辑（纯 Python，不依赖 Celery）：
```python
# probe/agent.py
while True:
    tasks = http_get(f"{OPSFLOW_URL}/api/v1/probes/tasks",
                     headers={"X-Probe-Key": PROBE_KEY, "X-Org-Code": ORG_CODE})
    for task in tasks:
        if task.type == "scan":
            result = run_nmap(task.target, task.scan_type, task.ports)
        elif task.type == "iperf":
            result = run_iperf3(task.server_host, task.protocol, task.duration)
        http_post(f"{OPSFLOW_URL}/api/v1/probes/tasks/{task.id}/result",
                  headers=..., json=result)
    http_post(f"{OPSFLOW_URL}/api/v1/probes/heartbeat", headers=...)
    sleep(POLL_INTERVAL)  # 默认 10 秒
```

#### 3.4 超时处理

中心 Celery beat 定时检查：
- 任务 `pending` 超过 30 分钟 -> 标记 `failed`，error_message="探针未响应，请检查探针状态"
- 探针心跳超过 5 分钟未上报 -> 组织管理页面标记"探针离线"

#### 3.5 WireGuard 集成

**中心服务器 WireGuard 配置**：

中心 backend 容器需要 `cap_add: [NET_ADMIN]` 权限，安装 `wireguard-tools`，直接操作宿主机 `wg0` 接口。

```yaml
# deploy/docker-compose.online.yml (backend 服务)
services:
  backend:
    cap_add:
      - NET_ADMIN
    # 中心服务器同时运行 WireGuard server
```

中心服务器初始化 WireGuard：
```bash
# 生成中心密钥对
wg genkey | tee /etc/wireguard/central_private.key | wg pubkey > /etc/wireguard/central_public.key

# 中心 wg0.conf
[Interface]
Address = 10.99.0.1/24
ListenPort = 51820
PrivateKey = <中心私钥>

# Peer 由后端自动添加/删除
```

**后端 WireGuard 管理 API**：

创建组织时后端自动：
1. 生成探针的 WireGuard 密钥对
2. 分配隧道 IP（从 10.99.0.2 递增）
3. 调用 `wg set wg0 peer <探针公钥> allowed-ips <隧道IP>/32` 添加 Peer
4. 将密钥信息存入 Organization 表

重置 probe_key 时后端自动：
1. `wg set wg0 peer <旧公钥> remove` 删除旧 Peer
2. 生成新密钥对，添加新 Peer
3. 旧探针立即断连

**探针镜像 WireGuard 组件**：

探针 Dockerfile 包含：
```dockerfile
# wireguard-tools（用户态工具，调用宿主机内核模块）
RUN apt-get install -y wireguard-tools
# wireguard-go（用户态 fallback，内核无模块时使用）
RUN apt-get install -y wireguard-go
```

探针容器需要 `cap_add: [NET_ADMIN]` + `/dev/net/tun` 设备映射：
```yaml
# deploy/probe/docker-compose.yml
services:
  probe:
    image: opsflow/probe:latest
    network_mode: host
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
    env_file: .env
    restart: unless-stopped
```

探针启动流程：
```python
# probe/entrypoint.sh
# 1. 启动 WireGuard
wg-quick up /etc/wireguard/wg0.conf  || wireguard-go wg0  # fallback
# 2. 验证 VPN 连通
ping -c 3 10.99.0.1  # ping 中心隧道IP
# 3. 启动探针 Agent
python agent.py
```

#### 3.6 探针配置包生成

管理员在"组织管理"页面点击"下载探针配置包"，系统自动生成一个 zip 文件：

```
deploy-probe-BJ-HQ.zip
├── docker-compose.yml       # 探针部署配置
├── .env                     # 预填好的配置
│   ├── OPSFLOW_URL=http://10.99.0.1:8000   # 中心隧道IP
│   ├── PROBE_KEY=pk_xxxxxxxxxxxx            # 认证密钥
│   ├── ORG_CODE=BJ-HQ                      # 组织编码
│   ├── WG_PRIVATE_KEY=<探针私钥>             # WireGuard 私钥
│   ├── WG_ADDRESS=10.99.0.2/24             # 探针隧道IP
│   ├── WG_PEER_PUBLICKEY=<中心公钥>          # 中心公钥
│   └── WG_ENDPOINT=<中心公网IP>:51820       # 中心地址
├── wg0.conf                 # WireGuard 配置（预生成）
└── README.md                # 操作指南
```

场地 IT 操作流程：
```bash
# 1. 解压配置包
unzip deploy-probe-BJ-HQ.zip -d opsflow-probe
cd opsflow-probe

# 2. 检查 .env（一般不需要改）
cat .env

# 3. 启动（需要 Docker + Docker Compose）
docker compose up -d

# 4. 确认日志
docker compose logs -f
# 应看到：
# [VPN] WireGuard 已连接，隧道IP: 10.99.0.2
# [Probe] 探针已连接中心，等待任务...

# 5. 验证（可选）
docker compose exec probe ping 10.99.0.1  # ping 中心
```

#### 3.7 探针部署包文件结构

**新增文件**：
```
deploy/probe/
  docker-compose.yml        # 探针 Docker 部署模板
  Dockerfile                # 探针镜像（python:3.12-slim + nmap + iperf3 + wireguard-tools + wireguard-go）
  entrypoint.sh             # 启动脚本（先连VPN再启动Agent）
  wg0.conf.template         # WireGuard 配置模板
  .env.template             # 环境变量模板
  README.md                 # 场地 IT 操作指南
```

### 第 4 期：前端增强

#### 4.1 中心大屏聚合展示

**文件**：`frontend/src/views/dashboard/DashboardPage.vue`

- 按组织分组展示网络状态卡片
- 每个组织显示：探针在线状态、最近扫描结果、Zabbix 告警数
- admin 可切换查看全部组织或单个组织

#### 4.2 探针状态页面

**新增文件**：`frontend/src/views/probes/ProbeStatus.vue`

- 各组织探针在线状态（在线/离线 + 最后心跳时间）
- 探针版本、执行任务数、平均执行时长
- 手动重置 probe_key 按钮

#### 4.3 扫描/测速页面增强

**文件**：`frontend/src/views/scan/ScanPage.vue`、`IperfPage.vue`

- 创建任务前检测探针状态，离线时警告
- 任务列表显示"等待探针执行"状态
- 超时任务显示"探针未响应"

#### 4.4 Zabbix 多组织支持

**文件**：`backend/app/services/zabbix_service.py`

- 根据当前用户的 org_id 查询对应组织的 Zabbix URL
- 中心通过 VPN 访问各分公司的 Zabbix API
- 大屏聚合各分公司的告警数据

---

## iperf3 公共测试点

### 需求

在性能测试页面增加公共 iperf3 测试服务器列表/地图，让用户可以选择全球公共 iperf3 服务器作为测速目标，测试场地到公网的质量。

### 数据来源

使用 [R0GGER/public-iperf3-servers](https://github.com/R0GGER/public-iperf3-servers) 开源列表，包含全球公共 iperf3 服务器的地址、位置、端口信息。

参考项目 [R0GGER/iperf3-map](https://github.com/R0GGER/iperf3-map)：基于 Leaflet.js 的交互式地图，可视化公共 iperf3 服务器并支持从浏览器发起测速。

### 实现方案

#### 后端：公共服务器列表 API

**新增文件**：`backend/app/api/v1/iperf_public.py`

```
GET /iperf/public-servers    # 返回公共 iperf3 服务器列表（带地理位置）
```

- 后端定期（每 24 小时）从 GitHub raw JSON 拉取最新公共服务器列表，缓存到内存或文件
- 返回结构：`[{host, port, location, country, city, lat, lng}, ...]`
- 不入库，纯缓存（公共服务器列表变化频繁，不适合存数据库）

#### 前端：测速目标选择增强

**文件**：`frontend/src/views/iperf/IperfPage.vue`

改造测速目标输入方式：
1. **手动输入**（现有）：用户手动输入 iperf3 服务端地址和端口
2. **内部服务器**（新增）：从资产列表中选择已标记为 iperf3 server 的设备
3. **公共测试点**（新增）：从公共服务器列表选择，支持按国家/城市筛选

公共测试点选择面板：
- 表格列表：服务器地址、位置（国家/城市）、端口、状态
- 可选地图视图：用 Leaflet.js 在地图上标记服务器位置，点击发起测速
- 搜索框：按国家/城市/主机名筛选

#### 前端：地图集成（可选增强）

**新增依赖**：`leaflet`（轻量地图库，约 40KB）

- 在 IperfPage 中增加"地图"tab，用 Leaflet.js 渲染公共服务器位置
- 点击地图标记 -> 填充测速表单 -> 发起测速
- 测速完成后在地图标记上显示带宽结果（颜色编码：绿=快、黄=中、红=慢）
- 不依赖 Google Maps API，用 OpenStreetMap 免费瓦片

#### 单机版兼容

- 公共测试点功能在单机版也可用（不依赖探针）
- 单机版：中心直接执行 iperf3 测速到公共服务器
- 在线版：通过探针执行，测试各分公司到公共服务器的质量

### 文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `backend/app/api/v1/iperf_public.py` | 新增 | 公共服务器列表 API + 缓存逻辑 |
| `backend/app/api/v1/router.py` | 修改 | 注册 iperf_public 路由 |
| `frontend/src/api/index.js` | 修改 | 增加 iperfApi.publicServers 方法 |
| `frontend/src/views/iperf/IperfPage.vue` | 修改 | 增加公共测试点选择面板 |
| `frontend/package.json` | 修改 | 增加 leaflet 依赖 |
| `frontend/src/views/iperf/IperfMap.vue` | 新增 | Leaflet 地图组件（可选） |

---

## 风险与缓解措施

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 数据迁移丢数据 | 高 | 迁移前自动备份 SQLite，迁移后行数校验，保留原文件可回滚 |
| VPN 不通 | 中 | 探针启动时连通性自检，失败时日志明确提示检查 VPN 路由 |
| 探针离线任务卡住 | 中 | 30 分钟超时自动标记 failed，前端显示探针离线警告 |
| 多组织并发性能 | 低 | PostgreSQL 并发能力强，org_id 索引避免全表扫描 |
| 探针 key 泄露 | 低 | key 只能拉取任务/回传结果不能读业务数据，支持一键重置 |
| 分公司子网冲突 | 高 | VPN 规划阶段必须确保各站点子网不重叠 |
| 公共 iperf3 服务器不可用 | 低 | 列表定期更新，测速失败提示换一个服务器 |

## 分支策略

- `main` 分支：保持现有单机版功能，包含多租户改造（已合并）
- `online` 分支：在线版改造，探针 + VPN + 中心平台
- iperf3 公共测试点功能在 `main` 分支开发（单机版也适用）

现有单机版不受影响，在线版在新分支上开发，成熟后可选择合并。

## 验证步骤

1. 本地 Docker Compose 启动 PostgreSQL + 后端 + 本地探针，验证扫描/测速通过探针执行
2. 创建两个组织 + 各自用户，验证数据隔离
3. 模拟探针离线，验证超时处理和前端警告
4. 配置 WireGuard VPN，部署远程探针，验证跨网段扫描
5. 配置各组织 Zabbix URL，验证中心大屏聚合告警数据
6. 压力测试：多组织并发扫描任务排队和执行性能
7. 验证 iperf3 公共测试点列表加载和测速功能
