# OpsFlow 宽带续费告警修正 + 全站 UI 优化 Spec

## Why
1. 宽带管理的"续费周期告警"在用户感知上仍按合同到期日工作：前端表格剩余天数、Dashboard 到期统计、测试通知都用 `contract_end`，只有后端定时任务是按续费周期算的，导致 UI 与实际推送不一致，用户无法判断下一次续费截止日。
2. 当前 UI 是 Element Plus 默认风格，深蓝硬编码侧栏 + 浅色内容区，缺少现代感、品牌感和视觉层次，用户反馈"有点丑"。

## What Changes

### A. 宽带续费告警对齐（按续费周期）
- 后端 `broadband_dashboard` API 的 `expiring_30d` / `expiring_7d` 改为按"最近续费截止日"计算，而非 `contract_end`
- 后端 `test_notify` 接口的 `days_remaining` 改为按当前最近的续费截止日计算，并传 `renewal_deadline` / `deadline_type`，与定时任务一致
- 后端合同列表/详情返回新增 `next_renewal_deadline` / `next_renewal_days` / `deadline_type` 计算字段（不落库，动态计算）
- 前端 `BroadbandPage` 表格"剩余"列改为按 `next_renewal_days` 显示，新增"下次续费日"列
- 前端 Dashboard "宽带到期倒计时" / "30 天内到期"统计改为按续费截止日

### B. 全站 UI 优化（保留 Element Plus + 重做设计系统）
- 重做 `frontend/src/styles/tokens.css`：新主色 `#2563EB`、深色侧栏 `#0F172A`、完整亮/暗双套 token、Fira Sans/Fira Code 字体栈、密度更紧凑的间距表
- 定制 Element Plus 主题（CSS 变量覆盖 `--el-color-primary` 等），让 EP 组件跟随新 token
- 重做 `Layout.vue`：侧栏视觉、顶栏、面包屑、暗色切换按钮、品牌 logo
- 全站 14 个页面移除硬编码颜色（`#001529`/`#f5f7fa`/`#303133` 等），统一走 token
- 新增暗色模式切换：顶栏按钮 + `localStorage` 记忆 + `data-theme="dark"` 根属性
- 引入 Fira Sans/Fira Code（Google Fonts 或本地托管），数字/终端用等宽
- 登录页 `LoginPage.vue` 视觉升级

## Impact
- 受影响代码：
  - 后端：`backend/app/api/v1/broadband.py`、`backend/app/tasks/broadband_tasks.py`（提取共用计算函数）、`backend/app/api/v1/dashboard.py`
  - 前端：`frontend/src/styles/tokens.css`、`frontend/src/styles/global.css`、`frontend/src/views/Layout.vue`、`frontend/src/views/broadband/BroadbandPage.vue`、`frontend/src/views/dashboard/DashboardPage.vue`、`frontend/src/views/LoginPage.vue` 及其余 11 个业务页面、`frontend/src/components/common/*`
- 受影响能力：宽带合同管理、宽带续费告警、运维数据大屏、全站视觉与暗色模式
- 部署：本地修改 -> git push -> 服务器 `git pull` + `upgrade.sh` 重新构建容器
- **BREAKING**：无接口契约破坏（仅新增字段，旧字段保留兼容）；UI 视觉变化较大但功能不变

## ADDED Requirements

### Requirement: 下一次续费截止日计算
系统 SHALL 为每条在用宽带合同动态计算"下一次续费截止日"（`next_renewal_deadline`）、距今天数（`next_renewal_days`）和截止类型（`deadline_type`，值为 `cycle` 或 `contract_end`），复用 `broadband_tasks._get_renewal_deadlines` 逻辑。

#### Scenario: 月度续费合同
- **GIVEN** 一条在用合同，`contract_start=2025-01-01`，`contract_end=2025-12-31`，`renewal_cycle=monthly`，今天为 2025-06-15
- **WHEN** 系统计算下一次续费截止日
- **THEN** `next_renewal_deadline=2025-06-30`，`deadline_type=cycle`

#### Scenario: 已过所有周期截止日
- **GIVEN** 一条在用合同，所有续费截止日均已过去，仅剩 `contract_end` 未到
- **WHEN** 系统计算下一次续费截止日
- **THEN** `next_renewal_deadline=contract_end`，`deadline_type=contract_end`

### Requirement: 暗色模式切换
系统 SHALL 在顶栏提供暗色模式切换按钮，切换时根元素设置 `data-theme="dark"`，偏好持久化到 `localStorage`，并在首次加载时恢复。

#### Scenario: 用户切换暗色模式
- **WHEN** 用户点击顶栏主题切换按钮
- **THEN** 根元素 `data-theme` 在 `light`/`dark` 间切换，所有 token 跟随变化，`localStorage` 记录偏好

#### Scenario: 恢复上次主题
- **WHEN** 用户重新打开页面
- **THEN** 系统读取 `localStorage` 并应用上次主题，无主题记录时默认浅色

### Requirement: 设计系统统一
系统 SHALL 通过 `tokens.css` 定义全站颜色/间距/圆角/阴影/字体 token，所有页面与 Element Plus 主题 SHALL 引用这些 token，禁止在业务页面硬编码十六进制颜色。

#### Scenario: 页面使用 token
- **WHEN** 开发者在新页面或现有页面设置颜色
- **THEN** 使用 `var(--ops-*)` 或 Element Plus 语义类，不出现裸 `#xxxxxx`

## MODIFIED Requirements

### Requirement: 宽带仪表盘统计
`broadband_dashboard` API 的 `expiring_30d` / `expiring_7d` SHALL 按每条合同"最近续费截止日"计算，而非 `contract_end`。返回字段新增 `expiring_renewal_30d` / `expiring_renewal_7d`，旧字段保留但标记为基于合同到期日。

#### Scenario: 30 天内有续费截止
- **GIVEN** 一条月度续费合同，下次续费截止日距今 20 天，合同到期日距今 200 天
- **WHEN** 调用 `/broadband/dashboard`
- **THEN** 该合同计入 `expiring_renewal_30d`，不计入 `expiring_30d`

### Requirement: 宽带测试通知
`test_notify` 接口 SHALL 按当前最近续费截止日计算 `days_remaining`，并传递 `renewal_deadline` / `deadline_type` 给通知服务，使测试通知与定时推送内容一致。

#### Scenario: 测试通知使用续费截止日
- **WHEN** 用户在表格点击"通知"按钮
- **THEN** 钉钉消息中"剩余天数"和"截止日期"为最近续费截止日，而非合同到期日

### Requirement: 宽带列表剩余天数显示
`BroadbandPage` 表格"剩余"列 SHALL 按 `next_renewal_days` 显示，颜色阈值（7/30 天）不变；新增"下次续费日"列展示 `next_renewal_deadline` 与 `deadline_type` 标签。

#### Scenario: 月度合同剩余显示
- **GIVEN** 一条月度续费合同，下次续费截止日距今 5 天
- **WHEN** 用户查看宽带列表
- **THEN** "剩余"列显示 5 天（红色），"下次续费日"列显示该截止日与"周期"标签

### Requirement: Layout 视觉与主题
`Layout.vue` 侧栏 SHALL 使用 `var(--ops-sidebar-bg)`（深色 `#0F172A`），顶栏 SHALL 提供主题切换按钮，所有硬编码颜色 SHALL 替换为 token 引用。

## REMOVED Requirements
无。本次不移除任何功能。
