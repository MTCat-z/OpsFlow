# Checklist

## 宽带续费告警对齐
- [ ] 后端存在共用 `get_next_renewal(contract)` 函数，返回 `(next_deadline, days_remaining, deadline_type)`
- [ ] `broadband_tasks._process_contract` 改用新函数，定时推送行为无回归
- [ ] `broadband_dashboard` 返回 `expiring_renewal_30d` / `expiring_renewal_7d`，按续费截止日计算
- [ ] `test_notify` 的 `days_remaining` / `renewal_deadline` / `deadline_type` 按最近续费截止日
- [ ] 合同列表/详情响应包含 `next_renewal_deadline` / `next_renewal_days` / `deadline_type`
- [ ] `BroadbandPage` "剩余"列按 `next_renewal_days` 显示
- [ ] `BroadbandPage` 新增"下次续费日"列，含 `deadline_type` 标签
- [ ] `BroadbandPage` StatCards "30 天内到期"改用 `expiring_renewal_30d`
- [ ] `DashboardPage` 宽带到期倒计时与 30 天统计按续费截止日
- [ ] 后端 `dashboard.py` overview 返回续费周期字段

## 全站 UI 优化
- [ ] `tokens.css` 主色为 `#2563EB`，侧栏深色为 `#0F172A`
- [ ] `tokens.css` 包含完整亮/暗双套 token
- [ ] 字体栈为 Fira Sans + Fira Code，Google Fonts 已引入
- [ ] Element Plus 主题变量（`--el-color-primary` 等）覆盖为新 token
- [ ] 暗色模式下 Element Plus 组件变量同步覆盖
- [ ] `useTheme` composable 存在，读写 `localStorage` + 设置根 `data-theme`
- [ ] `Layout.vue` 顶栏有主题切换按钮
- [ ] 首屏加载无暗色闪烁（主题在挂载前恢复）
- [ ] `Layout.vue` 侧栏/顶栏无硬编码颜色
- [ ] 全站 14 个页面 `<style>` 中无裸 `#xxxxxx` 硬编码颜色
- [ ] `StatCards` / `StatusTag` / `OutputBlock` 公共组件走 token
- [ ] `LoginPage.vue` 视觉已升级
- [ ] 数字/带宽/终端场景应用 Fira Code 等宽字体

## 验证与部署
- [ ] `npm run lint` 通过
- [ ] `npm run build` 通过
- [ ] 宽带列表剩余天数与下次续费日正确（月度/季度/年度各验证一例）
- [ ] 测试通知钉钉消息与定时推送内容一致（均按续费截止日）
- [ ] 暗色模式切换正常，刷新后保持
- [ ] 本地已 commit + push 到 GitHub
- [ ] 服务器 `git pull` + `upgrade.sh` 成功
- [ ] `http://192.168.40.183` 可访问且 UI 正常

## UI/UX 质量门（来自 ui-ux-pro-max）
- [ ] 无 emoji 用作图标（用 Element Plus Icons SVG）
- [ ] 可点击元素有 `cursor-pointer`
- [ ] Hover 状态有 150-300ms 过渡
- [ ] 浅色模式正文对比度 ≥ 4.5:1
- [ ] 键盘焦点可见（`:focus-visible`）
- [ ] `prefers-reduced-motion` 已尊重
- [ ] 375/768/1024/1440px 断点无横向滚动
