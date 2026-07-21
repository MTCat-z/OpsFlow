# Tasks

## A. 宽带续费告警对齐（按续费周期）

- [x] Task 1: 提取续费截止日计算共用函数
  - [x] SubTask 1.1: 新建 `backend/app/services/broadband_renewal.py` 导出 `get_renewal_deadlines` + `get_next_renewal`
  - [x] SubTask 1.2: `broadband_tasks._process_contract` 改用新函数，行为不变

- [x] Task 2: 后端 `broadband_dashboard` 按续费周期统计
  - [x] SubTask 2.1: 用 `get_next_renewal` 计算 `expiring_renewal_30d` / `expiring_renewal_7d`
  - [x] SubTask 2.2: 保留旧 `expiring_30d` / `expiring_7d` 兼容

- [x] Task 3: 后端 `test_notify` 按续费周期
  - [x] SubTask 3.1: 用 `get_next_renewal` 算 `days_remaining` / `renewal_deadline` / `deadline_type`
  - [x] SubTask 3.2: 传给 `send_renewal_reminder`，与定时任务参数对齐

- [x] Task 4: 后端列表/详情返回续费计算字段
  - [x] SubTask 4.1: 列表/详情追加 `next_renewal_deadline` / `next_renewal_days` / `deadline_type`

- [x] Task 5: 前端 `BroadbandPage` 按续费周期显示
  - [x] SubTask 5.1: "剩余"列改用 `row.next_renewal_days`
  - [x] SubTask 5.2: 新增"下次续费日"列，含 `deadline_type` 标签
  - [x] SubTask 5.3: StatCards "30 天内到期"改用 `expiring_renewal_30d`

- [x] Task 6: 前端 Dashboard 按续费周期
  - [x] SubTask 6.1: 倒计时列表与 30 天统计改用续费截止日字段
  - [x] SubTask 6.2: 后端 `dashboard.py` 返回 `expiring_renewal_30d` / `expiring_renewal_list`

## B. 全站 UI 优化（保留 Element Plus + 重做设计系统）

- [x] Task 7: 重做 `tokens.css` 设计系统
  - [x] SubTask 7.1: 新主色 `#2563EB` + 深色侧栏 `#0F172A`，亮/暗双套 token
  - [x] SubTask 7.2: 字体栈 Fira Sans + Fira Code
  - [x] SubTask 7.3: 紧凑密度间距表

- [x] Task 8: 定制 Element Plus 主题
  - [x] SubTask 8.1: `global.css` 覆盖 `--el-color-primary` 等
  - [x] SubTask 8.2: 暗色模式下 EP 变量同步覆盖

- [x] Task 9: 暗色模式切换
  - [x] SubTask 9.1: 新建 `useTheme` composable
  - [x] SubTask 9.2: `Layout.vue` 顶栏切换按钮，首屏无闪烁

- [x] Task 10: 重做 `Layout.vue`
  - [x] SubTask 10.1: 侧栏用 `var(--ops-sidebar-bg)`，logo 升级
  - [x] SubTask 10.2: 顶栏 token 化，加主题切换按钮
  - [x] SubTask 10.3: 响应式断点复核

- [x] Task 11: 全站 14 个页面移除硬编码颜色
  - [x] SubTask 11.1: 16 个页面 `<style>`/inline 中 `#xxxxxx` 替换为 token
  - [x] SubTask 11.2: 公共组件检查（无硬编码）
  - [x] SubTask 11.3: `LoginPage.vue` 视觉升级

- [x] Task 12: 字体落地
  - [x] SubTask 12.1: `index.html` 引入 Google Fonts
  - [x] SubTask 12.2: `.ops-num` / `.ops-output-block` 用 mono 字体

## C. 验证与部署

- [ ] Task 13: 前端验证
  - [ ] SubTask 13.1: `npm run lint` 通过
  - [ ] SubTask 13.2: `npm run build` 通过
  - [ ] SubTask 13.3: 手动验证宽带列表/Dashboard/暗色切换

- [ ] Task 14: 后端验证
  - [ ] SubTask 14.1: 宽带 dashboard/test_notify 接口返回新字段且按续费周期
  - [ ] SubTask 14.2: 定时任务行为无回归

- [ ] Task 15: 部署
  - [ ] SubTask 15.1: 本地 commit + push 到 GitHub
  - [ ] SubTask 15.2: 服务器 `git pull` + `upgrade.sh` 重新构建
  - [ ] SubTask 15.3: 访问 `http://192.168.40.183` 验证

# Task Dependencies
- Task 2/3/4 依赖 Task 1
- Task 5/6 依赖 Task 4（前端用后端新字段）
- Task 8 依赖 Task 7
- Task 9 依赖 Task 7
- Task 10 依赖 Task 7/8/9
- Task 11 依赖 Task 7/8（页面用新 token）
- Task 13/14 依赖 Task 5/6/11/12
- Task 15 依赖 Task 13/14
- Task A 组（1-6）与 Task B 组（7-12）相互独立，可并行
