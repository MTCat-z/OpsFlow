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
  // 导入导出
  downloadTemplate: () => request.get('/broadband/export/template', { responseType: 'blob' }),
  importExcel: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request.post('/broadband/import/excel', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
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
