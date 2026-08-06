<template>
  <div class="module-page">
    <el-row :gutter="12" class="stats-row">
      <el-col :xs="12" :md="6"><el-statistic title="批次总数" :value="stats.batches || 0" /></el-col>
      <el-col :xs="12" :md="6"><el-statistic title="运行中" :value="stats.running_batches || 0" /></el-col>
      <el-col :xs="12" :md="6"><el-statistic title="已完成" :value="stats.completed_batches || 0" /></el-col>
      <el-col :xs="12" :md="6"><el-statistic title="失败结果" :value="stats.failed_results || 0" /></el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <el-row justify="space-between" align="middle">
          <el-form :model="query" inline>
            <el-form-item>
              <el-select v-model="query.status" clearable placeholder="状态" style="width: 120px" @change="loadBatches">
                <el-option label="草稿" value="draft" />
                <el-option label="运行中" value="running" />
                <el-option label="已完成" value="completed" />
                <el-option label="部分成功" value="partial" />
                <el-option label="失败" value="failed" />
                <el-option label="已拦截" value="blocked" />
              </el-select>
            </el-form-item>
            <el-form-item><el-button type="primary" @click="loadBatches">筛选</el-button></el-form-item>
          </el-form>
          <el-button type="primary" @click="openBatchDialog()">新建批次</el-button>
        </el-row>
      </template>
      <el-table v-loading="loading" :data="batches" border stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="mode" label="模式" width="80" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="commands" label="命令" min-width="200" show-overflow-tooltip />
        <el-table-column prop="summary" label="摘要" min-width="160" show-overflow-tooltip />
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ row.created_at ? row.created_at.replace('T', ' ').slice(0, 19) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'draft' || row.status === 'failed'" size="small" type="success" @click="executeBatch(row)">执行</el-button>
            <el-button size="small" type="primary" @click="viewResults(row)">结果</el-button>
            <el-button v-if="row.status === 'draft'" size="small" @click="openBatchDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteBatch(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="query.page" style="margin-top: 16px; justify-content: flex-end" background layout="prev,pager,next,total" :total="total" :page-size="query.size" @current-change="loadBatches" />
    </el-card>

    <!-- 新建/编辑批次对话框 -->
    <el-dialog v-model="batchDialogVisible" :title="batchForm.id ? '编辑批次' : '新建批次'" width="640px">
      <el-form :model="batchForm" label-width="90px">
        <el-form-item label="名称"><el-input v-model="batchForm.name" /></el-form-item>
        <el-form-item label="目标资产">
          <el-select v-model="selectedAssetIds" multiple filterable placeholder="选择资产" style="width: 100%">
            <el-option v-for="a in assetOptions" :key="a.id" :label="`${a.name} (${a.ip_address})`" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="命令">
          <el-input v-model="batchForm.commands" type="textarea" :rows="6" placeholder="每行一条命令，例如：&#10;show version&#10;show ip interface brief" />
        </el-form-item>
        <el-alert v-if="dangerousCommands.length" type="error" :closable="false" style="margin-bottom: 12px">
          <template #title>检测到危险命令</template>
          <div v-for="(cmd, i) in dangerousCommands" :key="i" style="font-size: 12px; margin-top: 4px">{{ cmd }}</div>
        </el-alert>
        <el-form-item label="模式">
          <el-select v-model="batchForm.mode" style="width: 100%">
            <el-option label="脚本模式" value="script" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveBatch">保存</el-button>
      </template>
    </el-dialog>

    <!-- 执行确认对话框 -->
    <el-dialog v-model="confirmDialogVisible" title="执行确认" width="500px">
      <el-alert v-if="executeGuard && !executeGuard.safe" type="error" :closable="false">
        <template #title>危险命令被拦截</template>
        <div v-for="(r, i) in executeGuard.reasons" :key="i" style="font-size: 12px; margin-top: 4px">{{ r }}</div>
      </el-alert>
      <div v-else>
        <p>确认执行批次 <strong>{{ executeBatchName }}</strong>？</p>
        <p style="color: var(--ops-text-muted); font-size: 13px">将对选中的资产执行命令，请确认命令内容无误。</p>
      </div>
      <template #footer>
        <el-button @click="confirmDialogVisible = false">取消</el-button>
        <el-button v-if="!executeGuard || executeGuard.safe" type="primary" @click="confirmExecute">确认执行</el-button>
      </template>
    </el-dialog>

    <!-- 执行结果对话框 -->
    <el-dialog v-model="resultDialogVisible" title="执行结果" width="800px">
      <div v-if="results.length">
        <div v-for="r in results" :key="r.id" class="result-item">
          <el-row :gutter="8" align="middle" style="margin-bottom: 8px">
            <el-col :span="8"><strong>{{ r.asset_name || `资产#${r.asset_id}` }}</strong></el-col>
            <el-col :span="4">
              <el-tag :type="r.status === 'success' ? 'success' : 'danger'" size="small">{{ r.status === 'success' ? '成功' : '失败' }}</el-tag>
            </el-col>
          </el-row>
          <pre class="output-block">{{ r.output || r.error_message || '无输出' }}</pre>
        </div>
      </div>
      <el-empty v-else description="暂无执行结果" />
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { commandApi, assetApi } from '@/api'

const stats = ref({})
const loading = ref(false)
const batches = ref([])
const total = ref(0)
const query = reactive({ page: 1, size: 20, status: null })

const assetOptions = ref([])
const selectedAssetIds = ref([])

const batchDialogVisible = ref(false)
const batchForm = reactive({ id: null, name: '', commands: '', mode: 'script', status: 'draft' })

// 前端危险命令检测
const DANGEROUS_RE = [
  /\berase\b/i, /\bformat\b/i, /\breload\b/i, /\breboot\b/i,
  /\bwrite\s+erase\b/i, /\bfactory-reset\b/i, /\bdelete\s+\//i,
  /\bcopy\s+.*\s+running-config\b/i, /\bdelete\s+flash:/i,
]
const dangerousCommands = computed(() => {
  if (!batchForm.commands) return []
  return batchForm.commands.split('\n').filter(line => {
    const t = line.trim()
    return t && !t.startsWith('#') && DANGEROUS_RE.some(re => re.test(t))
  })
})

const confirmDialogVisible = ref(false)
const executeGuard = ref(null)
const executeBatchId = ref(null)
const executeBatchName = ref('')

const resultDialogVisible = ref(false)
const results = ref([])

function statusType(s) {
  return { draft: 'info', pending: '', running: 'warning', completed: 'success', partial: 'warning', failed: 'danger', blocked: 'danger' }[s] || 'info'
}
function statusLabel(s) {
  return { draft: '草稿', pending: '等待中', running: '运行中', completed: '已完成', partial: '部分成功', failed: '失败', blocked: '已拦截' }[s] || s
}

async function loadStats() { stats.value = await commandApi.dashboard() }

async function loadBatches() {
  loading.value = true
  try {
    const params = { page: query.page, size: query.size }
    if (query.status) params.status = query.status
    const res = await commandApi.listBatches(params)
    batches.value = res.items || []
    total.value = res.total || 0
  } finally { loading.value = false }
}

async function loadAssets() {
  try {
    const res = await assetApi.list({ size: 100 })
    assetOptions.value = res.items || []
  } catch { assetOptions.value = [] }
}

function openBatchDialog(row) {
  if (row) {
    Object.assign(batchForm, { id: row.id, name: row.name, commands: row.commands, mode: row.mode, status: row.status })
    selectedAssetIds.value = row.asset_ids ? row.asset_ids.split(',').filter(Boolean).map(Number) : []
  } else {
    Object.assign(batchForm, { id: null, name: '', commands: '', mode: 'script', status: 'draft' })
    selectedAssetIds.value = []
  }
  batchDialogVisible.value = true
}

async function saveBatch() {
  const data = { ...batchForm, asset_ids: selectedAssetIds.value.join(','), status: 'draft' }
  if (batchForm.id) {
    await commandApi.updateBatch(batchForm.id, data)
    ElMessage.success('批次已更新')
  } else {
    await commandApi.createBatch(data)
    ElMessage.success('批次已创建')
  }
  batchDialogVisible.value = false
  loadBatches()
  loadStats()
}

async function deleteBatch(row) {
  await ElMessageBox.confirm(`确认删除批次 "${row.name}"？`, '确认删除', { type: 'warning' })
  await commandApi.deleteBatch(row.id)
  ElMessage.success('批次已删除')
  loadBatches()
  loadStats()
}

async function executeBatch(row) {
  executeBatchId.value = row.id
  executeBatchName.value = row.name
  executeGuard.value = null
  confirmDialogVisible.value = true
}

async function confirmExecute() {
  try {
    const res = await commandApi.executeBatch(executeBatchId.value)
    if (res.safe === false) {
      executeGuard.value = res
      return
    }
    ElMessage.success('执行任务已提交')
    confirmDialogVisible.value = false
    loadBatches()
    loadStats()
  } catch (e) {
    ElMessage.error('执行失败: ' + (e.message || e))
  }
}

async function viewResults(row) {
  try {
    results.value = await commandApi.listResults(row.id)
  } catch { results.value = [] }
  resultDialogVisible.value = true
}

async function loadData() {
  await Promise.all([loadStats(), loadBatches(), loadAssets()])
}

onMounted(loadData)
</script>

<style scoped>
.result-item {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--ops-border);
}
.result-item:last-child {
  border-bottom: none;
}
.output-block {
  background: var(--ops-term-bg);
  color: var(--ops-term-fg);
  padding: 12px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
</style>
