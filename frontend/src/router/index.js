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
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/dashboard/DashboardPage.vue'), meta: { title: '运维数据大屏' } },
      { path: 'assets', name: 'Assets', component: () => import('@/views/assets/AssetList.vue'), meta: { title: '资产管理' } },
      { path: 'scan', name: 'Scan', component: () => import('@/views/scan/ScanPage.vue'), meta: { title: 'Nmap 扫描' } },
      { path: 'iperf', name: 'Iperf', component: () => import('@/views/iperf/IperfPage.vue'), meta: { title: '性能测试' } },
      { path: 'broadband', name: 'Broadband', component: () => import('@/views/broadband/BroadbandPage.vue'), meta: { title: '宽带管理' } },
      { path: 'topology', name: 'Topology', component: () => import('@/views/topology/TopologyPage.vue'), meta: { title: '网络拓扑' } },
      { path: 'diagnostics', name: 'Diagnostics', component: () => import('@/views/diagnostics/DiagnosticsPage.vue'), meta: { title: '网络诊断' } },
      { path: 'zabbix', name: 'Zabbix', component: () => import('@/views/zabbix/ZabbixDashboard.vue'), meta: { title: 'Zabbix 监控' } },
      { path: 'zabbix/hosts', name: 'ZabbixHosts', component: () => import('@/views/zabbix/ZabbixHosts.vue'), meta: { title: 'Zabbix 主机' } },
      { path: 'zabbix/hosts/:id', name: 'ZabbixHostDetail', component: () => import('@/views/zabbix/ZabbixHostDetail.vue'), meta: { title: 'Zabbix 主机详情' } },
      { path: 'inspection', name: 'Inspection', component: () => import('@/views/inspection/InspectionPage.vue'), meta: { title: '自动化巡检' } },
      { path: 'config-backup', name: 'ConfigBackup', component: () => import('@/views/config-backup/ConfigBackupPage.vue'), meta: { title: '配置备份' } },
      { path: 'commands', name: 'Commands', component: () => import('@/views/commands/CommandBatchPage.vue'), meta: { title: '批量命令执行' } },
      { path: 'ipam', name: 'Ipam', component: () => import('@/views/ipam/IpamPage.vue'), meta: { title: 'IPAM' } },
      { path: 'users', name: 'Users', component: () => import('@/views/users/UserManagePage.vue'), meta: { title: '用户管理', admin: true } },
      { path: 'organizations', name: 'Organizations', component: () => import('@/views/organizations/OrganizationList.vue'), meta: { title: '组织管理', admin: true } },
      { path: 'probes', name: 'ProbeStatus', component: () => import('@/views/probes/ProbeStatus.vue'), meta: { title: '探针状态', admin: true } },
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

function getUserFromStorage() {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    return null
  }
}

router.beforeEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - OpsFlow` : 'OpsFlow'

  const token = localStorage.getItem('token')
  const user = getUserFromStorage()

  if (to.meta.public) return true
  if (!token) return { name: 'Login', query: { redirect: to.fullPath } }
  if (to.meta.admin && user?.role !== 'admin') return { path: '/dashboard' }
  return true
})

export default router
