<template>
  <div class="module-page">
    <el-row :gutter="12" class="stats-row">
      <el-col :xs="12" :md="6"><el-statistic title="备份任务" :value="stats.jobs || 0" /></el-col>
      <el-col :xs="12" :md="6"><el-statistic title="启用任务" :value="stats.enabled_jobs || 0" /></el-col>
      <el-col :xs="12" :md="6"><el-statistic title="配置快照" :value="stats.snapshots || 0" /></el-col>
      <el-col :xs="12" :md="6"><el-statistic title="失败快照" :value="stats.failed_snapshots || 0" /></el-col>
    </el-row>

    <el-tabs v-model="activeTab" type="border-card" @tab-change="onTabChange">
      <!-- 备份任务 -->
      <el-tab-pane label="备份任务" name="jobs">
        <el-row justify="end" style="margin-bottom: 12px">
          <el-button type="primary" @click="openJobDialog()">新增任务</el-button>
        </el-row>
        <el-table v-loading="jobLoading" :data="jobs" border stripe>
          <el-table-column prop="name" label="名称" min-width="180" />
          <el-table-column prop="command" label="备份命令" width="200" show-overflow-tooltip />
          <el-table-column prop="schedule_cron" label="定时" width="130" />
          <el-table-column prop="asset_filter" label="资产筛选" width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.asset_filter || '全部' }}</template>
          </el-table-column>
          <el-table-column prop="enabled" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="250" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="success" :loading="row._running" @click="runJob(row)">执行</el-button>
              <el-button size="small" type="primary" @click="openJobDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteJob(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 配置快照 -->
      <el-tab-pane label="配置快照" name="snapshots">
        <el-form :model="snapQuery" inline style="margin-bottom: 12px">
          <el-form-item><el-input v-model="snapQuery.keyword" placeholder="资产名/配置内容" clearable style="width: 200px" @clear="loadSnapshots" @keyup.enter="loadSnapshots" /></el-form-item>
          <el-form-item><el-button type="primary" @click="loadSnapshots">搜索</el-button></el-form-item>
        </el-form>
        <el-table v-loading="snapLoading" :data="snapshots" border stripe>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="asset_name" label="资产" min-width="140" />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 'captured' ? 'success' : 'danger'" size="small">{{ row.status === 'captured' ? '已采集' : '失败' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="content_hash" label="哈希" width="100">
            <template #default="{ row }">{{ row.content_hash ? row.content_hash.slice(0, 8) + '...' : '-' }}</template>
          </el-table-column>
          <el-table-column label="变更" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.diff_summary" type="warning" size="small">有变更</el-tag>
              <el-tag v-else type="info" size="small">无变更</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" width="170">
            <template #default="{ row }">{{ row.created_at ? row.created_at.replace('T', ' ').slice(0, 19) : '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="viewDiff(row)">Diff</el-button>
              <el-button size="small" @click="viewConfig(row)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination v-model:current-page="snapQuery.page" style="margin-top: 16px; justify-content: flex-end" background layout="prev,pager,next,total" :total="snapTotal" :page-size="snapQuery.size" @current-change="loadSnapshots" />
      </el-tab-pane>
    </el-tabs>

    <!-- 任务编辑对话框 -->
    <el-dialog v-model="jobDialogVisible" :title="jobForm.id ? '编辑任务' : '新增任务'" width="540px">
      <el-form :model="jobForm" label-width="90px">
        <el-form-item label="名称"><el-input v-model="jobForm.name" /></el-form-item>
        <el-form-item label="备份命令"><el-input v-model="jobForm.command" placeholder="show running-config" /></el-form-item>
        <el-form-item label="定时计划"><el-input v-model="jobForm.schedule_cron" placeholder="0 2 * * *" /></el-form-item>
        <el-form-item label="资产筛选"><el-input v-model="jobForm.asset_filter" placeholder="留空表示全部资产，多个 ID 逗号分隔" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="jobForm.enabled" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="jobForm.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="jobDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveJob">保存</el-button>
      </template>
    </el-dialog>

    <!-- Diff 查看对话框 -->
    <el-dialog v-model="diffDialogVisible" title="配置差异对比" width="750px">
      <el-descriptions :column="2" border v-if="diffData">
        <el-descriptions-item label="变更">{{ diffData.changed ? '有变更' : '无变更' }}</el-descriptions-item>
        <el-descriptions-item label="当前哈希">{{ diffData.current_hash || '-' }}</el-descriptions-item>
      </el-descriptions>
      <pre class="diff-view" v-if="diffData && diffData.diff">{{ diffData.diff }}</pre>
      <el-empty v-else description="无差异数据" />
    </el-dialog>

    <!-- 配置内容查看对话框 -->
    <el-dialog v-model="configDialogVisible" title="配置内容" width="750px">
      <pre class="config-view">{{ configText }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { configBackupApi } from '@/api'

const stats = ref({})
const activeTab = ref('jobs')
const jobs = ref([])
const jobLoading = ref(false)
const snapshots = ref([])
const snapLoading = ref(false)
const snapTotal = ref(0)

const snapQuery = reactive({ page: 1, size: 20, keyword: '' })

const jobDialogVisible = ref(false)
const jobForm = reactive({ id: null, name: '', command: 'show running-config', schedule_cron: '0 2 * * *', asset_filter: '', enabled: true, notes: '' })

const diffDialogVisible = ref(false)
const diffData = ref(null)
const configDialogVisible = ref(false)
const configText = ref('')

async function loadStats() { stats.value = await configBackupApi.dashboard() }

async function loadJobs() {
  jobLoading.value = true
  try {
    const res = await configBackupApi.listJobs({ size: 100 })
    jobs.value = res.items || []
  } finally { jobLoading.value = false }
}

async function loadSnapshots() {
  snapLoading.value = true
  try {
    const params = { page: snapQuery.page, size: snapQuery.size }
    if (snapQuery.keyword) params.keyword = snapQuery.keyword
    const res = await configBackupApi.listSnapshots(params)
    snapshots.value = res.items || []
    snapTotal.value = res.total || 0
  } finally { snapLoading.value = false }
}

function onTabChange(tab) {
  if (tab === 'snapshots') loadSnapshots()
}

function openJobDialog(row) {
  if (row) {
    Object.assign(jobForm, { id: row.id, name: row.name, command: row.command, schedule_cron: row.schedule_cron, asset_filter: row.asset_filter || '', enabled: row.enabled, notes: row.notes || '' })
  } else {
    Object.assign(jobForm, { id: null, name: '', command: 'show running-config', schedule_cron: '0 2 * * *', asset_filter: '', enabled: true, notes: '' })
  }
  jobDialogVisible.value = true
}

async function saveJob() {
  if (jobForm.id) {
    await configBackupApi.updateJob(jobForm.id, jobForm)
    ElMessage.success('任务已更新')
  } else {
    await configBackupApi.createJob(jobForm)
    ElMessage.success('任务已创建')
  }
  jobDialogVisible.value = false
  loadJobs()
  loadStats()
}

async function deleteJob(row) {
  await ElMessageBox.confirm(`确认删除任务 "${row.name}"？`, '确认删除', { type: 'warning' })
  await configBackupApi.deleteJob(row.id)
  ElMessage.success('任务已删除')
  loadJobs()
  loadStats()
}

async function runJob(row) {
  row._running = true
  try {
    await configBackupApi.runJob(row.id)
    ElMessage.success('备份任务已提交')
  } finally { row._running = false }
}

async function viewDiff(row) {
  try {
    diffData.value = await configBackupApi.getDiff(row.id)
  } catch { diffData.value = null }
  diffDialogVisible.value = true
}

async function viewConfig(row) {
  try {
    const detail = await configBackupApi.getSnapshot(row.id)
    configText.value = detail.config_text || '无配置内容'
  } catch { configText.value = '加载失败' }
  configDialogVisible.value = true
}

async function loadData() {
  await loadStats()
  await loadJobs()
}

onMounted(loadData)
</script>

<style scoped>
.diff-view, .config-view {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  max-height: 500px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin-top: 12px;
}
</style>
