<template>
  <div class="module-page">
    <el-row :gutter="12" class="stats-row">
      <el-col :xs="12" :md="6"><el-statistic title="IPAM 子网" :value="stats.subnets || 0" /></el-col>
      <el-col :xs="12" :md="6"><el-statistic title="DHCP 子网" :value="stats.dhcp_subnets || 0" /></el-col>
      <el-col :xs="12" :md="6"><el-statistic title="地址记录" :value="stats.addresses || 0" /></el-col>
      <el-col :xs="12" :md="6"><el-statistic title="冲突地址" :value="stats.conflicts || 0" /></el-col>
    </el-row>

    <el-tabs v-model="activeTab" type="border-card" @tab-change="onTabChange">
      <!-- 子网管理 -->
      <el-tab-pane label="子网登记" name="subnets">
        <el-row justify="end" style="margin-bottom: 12px">
          <el-button type="primary" @click="openSubnetDialog()">新增子网</el-button>
        </el-row>
        <el-table v-loading="subnetLoading" :data="subnets" border stripe>
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column prop="cidr" label="CIDR" width="160" />
          <el-table-column prop="gateway" label="网关" width="140" />
          <el-table-column prop="vlan" label="VLAN" width="100" />
          <el-table-column prop="dhcp_enabled" label="DHCP" width="90">
            <template #default="{ row }">
              <el-tag :type="row.dhcp_enabled ? 'success' : 'info'" size="small">{{ row.dhcp_enabled ? '启用' : '关闭' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="notes" label="备注" min-width="120" show-overflow-tooltip />
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="success" :loading="row._discovering" @click="discover(row)">发现</el-button>
              <el-button size="small" type="primary" @click="openSubnetDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteSubnet(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 地址列表 -->
      <el-tab-pane label="地址列表" name="addresses">
        <el-form :model="addrQuery" inline style="margin-bottom: 12px">
          <el-form-item>
            <el-select v-model="addrQuery.subnet_id" clearable placeholder="选择子网" style="width: 180px" @change="loadAddresses">
              <el-option v-for="s in subnets" :key="s.id" :label="s.name + ' (' + s.cidr + ')'" :value="s.id" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-select v-model="addrQuery.status" clearable placeholder="状态" style="width: 120px" @change="loadAddresses">
              <el-option label="使用中" value="used" />
              <el-option label="空闲" value="free" />
              <el-option label="冲突" value="conflict" />
              <el-option label="保留" value="reserved" />
              <el-option label="离线" value="offline" />
            </el-select>
          </el-form-item>
          <el-form-item><el-input v-model="addrQuery.keyword" placeholder="IP/MAC/主机名" clearable style="width: 180px" @clear="loadAddresses" @keyup.enter="loadAddresses" /></el-form-item>
          <el-form-item><el-button type="primary" @click="loadAddresses">搜索</el-button></el-form-item>
        </el-form>
        <el-table v-loading="addrLoading" :data="addresses" border stripe>
          <el-table-column prop="ip_address" label="IP 地址" width="150" />
          <el-table-column prop="mac_address" label="MAC 地址" width="160" />
          <el-table-column prop="hostname" label="主机名" min-width="140" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="source" label="来源" width="80" />
          <el-table-column prop="last_seen_at" label="最后发现" width="170">
            <template #default="{ row }">{{ row.last_seen_at ? row.last_seen_at.replace('T', ' ').slice(0, 19) : '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="danger" @click="deleteAddress(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination v-model:current-page="addrQuery.page" style="margin-top: 16px; justify-content: flex-end" background layout="prev,pager,next,total" :total="addrTotal" :page-size="addrQuery.size" @current-change="loadAddresses" />
      </el-tab-pane>

      <!-- 冲突地址 -->
      <el-tab-pane label="冲突地址" name="conflicts">
        <el-table v-loading="conflictLoading" :data="conflicts" border stripe>
          <el-table-column prop="ip_address" label="IP 地址" width="150" />
          <el-table-column prop="mac_address" label="MAC 地址" width="180" />
          <el-table-column prop="hostname" label="主机名" min-width="140" show-overflow-tooltip />
          <el-table-column prop="last_seen_at" label="最后发现" width="170">
            <template #default="{ row }">{{ row.last_seen_at ? row.last_seen_at.replace('T', ' ').slice(0, 19) : '-' }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 子网编辑对话框 -->
    <el-dialog v-model="subnetDialogVisible" :title="subnetForm.id ? '编辑子网' : '新增子网'" width="500px">
      <el-form :model="subnetForm" label-width="90px">
        <el-form-item label="名称"><el-input v-model="subnetForm.name" /></el-form-item>
        <el-form-item label="CIDR"><el-input v-model="subnetForm.cidr" placeholder="192.168.1.0/24" /></el-form-item>
        <el-form-item label="网关"><el-input v-model="subnetForm.gateway" placeholder="192.168.1.1" /></el-form-item>
        <el-form-item label="VLAN"><el-input v-model="subnetForm.vlan" placeholder="VLAN 10" /></el-form-item>
        <el-form-item label="DHCP"><el-switch v-model="subnetForm.dhcp_enabled" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="subnetForm.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="subnetDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSubnet">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ipamApi } from '@/api'

const stats = ref({})
const activeTab = ref('subnets')
const subnets = ref([])
const subnetLoading = ref(false)
const addresses = ref([])
const addrLoading = ref(false)
const addrTotal = ref(0)
const conflicts = ref([])
const conflictLoading = ref(false)

const addrQuery = reactive({ page: 1, size: 20, subnet_id: null, status: null, keyword: '' })

const subnetDialogVisible = ref(false)
const subnetForm = reactive({ id: null, name: '', cidr: '', gateway: '', vlan: '', dhcp_enabled: true, notes: '' })

function statusType(s) {
  return { used: 'success', free: 'info', conflict: 'danger', reserved: '', offline: 'warning' }[s] || 'info'
}
function statusLabel(s) {
  return { used: '使用中', free: '空闲', conflict: '冲突', reserved: '保留', offline: '离线' }[s] || s
}

async function loadStats() { stats.value = await ipamApi.dashboard() }

async function loadSubnets() {
  subnetLoading.value = true
  try {
    const res = await ipamApi.listSubnets({ size: 100 })
    subnets.value = res.items || []
  } finally { subnetLoading.value = false }
}

async function loadAddresses() {
  addrLoading.value = true
  try {
    const params = { page: addrQuery.page, size: addrQuery.size }
    if (addrQuery.subnet_id) params.subnet_id = addrQuery.subnet_id
    if (addrQuery.status) params.status = addrQuery.status
    if (addrQuery.keyword) params.keyword = addrQuery.keyword
    const res = await ipamApi.listAddresses(params)
    addresses.value = res.items || []
    addrTotal.value = res.total || 0
  } finally { addrLoading.value = false }
}

async function loadConflicts() {
  conflictLoading.value = true
  try {
    const res = await ipamApi.listConflicts()
    conflicts.value = res.items || []
  } finally { conflictLoading.value = false }
}

function onTabChange(tab) {
  if (tab === 'addresses') loadAddresses()
  if (tab === 'conflicts') loadConflicts()
}

function openSubnetDialog(row) {
  if (row) {
    Object.assign(subnetForm, { id: row.id, name: row.name, cidr: row.cidr, gateway: row.gateway || '', vlan: row.vlan || '', dhcp_enabled: row.dhcp_enabled, notes: row.notes || '' })
  } else {
    Object.assign(subnetForm, { id: null, name: '', cidr: '', gateway: '', vlan: '', dhcp_enabled: true, notes: '' })
  }
  subnetDialogVisible.value = true
}

async function saveSubnet() {
  if (subnetForm.id) {
    await ipamApi.updateSubnet(subnetForm.id, subnetForm)
    ElMessage.success('子网已更新')
  } else {
    await ipamApi.createSubnet(subnetForm)
    ElMessage.success('子网已创建')
  }
  subnetDialogVisible.value = false
  loadSubnets()
  loadStats()
}

async function deleteSubnet(row) {
  await ElMessageBox.confirm(`确认删除子网 "${row.name}"？该子网下所有地址记录将被一并删除。`, '确认删除', { type: 'warning' })
  await ipamApi.deleteSubnet(row.id)
  ElMessage.success('子网已删除')
  loadSubnets()
  loadStats()
}

async function discover(row) {
  row._discovering = true
  try {
    await ipamApi.discoverSubnet(row.id)
    ElMessage.success('IP 发现任务已提交')
  } finally { row._discovering = false }
}

async function deleteAddress(row) {
  await ElMessageBox.confirm(`确认删除地址 ${row.ip_address}？`, '确认删除', { type: 'warning' })
  await ipamApi.deleteAddress(row.id)
  ElMessage.success('地址已删除')
  loadAddresses()
  loadStats()
}

async function loadData() {
  await loadStats()
  await loadSubnets()
}

onMounted(loadData)
</script>
