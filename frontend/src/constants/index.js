// ═══ 设备类型 ═══
export const DEVICE_TYPES = [
  { label: '服务器', value: 'server' },
  { label: '交换机', value: 'switch' },
  { label: '路由器', value: 'router' },
  { label: '防火墙', value: 'firewall' },
  { label: '其他', value: 'other' },
]

// ═══ 通用任务状态（Scan / Iperf / Topology 共用） ═══
export const TASK_STATUS_MAP = {
  pending: { label: '等待中', type: 'info' },
  running: { label: '运行中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  failed: { label: '失败', type: 'danger' },
}

// 扫描任务专用（running 显示"扫描中"）
export const SCAN_STATUS_MAP = {
  ...TASK_STATUS_MAP,
  running: { label: '扫描中', type: 'warning' },
}

// Iperf 任务专用（running 显示"测速中"）
export const IPERF_STATUS_MAP = {
  ...TASK_STATUS_MAP,
  running: { label: '测速中', type: 'warning' },
}

// ═══ 宽带合同状态 ═══
export const BROADBAND_STATUS_MAP = {
  active: { label: '在用', type: 'success' },
  expired: { label: '已过期', type: 'danger' },
  cancelled: { label: '已取消', type: 'info' },
}

// ═══ 续费周期 ═══
export const RENEWAL_CYCLE_MAP = {
  monthly: { label: '每月', months: 1, tagType: 'warning' },
  quarterly: { label: '每季度', months: 3, tagType: 'primary' },
  semi_annual: { label: '每半年', months: 6, tagType: 'success' },
  annual: { label: '每年', months: 12, tagType: '' },
}

// ═══ 审计日志 ═══
export const AUDIT_ACTION_MAP = {
  login: '登录',
  logout: '登出',
  create: '创建',
  update: '修改',
  delete: '删除',
}

export const AUDIT_ACTION_TYPE_MAP = {
  login: 'success',
  logout: 'info',
  create: '',
  update: 'warning',
  delete: 'danger',
}

export const AUDIT_RESOURCE_MAP = {
  user: '用户',
  asset: '资产',
  scan_task: '扫描任务',
  topology_node: '拓扑节点',
  auth: '认证',
}

// ═══ Zabbix 严重级别 ═══
export const ZABBIX_SEVERITY_MAP = {
  0: '未分类',
  1: '信息',
  2: '警告',
  3: '一般',
  4: '严重',
  5: '灾难',
}

export const ZABBIX_SEVERITY_TYPE_MAP = {
  0: 'info',
  1: 'info',
  2: 'warning',
  3: 'warning',
  4: 'danger',
  5: 'danger',
}

// ═══ 拓扑节点颜色 ═══
export const TOPOLOGY_NODE_COLORS = {
  router: '#f56c6c',
  switch: '#e6a23c',
  server: '#409eff',
  firewall: '#909399',
  ap: '#67c23a',
  endpoint: '#909399',
  unknown: '#c0c4cc',
}
