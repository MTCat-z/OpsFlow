<template>
  <div class="app-container">
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">组织总数</div>
          <div class="stat-value">{{ stats.total }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-online">
          <div class="stat-label">探针在线</div>
          <div class="stat-value">{{ stats.online }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-offline">
          <div class="stat-label">探针离线</div>
          <div class="stat-value">{{ stats.offline }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-unconfigured">
          <div class="stat-label">未配置</div>
          <div class="stat-value">{{ stats.unconfigured }}</div>
        </el-card>
      </el-col>
    </el-row>
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>探针状态列表</span>
          <div>
            <el-input v-model="keyword" placeholder="搜索组织名称/编码" clearable size="small" style="width: 220px; margin-right: 12px" @clear="loadData" @keyup.enter="loadData" />
            <el-button type="primary" size="small" @click="loadData">刷新</el-button>
          </div>
        </div>
      </template>
      <el-table v-loading="loading" stripe border :data="organizations" style="width: 100%">
        <el-table-column prop="name" label="组织名称" min-width="140" />
        <el-table-column prop="code" label="组织编码" width="140" />
        <el-table-column label="探针状态" align="center" width="110">
          <template #default="{ row }">
            <el-tag v-if="!row.probe_key" type="info">未配置</el-tag>
            <el-tag v-else-if="row.probe_online" type="success">在线</el-tag>
            <el-tag v-else type="danger">离线</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后心跳" width="180">
          <template #default="{ row }">
            <span v-if="row.probe_last_heartbeat">{{ formatTime(row.probe_last_heartbeat) }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="隧道 IP" width="140">
          <template #default="{ row }">
            <span v-if="row.wg_tunnel_ip">{{ row.wg_tunnel_ip }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="probe_key" width="220">
          <template #default="{ row }">
            <span v-if="row.probe_key" class="mono">{{ row.probe_key }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" align="center" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" :disabled="!row.probe_key" @click="handleReset(row)">重置密钥</el-button>
            <el-button size="small" type="danger" :disabled="!row.probe_key" @click="handleClear(row)">清理探针</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-dialog v-model="resetDialogVisible" title="探针密钥已重置" width="520px">
      <el-alert type="warning" :closable="false" title="请下载新配置并重新部署该组织的探针，旧配置已失效。" style="margin-bottom: 16px" />
      <el-descriptions :column="1" border>
        <el-descriptions-item label="组织">{{ resetResult.org_code }}</el-descriptions-item>
        <el-descriptions-item label="probe_key"><code class="mono">{{ resetResult.probe_key }}</code></el-descriptions-item>
        <el-descriptions-item label="隧道 IP">{{ resetResult.wg_tunnel_ip }}</el-descriptions-item>
        <el-descriptions-item label="公钥"><code class="mono" style="word-break: break-all">{{ resetResult.wg_public_key }}</code></el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="resetDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="downloadConfig(resetResult.org_id)">下载新配置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { organizationApi } from '@/api'

const organizations = ref([])
const loading = ref(false)
const keyword = ref('')
const resetDialogVisible = ref(false)
const resetResult = ref({})
let timer = null

const stats = computed(() => {
  const total = organizations.value.length
  let online = 0, offline = 0, unconfigured = 0
  for (const o of organizations.value) {
    if (!o.probe_key) unconfigured++
    else if (o.probe_online) online++
    else offline++
  }
  return { total, online, offline, unconfigured }
})

async function loadData() {
  loading.value = true
  try {
    const params = {}
    if (keyword.value) params.keyword = keyword.value
    const res = await organizationApi.list(params)
    organizations.value = res.items || []
  } catch (e) {
    ElMessage.error('加载探针状态失败')
  } finally {
    loading.value = false
  }
}

function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

async function handleReset(row) {
  try {
    await ElMessageBox.confirm(`确认重置「${row.name}」的探针密钥？重置后旧配置立即失效，需重新下载部署。`, '重置确认', { type: 'warning', confirmButtonText: '确认重置', cancelButtonText: '取消' })
  } catch { return }
  try {
    const res = await organizationApi.resetProbe(row.id)
    resetResult.value = { ...res, org_id: row.id, org_code: row.code }
    resetDialogVisible.value = true
    ElMessage.success('探针密钥已重置')
    loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '重置失败')
  }
}

async function handleClear(row) {
  try {
    await ElMessageBox.confirm(`确认彻底清理「${row.name}」的探针配置？将移除 WireGuard peer 并清空所有探针字段，历史任务记录保留。此操作不可恢复。`, '清理确认', { type: 'error', confirmButtonText: '确认清理', cancelButtonText: '取消' })
  } catch { return }
  try {
    await organizationApi.clearProbe(row.id)
    ElMessage.success('探针配置已清理')
    loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '清理失败')
  }
}

async function downloadConfig(orgId) {
  try {
    const res = await organizationApi.downloadProbeConfig(orgId)
    const blob = new Blob([res], { type: 'application/zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `opsflow-probe-${resetResult.value.org_code || orgId}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载配置失败')
  }
}

onMounted(() => {
  loadData()
  timer = setInterval(loadData, 30000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.stat-row { margin-bottom: 16px; }
.stat-card { text-align: center; }
.stat-label { font-size: 13px; color: #909399; margin-bottom: 8px; }
.stat-value { font-size: 28px; font-weight: 600; color: #303133; }
.stat-online .stat-value { color: #67c23a; }
.stat-offline .stat-value { color: #f56c6c; }
.stat-unconfigured .stat-value { color: #909399; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.muted { color: #c0c4cc; }
.mono { font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; }
</style>
