import request from './request'

// 认证
export const authApi = {
  login: (d) => {
    const form = new URLSearchParams()
    form.append('username', d.username)
    form.append('password', d.password)
    return request.post('/auth/login', form)
  },
  changePassword: (d) => request.post('/auth/change-password', d),
}

// 用户管理（管理员）
export const userApi = {
  list: (p) => request.get('/users', { params: p }),
  create: (d) => request.post('/users', d),
  update: (id, d) => request.put('/users/' + id, d),
  resetPassword: (id, d) => request.post('/users/' + id + '/reset-password', d),
  delete: (id) => request.delete('/users/' + id),
}

// 审计日志（管理员）
export const auditApi = {
  list: (p) => request.get('/audit', { params: p }),
}

export const assetApi = {
  list: (p) => request.get('/assets', { params: p }),
  get: (id) => request.get('/assets/' + id),
  create: (d) => request.post('/assets', d),
  update: (id, d) => request.put('/assets/' + id, d),
  delete: (id) => request.delete('/assets/' + id),
  getCredentials: (id) => request.get('/assets/' + id + '/credentials'),
  export: () => window.open('/api/v1/assets/export/excel', '_blank'),
}
export const scanApi = {
  start: (d) => request.post('/scan/start', d),
  list: (p) => request.get('/scan/tasks', { params: p }),
  get: (id) => request.get('/scan/tasks/' + id),
  delete: (id) => request.delete('/scan/tasks/' + id),
}
export const iperfApi = {
  start: (d) => request.post('/iperf/start', d),
  list: (p) => request.get('/iperf/tasks', { params: p }),
  get: (id) => request.get('/iperf/tasks/' + id),
  delete: (id) => request.delete('/iperf/tasks/' + id),
  targets: () => request.get('/probes/targets'),
}

// 网络诊断
export const diagApi = {
  ping: (d) => request.post('/diagnostics/ping', d),
  traceroute: (d) => request.post('/diagnostics/traceroute', d),
  dns: (d) => request.post('/diagnostics/dns', d),
  port: (d) => request.post('/diagnostics/port', d),
  mtr: (d) => request.post('/diagnostics/mtr', d),
}

// 宽带合同管理
export const broadbandApi = {
  list: (p) => request.get('/broadband', { params: p }),
  get: (id) => request.get('/broadband/' + id),
  create: (d) => request.post('/broadband', d),
  update: (id, d) => request.put('/broadband/' + id, d),
  delete: (id) => request.delete('/broadband/' + id),
  dashboard: () => request.get('/broadband/dashboard'),
  testNotify: (id) => request.post('/broadband/' + id + '/test-notify'),
  markRenewed: (id) => request.post('/broadband/' + id + '/mark-renewed'),
  // 导入导出
  downloadTemplate: () => request.get('/broadband/export/template', { responseType: 'blob' }),
  exportExcel: (params) => request.get('/broadband/export/excel', { params, responseType: 'blob' }),
  importExcel: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request.post('/broadband/import/excel', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

// 组织管理
export const organizationApi = {
  list: (p) => request.get('/organizations', { params: p }),
  create: (d) => request.post('/organizations', d),
  update: (id, d) => request.put('/organizations/' + id, d),
  delete: (id) => request.delete('/organizations/' + id),
  all: () => request.get('/organizations/all'),
  generateProbe: (id) => request.post('/organizations/' + id + '/generate-probe'),
  resetProbe: (id) => request.post('/organizations/' + id + '/reset-probe'),
  clearProbe: (id) => request.post('/organizations/' + id + '/clear-probe'),
  downloadProbeConfig: (id) => request.get('/organizations/' + id + '/probe-config', { responseType: 'blob' }),
}

// 网络拓扑
export const topologyApi = {
  getGraph: (p) => request.get('/topology/graph', { params: p }),
  discover: (d) => request.post('/topology/discover', d),
  getDiscoveryTask: (id) => request.get('/topology/discover/tasks/' + id),
  listDiscoveryTasks: (p) => request.get('/topology/discover/tasks', { params: p }),
  deleteDiscoveryTask: (id) => request.delete('/topology/discover/tasks/' + id),
  addNode: (d) => request.post('/topology/nodes', d),
  updateNode: (id, d) => request.put('/topology/nodes/' + id, d),
  updateNodePosition: (id, d) => request.patch('/topology/nodes/' + id + '/position', d),
  deleteNode: (id) => request.delete('/topology/nodes/' + id),
  addEdge: (d) => request.post('/topology/edges', d),
  deleteEdge: (id) => request.delete('/topology/edges/' + id),
  importNode: (id, d) => request.post('/topology/import/' + id, d),
  importBatch: (d) => request.post('/topology/import/batch', d),
}

// Zabbix 监控
export const zabbixApi = {
  status: () => request.get('/zabbix/status'),
  hosts: (p) => request.get('/zabbix/hosts', { params: p }),
  hostDetail: (id) => request.get('/zabbix/hosts/' + id),
  hostMetrics: (id, p) => request.get('/zabbix/hosts/' + id + '/metrics', { params: p }),
  problems: (p) => request.get('/zabbix/problems', { params: p }),
  events: (p) => request.get('/zabbix/events', { params: p }),
  triggers: (p) => request.get('/zabbix/triggers', { params: p }),
  dashboard: () => request.get('/zabbix/dashboard'),
  clearCache: () => request.post('/zabbix/cache/clear'),
}

export const dashboardApi = {
  overview: () => request.get('/dashboard/overview'),
}

export const inspectionApi = {
  dashboard: () => request.get('/inspection/dashboard'),
  listPlans: (p) => request.get('/inspection/plans', { params: p }),
  createPlan: (d) => request.post('/inspection/plans', d),
  updatePlan: (id, d) => request.put('/inspection/plans/' + id, d),
  deletePlan: (id) => request.delete('/inspection/plans/' + id),
  runPlan: (id) => request.post('/inspection/plans/' + id + '/run'),
  listRuns: (p) => request.get('/inspection/runs', { params: p }),
  getRun: (id) => request.get('/inspection/runs/' + id),
}

export const configBackupApi = {
  dashboard: () => request.get('/config-backup/dashboard'),
  listJobs: (p) => request.get('/config-backup/jobs', { params: p }),
  createJob: (d) => request.post('/config-backup/jobs', d),
  updateJob: (id, d) => request.put('/config-backup/jobs/' + id, d),
  deleteJob: (id) => request.delete('/config-backup/jobs/' + id),
  runJob: (id) => request.post('/config-backup/jobs/' + id + '/run'),
  listSnapshots: (p) => request.get('/config-backup/snapshots', { params: p }),
  getSnapshot: (id) => request.get('/config-backup/snapshots/' + id),
  getDiff: (id) => request.get('/config-backup/snapshots/' + id + '/diff'),
}

export const commandApi = {
  dashboard: () => request.get('/commands/dashboard'),
  listBatches: (p) => request.get('/commands/batches', { params: p }),
  createBatch: (d) => request.post('/commands/batches', d),
  updateBatch: (id, d) => request.put('/commands/batches/' + id, d),
  getBatch: (id) => request.get('/commands/batches/' + id),
  deleteBatch: (id) => request.delete('/commands/batches/' + id),
  executeBatch: (id) => request.post('/commands/batches/' + id + '/execute'),
  listResults: (id) => request.get('/commands/batches/' + id + '/results'),
}

export const ipamApi = {
  dashboard: () => request.get('/ipam/dashboard'),
  listSubnets: (p) => request.get('/ipam/subnets', { params: p }),
  createSubnet: (d) => request.post('/ipam/subnets', d),
  updateSubnet: (id, d) => request.put('/ipam/subnets/' + id, d),
  deleteSubnet: (id) => request.delete('/ipam/subnets/' + id),
  discoverSubnet: (id) => request.post('/ipam/subnets/' + id + '/discover'),
  listAddresses: (p) => request.get('/ipam/addresses', { params: p }),
  createAddress: (d) => request.post('/ipam/addresses', d),
  updateAddress: (id, d) => request.put('/ipam/addresses/' + id, d),
  deleteAddress: (id) => request.delete('/ipam/addresses/' + id),
  listConflicts: () => request.get('/ipam/conflicts'),
}
