<template>
  <div class="app-container">
    <StatCards :items="statItems" />
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>探针状态监控</span>
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
        <el-table-column label="心跳延迟" width="120">
          <template #default="{ row }">
            <span v-if="row.probe_last_heartbeat" :class="heartbeatClass(row)">{{ heartbeatDelay(row) }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="隧道 IP" width="140">
          <template #default="{ row }">
            <span v-if="row.wg_tunnel_ip" class="mono">{{ row.wg_tunnel_ip }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" align="center" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="goToOrg(row)">配置</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { organizationApi } from '@/api'
import StatCards from '@/components/common/StatCards.vue'

const router = useRouter()
const organizations = ref([])
const loading = ref(false)
const keyword = ref('')
let timer = null

const statItems = computed(() => {
  const total = organizations.value.length
  let online = 0, offline = 0, unconfigured = 0
  for (const o of organizations.value) {
    if (!o.probe_key) unconfigured++
    else if (o.probe_online) online++
    else offline++
  }
  return [
    { title: '组织总数', value: total },
    { title: '探针在线', value: online },
    { title: '探针离线', value: offline },
    { title: '未配置', value: unconfigured },
  ]
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

function heartbeatDelay(row) {
  if (!row.probe_last_heartbeat) return ''
  const diff = Math.floor((Date.now() - new Date(row.probe_last_heartbeat).getTime()) / 1000)
  if (diff < 60) return `${diff} 秒前`
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  return `${Math.floor(diff / 3600)} 小时前`
}

function heartbeatClass(row) {
  if (!row.probe_last_heartbeat) return ''
  const diff = Math.floor((Date.now() - new Date(row.probe_last_heartbeat).getTime()) / 1000)
  if (diff < 120) return 'ok'
  if (diff < 600) return 'warn'
  return 'bad'
}

function goToOrg() {
  router.push('/organizations')
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
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.muted {
  color: var(--ops-text-muted, #c0c4cc);
}
.mono {
  font-family: var(--ops-font-mono, 'Consolas', 'Monaco', monospace);
  font-size: 12px;
}
.ok {
  color: var(--ops-success, #67c23a);
}
.warn {
  color: var(--ops-warning, #e6a23c);
}
.bad {
  color: var(--ops-danger, #f56c6c);
}
</style>
