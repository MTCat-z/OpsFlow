# OpsFlow 探针部署 SOP（分公司版）

> 本文档面向分公司/场地 IT 人员，指导如何在本地服务器上部署 OpsFlow 网络探针。
> 探针部署后，信息中心可远程下发 nmap 扫描和 iperf3 测速任务，探针在本地执行并回传结果。

---

## 一、前置要求

### 1.1 服务器要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Linux，内核 5.6 以上（推荐 Ubuntu 22.04/24.04） |
| Docker | 20.10 以上 |
| Docker Compose | v2 以上 |
| 网络 | 能出公网（UDP 51820 到达中心服务器） |
| 设备 | `/dev/net/tun` 存在（大部分 Linux 默认有） |

### 1.2 检查命令

```bash
# 检查内核版本（需要 5.6 以上）
uname -r

# 检查 Docker
docker --version
docker compose version

# 检查 tun 设备
ls -la /dev/net/tun
# 应输出: crw-rw-rw- ... /dev/net/tun
```

如果 Docker 没装：

```bash
# Ubuntu/Debian
apt update && apt install -y docker.io docker-compose-plugin
systemctl enable docker && systemctl start docker

# 验证
docker run hello-world
```

如果 `/dev/net/tun` 不存在：

```bash
modprobe tun
# 如果还不行，说明是虚拟机，联系云服务商开启 tun 设备
```

---

## 二、接收配置文件

信息中心管理员会在前端"组织管理"页面点击"生成探针"和"下载配置"，得到一个 zip 包。
解压后包含以下文件：

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | 容器编排 |
| `Dockerfile` | 镜像构建文件（离线构建用） |
| `agent.py` | 探针 Agent 程序 |
| `entrypoint.sh` | 容器启动脚本 |
| `.env` | 探针环境变量（已填好，无需修改） |
| `wg0.conf` | WireGuard VPN 配置（已填好，无需修改） |
| `README.md` | 简要说明 |

> **重要**：`.env` 里的 `PROBE_KEY` 是 32 位十六进制字符串（只含 `0-9` 和 `a-f`）。
> 传输时请用 scp/文件传输，**不要截图**，避免 OCR 把 `0` 识别成 `O`、`5` 识别成 `S` 等。

---

## 三、部署步骤

### 3.1 创建探针目录并解压配置包

```bash
mkdir -p /opt/opsflow-probe
cd /opt/opsflow-probe

# 把信息中心发来的 zip 包解压到此处
unzip /path/to/probe-XXXX.zip
```

确认文件齐全：

```bash
ls -la
# 应看到: docker-compose.yml Dockerfile agent.py entrypoint.sh .env wg0.conf README.md
```

> **注意**：`agent.py` 必须有内容（约 225 行）。如果 `agent.py` 是空文件（0 字节），
> 说明下载的配置包有 bug，请联系信息中心重新生成或手动补全（见附录 C）。

### 3.2 选择 VPN 部署模式

探针与中心服务器通过 WireGuard VPN 通信，有两种模式：

#### 模式 A：宿主机运行 WireGuard（推荐，稳定性最好）

在宿主机上安装 WireGuard 并启动，容器通过 `network_mode: host` 共享隧道。
此模式避免了容器内 TUN 设备冲突，是经过实战验证的推荐方案。

```bash
# 安装 WireGuard
apt install -y wireguard

# 把配置包里的 wg0.conf 复制到系统目录
cp /opt/opsflow-probe/wg0.conf /etc/wireguard/wg0.conf
chmod 600 /etc/wireguard/wg0.conf

# 启动 WireGuard
wg-quick up wg0

# 验证隧道连通
ping -c 3 10.99.0.1
# 应能 ping 通

# 设置开机自启
systemctl enable wg-quick@wg0
```

#### 模式 B：容器内运行 WireGuard

如果无法在宿主机安装 WireGuard，可以让容器自己启动 VPN。
此模式需要 `/dev/net/tun` 设备和 `NET_ADMIN` 权限（docker-compose.yml 已配置）。

无需额外操作，直接进入下一步即可。entrypoint.sh 会自动检测：如果隧道已连通则跳过，否则在容器内启动 WireGuard。

> **注意**：不要同时用模式 A 和模式 B。如果宿主机已运行 WireGuard，容器会自动检测并跳过，
> 不会重复启动。但如果宿主机的接口名也是 `wg0` 且容器试图创建同名接口，会报
> `Failed to create TUN device: device or resource busy`。entrypoint.sh 已处理此情况。

### 3.3 确认 .env 配置

```bash
cat /opt/opsflow-probe/.env
```

确认以下关键字段：

```ini
# OPSFLOW_URL 必须是隧道 IP + /api/v1 后缀，不能用公网 IP
OPSFLOW_URL=http://10.99.0.1:8000/api/v1

# PROBE_KEY 是 32 位 hex（只含 0-9 和 a-f），不含大写字母
PROBE_KEY=pk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ORG_CODE 大小写敏感，需与中心服务器一致
ORG_CODE=XXXX-XX
```

> **关键**：`OPSFLOW_URL` 必须用隧道 IP `10.99.0.1`，不能用公网 IP。
> 因为公网通常只转发了 UDP 51820（WireGuard），HTTP 端口未转发，用公网 IP 会连不上 API。

### 3.4 启动探针

```bash
cd /opt/opsflow-probe
docker compose up -d --build
```

> `--build` 表示从本地 Dockerfile 构建镜像，无需从远程拉取。

### 3.5 查看启动日志

```bash
docker compose logs -f
```

**正常启动日志（模式 A - 宿主机 VPN）：**

```
[Probe] OpsFlow 探针启动中...
[VPN] 隧道已连通（宿主机 WireGuard），跳过容器内 VPN 启动
[Probe] 启动 Agent...
2026-08-03 10:00:00 [INFO] OpsFlow 探针已启动
2026-08-03 10:00:00 [INFO] 中心地址: http://10.99.0.1:8000/api/v1
2026-08-03 10:00:00 [INFO] 组织编码: XIAN-LT
```

**正常启动日志（模式 B - 容器 VPN）：**

```
[Probe] OpsFlow 探针启动中...
[VPN] 隧道未连通，尝试在容器内启动 WireGuard...
[VPN] 等待隧道连通...
[VPN] WireGuard 已连接
[Probe] 启动 Agent...
2026-08-03 10:00:00 [INFO] OpsFlow 探针已启动
```

日志应持续运行，**不应出现 `exited with code 0`**。按 `Ctrl+C` 退出日志查看（探针继续后台运行）。

---

## 四、验证

### 4.1 验证 VPN 连通

```bash
# 模式 A：在宿主机测试
ping -c 3 10.99.0.1

# 模式 B：在容器内测试
docker compose exec opsflow-probe ping -c 3 10.99.0.1
```

应能 ping 通。如果不通，见排查章节。

### 4.2 验证 API 可达

```bash
# 在探针服务器上测试心跳接口
curl -X POST http://10.99.0.1:8000/api/v1/probes/heartbeat \
  -H "X-Probe-Key: $(grep PROBE_KEY /opt/opsflow-probe/.env | cut -d= -f2)" \
  -H "X-Org-Code: $(grep ORG_CODE /opt/opsflow-probe/.env | cut -d= -f2)"
```

应返回 `{"success":true,"server_time":"..."}`。

如果返回 `{"detail":"探针认证失败"}`，说明 `PROBE_KEY` 或 `ORG_CODE` 不对（见排查章节）。

### 4.3 验证探针在线

在 OpsFlow 前端"组织管理"页面确认：
- 探针状态显示"**在线**"（绿色标签）
- 探针持续在线（不会 5 分钟后变离线）

> **注意**：如果探针显示在线但很快变离线，说明是手动 curl 测试触发的一次性心跳，
> 探针 agent 实际没在运行。需确认容器没有 `exited with code 0`。

### 4.4 验证任务执行

信息中心创建一个扫描任务（目标填本分公司的内网网段），确认：
- 探针日志出现 `收到 1 个任务`
- 任务状态从 pending -> running -> completed
- 扫描结果正确显示分公司内网设备

---

## 五、日常维护

### 5.1 查看日志

```bash
# 查看最近日志
docker compose logs --tail 50

# 实时跟踪日志
docker compose logs -f
```

### 5.2 重启探针

```bash
cd /opt/opsflow-probe
docker compose restart
```

### 5.3 更新探针

```bash
cd /opt/opsflow-probe
docker compose down
docker compose up -d --build
```

### 5.4 停止探针

```bash
cd /opt/opsflow-probe
docker compose down
```

### 5.5 模式 A 的 VPN 维护

```bash
# 查看 VPN 状态
wg show

# 重启 VPN
wg-quick down wg0 && wg-quick up wg0

# VPN 日志
journalctl -u wg-quick@wg0 -f
```

---

## 六、常见问题排查

### 问题 1：VPN 隧道未连通（ping 不通 10.99.0.1）

**排查步骤：**

```bash
# 1. 检查 wg0.conf 中的 Endpoint 和 AllowedIPs
cat /etc/wireguard/wg0.conf
# Endpoint 应为 115.238.43.18:51820
# AllowedIPs 必须是 10.99.0.0/24（不是 10.99.6.0/24 或其他）

# 2. 检查 WireGuard 是否运行
wg show
# 应看到 interface: wg0 和 peer 信息
# 如果有 "latest handshake" 说明握手成功
# 如果 "transfer: 0 B received" 说明握手未成功

# 3. 测试到中心服务器的公网 IP 是否可达
ping -c 3 115.238.43.18

# 4. 检查分公司防火墙是否封了 UDP 51820
```

**常见原因：**

| 原因 | 解决方案 |
|------|----------|
| 中心服务器在 NAT 后，网关未转发 UDP 51820 | 联系信息中心，在网关上配置端口转发：公网 51820/UDP → 中心服务器内网 IP:51820/UDP |
| AllowedIPs 写错（如 10.99.6.0/24） | 改为 `10.99.0.0/24` |
| 公钥/私钥不匹配 | 联系信息中心重新生成配置 |
| 分公司防火墙封了 UDP 51820 | 联系分公司网络管理员放行 |

> **注意**：`nc -zuv 115.238.43.18 51820` 显示 "succeeded" **不能**证明 UDP 端口真的通。
> nc 的 UDP 模式只发包不等回应，结果不可靠。请以 `wg show` 的 handshake 和 transfer 为准。

### 问题 2：容器不断重启（exited with code 0）

**现象**：`docker compose logs` 显示 `[Probe] 启动 Agent...` 后立即 `exited with code 0`

**根因**：agent.py 进程立即退出。最常见原因是：

1. **agent.py 是空文件**：下载的配置包里 agent.py 为 0 字节
   ```bash
   wc -l /opt/opsflow-probe/agent.py
   # 如果输出 0，说明是空文件，见附录 C 手动补全
   ```

2. **环境变量未加载**：.env 文件变量名拼错（如 `PR0BE_KEY` 数字 0 代替字母 O）
   ```bash
   # 检查变量名是否正确（用 hexdump 排除隐藏字符）
   hexdump -C /opt/opsflow-probe/.env | head -5
   # 应看到 OPSFLOW_URL 和 PROBE_KEY（字母 O，不是数字 0）

   # 检查容器实际拿到的环境变量
   docker compose run --rm --no-deps opsflow-probe env | grep -E "PROBE_KEY|ORG_CODE|OPSFLOW_URL"
   ```

3. **手动运行 agent 看真实报错**：
   ```bash
   docker compose run --rm --no-deps opsflow-probe python /app/agent.py
   ```

### 问题 3：探针认证失败（HTTP 401）

**现象**：curl 测试心跳返回 `{"detail":"探针认证失败"}`

**排查**：

```bash
# 1. 从中心服务器数据库获取真实的 PROBE_KEY
# 在中心服务器执行：
docker exec ops_backend python -c "
from app.core.database import engine
from sqlmodel import Session, select
from app.models.organization import Organization
with Session(engine) as s:
    for o in s.exec(select(Organization)).all():
        print(f'code={o.code}  probe_key={o.probe_key}  active={o.is_active}')
"

# 2. 对比 .env 里的值是否完全一致（逐字符对比）
# PROBE_KEY 是 32 位 hex，只含 0-9 和 a-f，不含大写字母
# 常见 OCR 误读：0↔O, 5↔S, 8↔B, 1↔l, 6↔G

# 3. 确认 ORG_CODE 大小写一致
```

> **最佳实践**：PROBE_KEY 不要通过截图/手打传输，用 scp 或文件传输避免字符识别错误。

### 问题 4：探针显示在线但很快变离线

**现象**：手动 curl 测试后前端显示在线，5 分钟后变离线

**根因**：探针 agent 没有真正运行，手动 curl 只触发了一次性心跳。心跳超时为 5 分钟。

**解决**：确认容器正常运行（没有 exited），且日志里有 agent.py 的持续输出。

### 问题 5：Failed to create TUN device

**现象**：容器日志报 `Failed to create TUN device: device or resource busy` 或 `invalid argument`

**根因**：宿主机已运行 WireGuard（接口名 wg0），容器用 `network_mode: host` 共享网络后又试图创建同名接口，冲突。

**解决**：使用模式 A（宿主机运行 WireGuard），entrypoint.sh 会自动检测隧道是否已连通并跳过容器内 VPN 启动。如果仍报错，确保 entrypoint.sh 是最新版本。

### 问题 6：镜像构建失败

**现象**：`docker compose up -d --build` 构建失败

**常见原因**：
- 网络问题导致 apt 源不可达：Dockerfile 已配置阿里云镜像，如仍失败检查网络
- 磁盘空间不足：`df -h` 检查
- Docker 版本太旧不支持 buildx：升级 Docker

---

## 附录 A：部署模式对比

| 对比项 | 模式 A（宿主机 VPN） | 模式 B（容器 VPN） |
|--------|---------------------|-------------------|
| 稳定性 | 高（推荐） | 中 |
| 宿主机需装 WireGuard | 是 | 否 |
| TUN 设备冲突风险 | 无 | 有 |
| 网络调试方便性 | 高（直接用 wg 命令） | 中（需进容器） |
| 开机自启 | systemctl 管理 | docker restart 策略 |

---

## 附录 B：文件清单

部署完成后，`/opt/opsflow-probe/` 目录应包含：

```
/opt/opsflow-probe/
├── docker-compose.yml   # Docker Compose 编排
├── Dockerfile           # 镜像构建文件
├── agent.py             # 探针 Agent 程序（约 225 行，不能为空）
├── entrypoint.sh        # 容器启动脚本
├── .env                 # 探针环境变量（含 PROBE_KEY，不要泄露）
├── wg0.conf             # WireGuard VPN 配置（含私钥，权限 600）
└── README.md            # 简要说明
```

模式 A 还会在 `/etc/wireguard/wg0.conf` 有一份 VPN 配置。

---

## 附录 C：手动补全 agent.py

如果下载的配置包里 `agent.py` 是空文件（已知 bug），可以从项目源码手动复制：

```bash
# 在中心服务器执行，把 agent.py 传到探针服务器
scp /opt/ops-platform/backend/app/probe/agent.py root@10.99.0.3:/opt/opsflow-probe/agent.py

# 或者在探针服务器上确认文件非空
wc -l /opt/opsflow-probe/agent.py
# 应输出 225 左右，如果输出 0 则需要补全
```

补全后重启探针：

```bash
cd /opt/opsflow-probe
docker compose down
docker compose up -d --build
```

---

## 附录 D：信息中心侧配置（仅管理员）

### D.1 中心服务器 NAT 端口转发

如果中心服务器在 NAT 后面（内网 IP），必须在网关/防火墙上配置端口转发：

```
公网 IP:51820/UDP  →  中心服务器内网 IP:51820/UDP
```

**这是探针能否连通的前提**。如果只转发 TCP 不转发 UDP，ping 能通但 WireGuard 握手包到不了服务器。

验证方法（在中心服务器抓包）：

```bash
tcpdump -i any udp port 51820 -n
# 然后在分公司探针重启 WireGuard，应看到握手包
```

### D.2 生成探针配置

1. 在"组织管理"页面创建组织（填写名称和编码）
2. 点击"生成探针"按钮，系统会自动：
   - 生成 PROBE_KEY
   - 生成 WireGuard 密钥对
   - 分配隧道 IP（10.99.0.2 起）
   - 注册到中心服务器的 WireGuard
3. 点击"下载配置"，得到 zip 包，发给分公司

### D.3 验证中心服务器 WireGuard

```bash
# 查看所有 peer
wg show

# 确认 peer 的 allowed-ips 正确（应为 10.99.0.x/32）
# 确认有 handshake 和 transfer 数据

# 如果 peer 的 allowed-ips 为空，说明注册失败
# 重新点击"重置探针密钥"
```

---

## 联系方式

如有问题无法解决，请联系信息中心管理员。
请提供以下信息以便排查：

1. `docker compose logs` 的最后 30 行输出
2. `wg show` 的输出
3. `cat /opt/opsflow-probe/.env` 的输出（**隐藏 PROBE_KEY**）
4. `uname -r` 和 `docker --version` 的输出
5. `wc -l /opt/opsflow-probe/agent.py` 的输出
