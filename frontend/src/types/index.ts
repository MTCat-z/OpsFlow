// ═══ 通用类型 ═══

export interface User {
  username: string
  role: 'admin' | 'user'
  must_change_password?: boolean
}

export interface LoginResponse {
  access_token: string
  username: string
  role: string
  must_change_password: boolean
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
}

export interface PaginatedParams {
  page?: number
  size?: number
  keyword?: string
}

// ═══ 资产类型 ═══

export type DeviceType = 'server' | 'switch' | 'router' | 'firewall' | 'other'
export type AuthType = 'password' | 'key'
export type Protocol = 'ssh' | 'telnet'

export interface Asset {
  id: number
  name: string
  ip_address: string
  device_type: DeviceType
  location: string
  owner: string
  username: string
  protocol: Protocol
  ssh_port: number
  auth_type: AuthType
  status: 'active' | 'inactive'
}

export interface AssetForm {
  name: string
  ip_address: string
  device_type: DeviceType
  location: string
  owner: string
  username: string
  password: string
  protocol: Protocol
  ssh_port: number
  auth_type: AuthType
  ssh_private_key: string
}

// ═══ 宽带合同 ═══

export type BroadbandStatus = 'active' | 'expired' | 'cancelled'
export type RenewalCycle = 'monthly' | 'quarterly' | 'semi_annual' | 'annual'

export interface Broadband {
  id: number
  account: string
  provider: string
  bandwidth: string
  status: BroadbandStatus
  expire_date: string
  renewal_cycle: RenewalCycle
  monthly_cost: number | null
  annual_cost: number | null
  reminder_days: number[]
  remark: string
}

// ═══ 任务状态 ═══

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface StatusConfig {
  label: string
  type: '' | 'success' | 'warning' | 'info' | 'danger'
}

export type StatusMap = Record<string, StatusConfig>
