<template>
  <div class="module-page">
    <el-row :gutter="12" class="stats-row">
      <el-col :xs="12" :md="6"><el-statistic title="巡检方案" :value="stats.plans || 0" /></el-col>
      <el-col :xs="12" :md="6"><el-statistic title="启用方案" :value="stats.enabled_plans || 0" /></el-col>
      <el-col :xs="12" :md="6"><el-statistic title="巡检报告" :value="stats.runs || 0" /></el-col>
      <el-col :xs="12" :md="6"><el-statistic title="异常数量" :value="stats.exceptions || 0" /></el-col>
    </el-row>

    <el-tabs v-model="activeTab" type="border-card" @tab-change="onTabChange">
      <!-- 巡检方案 -->
      <el-tab-pane label="巡检方案" name="plans">
        <el-row justify="end" style="margin-bottom: 12px">
          <el-button type="primary" @click="openPlanDialog()">新增方案</el-button>
        </el-row>
        <el-table v-loading="planLoading" :data="plans" border stripe>
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column prop="scope" label="范围" width="100" />
          <el-table-column prop="checks" label="检查项" min-width="180">
            <template #default="{ row }">
              <el-tag v-for="c in (row.checks || '').split(',').filter(Boolean)" :key="c" size="small" style="margin: 2px">{{ checkLabel(c.trim()) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="schedule_cron" label="定时" width="130" />
          <el-table-column prop="notify_dingtalk" label="钉钉" width="80">
            <template #default="{ row }">
              <el-tag :type="row.notify_dingtalk ? 'success' : 'info'" size="small">{{ row.notify_dingtalk ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="enabled" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="250" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="success" :loading="row._running" @click="runPlan(row)">执行</el-button>
              <el-button size="small" type="primary" @click="openPlanDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deletePlan(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 巡检报告 -->
      <el-tab-pane label="巡检报告" name="runs">
        <el-form :model="runQuery" inline style="margin-bottom: 12px">
          <el-form-item>
            <el-select v-model="runQuery.plan_id" clearable placeholder="选择方案" style="width: 180px" @change="loadRuns">
              <el-option v-for="p in plans" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-select v-model="runQuery.status" clearable placeholder="状态" style="width: 120px" @change="loadRuns">
              <el-option label="运行中" value="running" />
              <el-option label="已完成" value="completed" />
              <el-option label="失败" value="failed" />
            </el-select>
          </el-form-item>
          <el-form-item><el-button type="primary" @click="loadRuns">筛选</el-button></el-form-item>
        </el-form>
        <el-table v-loading="runLoading" :data="runs" border stripe>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column label="方案" width="160">
            <template #default="{ row }">{{ planName(row.plan_id) }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : ''" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="exception_count" label="异常" width="80" />
          <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
          <el-table-column label="时间" width="170">
            <template #default="{ row }">{{ row.created_at ? row.created_at.replace('T', ' ').slice(0, 19) : '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="viewReport(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination v-model:current-page="runQuery.page" style="margin-top: 16px; justify-content: flex-end" background layout="prev,pager,next,total" :total="runTotal" :page-size="runQuery.size" @current-change="loadRuns" />
      </el-tab-pane>
    </el-tabs>

    <!-- 方案编辑对话框 -->
    <el-dialog v-model="planDialogVisible" :title="planForm.id ? '编辑方案' : '新增方案'" width="540px">
      <el-form :model="planForm" label-width="90px">
        <el-form-item label="名称"><el-input v-model="planForm.name" /></el-form-item>
        <el-form-item label="范围">
          <el-select v-model="planForm.scope" style="width: 100%">
            <el-option label="所有资产" value="assets" />
            <el-option label="核心资产" value="core" />
          </el-select>
        </el-form-item>
        <el-form-item label="检查项">
          <el-checkbox-group v-model="planChecks">
            <el-checkbox label="ping">Ping 连通性</el-checkbox>
            <el-checkbox label="port">SSH 端口</el-checkbox>
            <el-checkbox label="broadband_expiry">宽带到期</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="定时计划"><el-input v-model="planForm.schedule_cron" placeholder="0 9 * * *" /></el-form-item>
        <el-form-item label="钉钉通知"><el-switch v-model="planForm.notify_dingtalk" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="planForm.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePlan">保存</el-button>
      </template>
    </el-dialog>

    <!-- 报告详情对话框 -->
    <el-dialog v-model="reportDialogVisible" title="巡检报告详情" width="700px">
      <el-descriptions :column="2" border v-if="currentRun">
        <el-descriptions-item label="状态">{{ currentRun.status }}</el-descriptions-item>
        <el-descriptions-item label="异常数">{{ currentRun.exception_count }}</el-descriptions-item>
        <el-descriptions-item label="摘要" :span="2">{{ currentRun.summary }}</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 16px" v-if="reportItems.length">
        <el-table :data="reportItems" border stripe size="small" max-height="400">
          <el-table-column prop="asset" label="资产" min-width="160" />
          <el-table-column prop="target" label="目标" min-width="120" />
          <el-table-column prop="check" label="检查项" width="120" />
          <el-table-column prop="status" label="结果" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'ok' ? 'success' : row.status === 'warning' ? 'warning' : 'danger'" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="detail" label="详情" min-width="200" show-overflow-tooltip />
        </el-table>
      </div>
      <el-empty v-else description="无检查数据" />
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { inspectionApi } from '@/api'

const stats = ref({})
const activeTab = ref('plans')
const plans = ref([])
const planLoading = ref(false)
const runs = ref([])
const runLoading = ref(false)
const runTotal = ref(0)

const runQuery = reactive({ page: 1, size: 20, plan_id: null, status: null })

const planDialogVisible = ref(false)
const planForm = reactive({ id: null, name: '', scope: 'assets', checks: 'ping,port', schedule_cron: '0 9 * * *', notify_dingtalk: true, enabled: true })
const planChecks = ref(['ping', 'port'])

const reportDialogVisible = ref(false)
const currentRun = ref(null)
const reportItems = ref([])

function checkLabel(c) {
  return { ping: 'Ping', port: 'SSH 端口', broadband_expiry: '宽带到期', service: '服务' }[c] || c
}
function planName(id) {
  const p = plans.value.find(p => p.id === id)
  return p ? p.name : `#${id}`
}

async function loadStats() { stats.value = await inspectionApi.dashboard() }

async function loadPlans() {
  planLoading.value = true
  try {
    const res = await inspectionApi.listPlans({ size: 100 })
    plans.value = res.items || []
  } finally { planLoading.value = false }
}

async function loadRuns() {
  runLoading.value = true
  try {
    const params = { page: runQuery.page, size: runQuery.size }
    if (runQuery.plan_id) params.plan_id = runQuery.plan_id
    if (runQuery.status) params.status = runQuery.status
    const res = await inspectionApi.listRuns(params)
    runs.value = res.items || []
    runTotal.value = res.total || 0
  } finally { runLoading.value = false }
}

function onTabChange(tab) {
  if (tab === 'runs') loadRuns()
}

function openPlanDialog(row) {
  if (row) {
    Object.assign(planForm, { id: row.id, name: row.name, scope: row.scope, checks: row.checks, schedule_cron: row.schedule_cron, notify_dingtalk: row.notify_dingtalk, enabled: row.enabled })
    planChecks.value = (row.checks || '').split(',').filter(Boolean).map(s => s.trim())
  } else {
    Object.assign(planForm, { id: null, name: '', scope: 'assets', checks: 'ping,port', schedule_cron: '0 9 * * *', notify_dingtalk: true, enabled: true })
    planChecks.value = ['ping', 'port']
  }
  planDialogVisible.value = true
}

async function savePlan() {
  planForm.checks = planChecks.value.join(',')
  if (planForm.id) {
    await inspectionApi.updatePlan(planForm.id, planForm)
    ElMessage.success('方案已更新')
  } else {
    await inspectionApi.createPlan(planForm)
    ElMessage.success('方案已创建')
  }
  planDialogVisible.value = false
  loadPlans()
  loadStats()
}

async function deletePlan(row) {
  await ElMessageBox.confirm(`确认删除方案 "${row.name}"？`, '确认删除', { type: 'warning' })
  await inspectionApi.deletePlan(row.id)
  ElMessage.success('方案已删除')
  loadPlans()
  loadStats()
}

async function runPlan(row) {
  row._running = true
  try {
    await inspectionApi.runPlan(row.id)
    ElMessage.success('巡检任务已提交')
  } finally { row._running = false }
}

async function viewReport(row) {
  currentRun.value = row
  try {
    const detail = await inspectionApi.getRun(row.id)
    currentRun.value = detail
    if (detail.report_json) {
      try { reportItems.value = JSON.parse(detail.report_json) } catch { reportItems.value = [] }
    } else {
      reportItems.value = []
    }
  } catch { reportItems.value = [] }
  reportDialogVisible.value = true
}

async function loadData() {
  await loadStats()
  await loadPlans()
}

onMounted(loadData)
</script>
