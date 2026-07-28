# OpsFlow 多场地在线版改造方案

## 概述

将 OpsFlow 从单机单租户内网工具改造为支持多分公司/多场地的在线平台，实现数据隔离、分布式网络探针、统一管理。

## 当前架构分析

| 维度 | 现状 | 改造需求 |
|------|------|----------|
| 数据库 | SQLite 单文件 | 迁移到 PostgreSQL，支持并发多租户 |
| 数据隔离 | 无，所有用户看全量数据 | 增加 Organization 模型，所有业务表加 org_id |
| 认证 | JWT 仅含 user_id + role | JWT 增加 org_id，查询自动按 org 过滤 |
| 权限 | admin/user 二元角色 | 增加 org_admin 角色（场地管理员） |
| 网络工具 | nmap/iperf3 在单台宿主机执行 | 分布式探针，各场地本地执行 |
| 部署 | 单机 Docker Compose | 中心服务器 + 各场地探针 Agent |
| 定时任务 | 单 Celery beat | 中心调度 + 探针本地执行 |

## 改造方案（分 4 期）

---

### 第 1 期：基础设施升级（数据库 + 部署架构）

#### 1.1 SQLite -> PostgreSQL

**文件**：`backend/app/core/database.py`、`backend/app/core/config.py`、`backend/requirements.txt`

- `requirements.txt` 增加 `psycopg2-binary` 或 `asyncpg`
- `config.py` 的 `DATABASE_URL` 默认值改为 PostgreSQL 格式
- `database.py` 的 `connect_args` 按 DB 类型区分（SQLite 保留 `check_same_thread`，PostgreSQL 不需要）
- `_migrate_columns()` 的 SQLite PRAGMA 改为兼容 PostgreSQL（`information_schema.columns` 查询）
- 编写数据迁移脚本：SQLite -> PostgreSQL 的一次性导入

#### 1.2 部署架构拆分

**新增文件**：`deploy/docker-compose.online.yml`

中心服务器部署：
```
PostgreSQL（独立容器或托管）
Redis（独立容器）
FastAPI 后端（可多副本）
Celery Worker + Beat（调度中心）
Nginx（前端 + API 网关）
```

各场地探针部署（轻量）：
```
deploy/docker-compose.probe.yml

Redis（本地队列，可选）
Celery Worker（仅消费 scan/iperf 队列）
nmap + iperf3（宿主机安装）
```

探针注册机制：
- 探针启动时向中心服务器注册（POST /api/v1/probes/register）
- 中心分配 `probe_key`，探针携带 key 拉取任务
- 任务结果通过 API 回传中心

---

### 第 2 期：多租户数据隔离

#### 2.1 Organization 模型

**新增文件**：`backend/app/models/organization.py`

```python
class Organization(SQLModel, table=True):
    id: Optional[int] = primary_key
    name: str                    # 场地名称，如"北京总部"
    code: str = unique           # 场地编码，如"BJ-HQ"
    probe_url: Optional[str]     # 探针地址（如果有）
    probe_key: Optional[str]     # 探鉴权 key
    dingtalk_webhook: Optional[str]  # 场地独立钉钉
    zabbix_url: Optional[str]    # 场地独立 Zabbix
    is_active: bool = True
    created_at: datetime
```

#### 2.2 User 模型扩展

**文件**：`backend/app/models/user.py`

```python
# 新增字段
org_id: Optional[int] = Field(foreign_key="organizations.id")
role: str  # admin(超管) / org_admin(场地管理员) / user(普通用户)
```

角色权限矩阵：
| 角色 | 权限 |
|------|------|
| admin | 全局管理，管理所有组织 |
| org_admin | 管理本组织用户，查看本组织数据 |
| user | 查看操作本组织数据 |

#### 2.3 业务表加 org_id

**影响文件**（所有模型文件）：
- `asset.py` -> Asset 加 `org_id`
- `broadband.py` -> BroadbandContract 加 `org_id`
- `scan_task.py` -> ScanTask 加 `org_id`
- `iperf_task.py` -> IperfTask 加 `org_id`
- `topology.py` -> TopologyNode/Edge 加 `org_id`
- `ipam.py` -> IpamSubnet/Address 加 `org_id`
- `inspection.py` -> InspectionPlan/Run 加 `org_id`
- `config_backup.py` -> ConfigBackupJob/Snapshot 加 `org_id`
- `command.py` -> CommandBatch/Result 加 `org_id`

#### 2.4 查询自动过滤

**文件**：`backend/app/core/auth.py`

新增依赖函数：
```python
def get_current_org(user: User = Depends(get_current_user)) -> int:
    """返回当前用户的 org_id，admin 返回 None（不过滤）"""
    if user.role == "admin":
        return None
    return user.org_id
```

**文件**：所有 `backend/app/api/v1/*.py` 的列表查询

每个 list 接口增加 org 过滤：
```python
@router.get("/assets")
def list_assets(org_id: int = Depends(get_current_org), ...):
    q = select(Asset)
    if org_id is not None:
        q = q.where(Asset.org_id == org_id)
    ...
```

#### 2.5 JWT 扩展

**文件**：`backend/app/core/auth.py`

```python
payload = {
    "sub": str(user.id),
    "username": user.username,
    "role": user.role,
    "org_id": user.org_id,  # 新增
    "must_change_password": user.must_change_password,
    "exp": expire,
}
```

---

### 第 3 期：分布式探针

#### 3.1 探针 Agent

**新增目录**：`backend/app/probe/`

探针是一个轻量 Celery Worker，仅执行网络操作：
- 注册到中心服务器，获取 `probe_key`
- 定期拉取本组织的 scan/iperf 任务
- 本地执行 nmap/iperf3
- 结果通过 API 回传

**新增 API**：`backend/app/api/v1/probes.py`
```
POST   /probes/register        # 探针注册
GET    /probes/{org_id}/tasks  # 拉取待执行任务
POST   /probes/tasks/{id}/result  # 回传结果
GET    /probes/status          # 探针在线状态
```

#### 3.2 任务调度改造

**文件**：`backend/app/tasks/scan_tasks.py`、`iperf_tasks.py`

当前：直接在本地执行 nmap/iperf3
改为：
1. 中心创建任务（状态=pending）
2. 探针拉取任务（状态=running）
3. 探针本地执行
4. 探针回传结果（状态=completed）

#### 3.3 探针部署包

**新增文件**：`deploy/probe/`
```
deploy/probe/
  docker-compose.probe.yml   # 探针 Docker 部署
  Dockerfile.probe            # 探针镜像（Python + nmap + iperf3）
  install.sh                  # 一键安装脚本
  README.md                   # 场地 IT 人员操作指南
```

---

### 第 4 期：前端多组织支持

#### 4.1 组织管理界面

**新增文件**：`frontend/src/views/organizations/OrganizationList.vue`

- admin 可创建/编辑/禁用组织
- 查看各组织探针状态
- 查看各组织用户数和资产数

#### 4.2 路由和权限扩展

**文件**：`frontend/src/router/index.js`

新增路由：
```
/organizations    # 组织管理（仅 admin）
/probes           # 探针状态（admin + org_admin）
```

路由守卫增加 org_admin 角色判断。

#### 4.3 用户管理增强

**文件**：`frontend/src/views/users/UserManagePage.vue`

- 创建用户时选择所属组织
- org_admin 只能管理本组织用户
- 用户列表增加"所属组织"列

#### 4.4 场地切换（admin 专用）

admin 可在顶栏切换查看不同组织的数据：
```
顶栏下拉：[全部] [北京总部] [上海分部] [广州分部]
```

切换后所有页面数据按选中组织过滤。

---

## 实施优先级建议

```
第 1 期（基础设施）  ──> 第 2 期（多租户）  ──> 第 3 期（探针）  ──> 第 4 期（前端）
   1-2 天                3-5 天                2-3 天              2-3 天
```

**最小可用版本（MVP）**：完成第 1+2 期即可上线，各场地共用中心服务器的 nmap/iperf3（远程扫描，精度可能降低）。第 3 期按需逐步部署探针。

## 风险与注意事项

1. **数据迁移**：现有 SQLite 数据需迁移到 PostgreSQL，编写一次性脚本
2. **网络扫描精度**：中心远程扫描各场地内网可能不准确，探针部署前可先通过 SSH 远程执行
3. **安全**：探针 key 需要妥善管理，建议用 HTTPS + IP 白名单
4. **成本**：PostgreSQL 可用云托管（如 RDS），中心服务器需公网 IP 或 VPN 打通
5. **backward compat**：单机版仍需可用，通过配置切换部署模式

## 验证步骤

1. 本地 Docker Compose 启动 PostgreSQL + 后端，验证数据库迁移
2. 创建两个组织 + 各自用户，验证数据隔离
3. 部署一个探针，验证远程任务分发和结果回传
4. 前端切换组织，验证数据过滤
5. 压力测试：多组织并发查询性能
