# Tasks

- [x] Task 1: 修复配置备份 IDOR（H-1）
  - [x] SubTask 1.1: 在 `config_backup.py` 的 `update_job` / `delete_job` / `run_job` / `get_snapshot` / `get_snapshot_diff` 加入 `current_user: User = Depends(get_current_user)` 并调用 `check_org_access(resource, current_user)`，越权返回 404
  - [x] SubTask 1.2: 在 `run_job` 入口对 `job.command` 调用 `check_dangerous_commands`，命中黑名单时返回 400 拒绝触发
  - [x] SubTask 1.3: 将 `create_job` / `update_job` / `delete_job` / `run_job` 的角色依赖从无改为 `require_org_admin`
  - [x] SubTask 1.4: 在 `config_backup_tasks.run_config_backup` 加载资产时，在原有 `Asset.id.in_(ids)` 基础上追加 `Asset.org_id == job.org_id` 过滤

- [x] Task 2: 修复批量命令跨租户执行（H-2）
  - [x] SubTask 2.1: 在 `command_tasks.run_command_batch` 加载资产后，过滤掉 `asset.org_id != batch.org_id` 的资产，并记日志
  - [x] SubTask 2.2: 在 `command_guard.DANGEROUS_PATTERNS` 追加通用 shell 高危词：`\brm\b`、`\bcurl\b`、`\bwget\b`、`\bbash\b`、`\bsh\b`、`\bpython\b`、`\bnc\b`、`/dev/tcp`、重定向 `>`/`>>`/`<<`、反引号、`\$\(` 命令替换
  - [x] SubTask 2.3: 将 `commands.py` 中 `create_batch` / `update_batch` / `delete_batch` / `execute_batch` 的角色依赖改为 `require_org_admin`

- [x] Task 3: 修复资产 Excel 导出泄露（M-1）
  - [x] SubTask 3.1: 在 `assets.export_assets` 加入 `org_id: Optional[int] = Depends(get_current_org)` 依赖
  - [x] SubTask 3.2: 在 `select(Asset)` 后追加 `if org_id is not None: q = q.where(Asset.org_id == org_id)` 过滤

- [x] Task 4: 修复 inspection / topology / ipam 多端点缺失所有权校验（M-2）
  - [x] SubTask 4.1: inspection 模块 — `get_plan` / `update_plan` / `delete_plan` / `run_plan` / `get_run` 加入 `current_user` + `check_org_access`；`run_plan` 限制为 `require_org_admin`
  - [x] SubTask 4.2: topology 模块 — `update_node` / `update_node_position` / `delete_node` / `create_edge` / `delete_edge` / `start_discovery` / `get_discovery_task` / `delete_discovery_task` / `import_node_to_asset` / `import_batch` 加入 `current_user` + `check_org_access`；`start_discovery` / `delete_discovery_task` / `import_*` 限制为 `require_org_admin`
  - [x] SubTask 4.3: ipam 模块 — `update_subnet` / `delete_subnet` / `discover_subnet` / `update_address` / `delete_address` 加入 `current_user` + `check_org_access`；`discover_subnet` 限制为 `require_org_admin`

- [x] Task 5: 回归验证
  - [x] SubTask 5.1: 编写针对每个修复点的单元测试（跨 org 访问返回 404/403、`command_guard` 新增词命中、`export_assets` 过滤生效）
  - [x] SubTask 5.2: 启动后端服务，手动构造跨租户请求验证端到端拦截

# Task Dependencies
- Task 5 依赖 Task 1、2、3、4 全部完成
- Task 1、2、3、4 之间无依赖，可并行
