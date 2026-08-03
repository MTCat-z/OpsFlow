# 安全漏洞修复 Checklist

## H-1 配置备份 IDOR
- [x] `config_backup.update_job` 加入 `current_user` 依赖与 `check_org_access`，越权返回 404
- [x] `config_backup.delete_job` 加入 `current_user` 依赖与 `check_org_access`，越权返回 404
- [x] `config_backup.run_job` 加入 `current_user` 依赖与 `check_org_access`，越权返回 404
- [x] `config_backup.get_snapshot` 加入 `current_user` 依赖与 `check_org_access`，越权返回 404
- [x] `config_backup.get_snapshot_diff` 加入 `current_user` 依赖与 `check_org_access`，越权返回 404
- [x] `run_job` 入口对 `job.command` 调用 `check_dangerous_commands`，命中黑名单返回 400
- [x] `create_job` / `update_job` / `delete_job` / `run_job` 角色依赖改为 `require_org_admin`
- [x] `config_backup_tasks.run_config_backup` 加载资产追加 `Asset.org_id == job.org_id` 过滤

## H-2 批量命令跨租户执行
- [x] `command_tasks.run_command_batch` 过滤掉 `asset.org_id != batch.org_id` 的资产
- [x] `command_guard.DANGEROUS_PATTERNS` 追加 `rm`、`curl`、`wget`、`bash`、`sh`、`python`、`nc`、`/dev/tcp`、`>`、`>>`、`<<`、反引号、`$()` 等高危词
- [x] `commands.create_batch` / `update_batch` / `delete_batch` / `execute_batch` 角色依赖改为 `require_org_admin`

## M-1 资产 Excel 导出泄露
- [x] `assets.export_assets` 加入 `org_id: Optional[int] = Depends(get_current_org)` 依赖
- [x] `export_assets` 在查询时按 org_id 过滤

## M-2 inspection / topology / ipam 所有权校验
- [x] inspection: `get_plan` / `update_plan` / `delete_plan` / `run_plan` / `get_run` 加入 `current_user` + `check_org_access`
- [x] inspection: `run_plan` 限制为 `require_org_admin`
- [x] topology: `update_node` / `update_node_position` / `delete_node` / `create_edge` / `delete_edge` / `get_discovery_task` 加入 `current_user` + `check_org_access`
- [x] topology: `start_discovery` / `delete_discovery_task` / `import_node_to_asset` / `import_batch` 限制为 `require_org_admin`
- [x] ipam: `update_subnet` / `delete_subnet` / `update_address` / `delete_address` 加入 `current_user` + `check_org_access`
- [x] ipam: `discover_subnet` 限制为 `require_org_admin`

## 回归验证
- [x] 跨 org 访问 config-backup 资源返回 404 的单元测试通过
- [x] `command_guard` 新增高危词命中测试通过（13 个危险词命中、4 个安全命令无误报）
- [x] `export_assets` 按 org 过滤测试通过（user 仅本 org，admin 全量）
- [x] inspection / topology / ipam 跨 org 操作返回 404/403 测试通过（20 项端到端）
- [x] 端到端手动验证：用 `user` 角色触发命令执行返回 403（含 config-backup run / command batch execute / inspection run / topology start_discovery / ipam discover_subnet）
