import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginPage.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    redirect: '/assets',
    children: [
      { path: 'assets', name: 'Assets', component: () => import('@/views/assets/AssetList.vue'), meta: { title: '资产管理' } },
      { path: 'scan', name: 'Scan', component: () => import('@/views/scan/ScanPage.vue'), meta: { title: 'Nmap扫描' } },
      { path: 'iperf', name: 'Iperf', component: () => import('@/views/iperf/IperfPage.vue'), meta: { title: '性能测试' } },
      { path: 'broadband', name: 'Broadband', component: () => import('@/views/broadband/BroadbandPage.vue'), meta: { title: '宽带管理' } },
      { path: 'topology', name: 'Topology', component: () => import('@/views/topology/TopologyPage.vue'), meta: { title: '网络拓扑' } },
      { path: 'diagnostics', name: 'Diagnostics', component: () => import('@/views/diagnostics/DiagnosticsPage.vue'), meta: { title: '网络诊断' } },
      { path: 'zabbix', name: 'Zabbix', component: () => import('@/views/zabbix/ZabbixDashboard.vue'), meta: { title: 'Zabbix监控' } },
      { path: 'zabbix/hosts', name: 'ZabbixHosts', component: () => import('@/views/zabbix/ZabbixHosts.vue'), meta: { title: 'Zabbix主机' } },
      { path: 'zabbix/hosts/:id', name: 'ZabbixHostDetail', component: () => import('@/views/zabbix/ZabbixHostDetail.vue'), meta: { title: 'Zabbix主机详情' } },
      { path: 'users', name: 'Users', component: () => import('@/views/users/UserManagePage.vue'), meta: { title: '用户管理', admin: true } },
      { path: 'audit', name: 'Audit', component: () => import('@/views/users/AuditLogPage.vue'), meta: { title: '审计日志', admin: true } },
    ],
  },
  {
    path: '/terminal/:assetId',
    name: 'Terminal',
    component: () => import('@/views/terminal/TerminalPage.vue'),
    meta: { title: '终端' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: '404', public: true },
  },
]

const router = createRouter({ history: createWebHistory(), routes })

// 安全解析 localStorage 中的用户信息
function getUserFromStorage() {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    return null
  }
}

// 全局路由守卫
router.beforeEach((to) => {
  // 设置页面标题
  document.title = to.meta.title ? `${to.meta.title} - OpsFlow` : 'OpsFlow'

  const token = localStorage.getItem('token')
  const user = getUserFromStorage()

  // 公开页面直接放行
  if (to.meta.public) return true

  // 未登录跳转到登录页
  if (!token) return { name: 'Login', query: { redirect: to.fullPath } }

  // 需要管理员权限的页面
  if (to.meta.admin && user?.role !== 'admin') return { path: '/assets' }

  return true
})

export default router
