<template>
  <div>
    <!-- 统计卡片 -->
    <StatCards :items="statItems" />
    <!-- 筛选 + 表格 -->
    <el-card shadow="never">
      <template #header>
        <el-row justify="space-between" align="middle">
          <el-form :model="query" inline>
            <el-form-item><el-input v-model="query.keyword" placeholder="运营商/线路/位置" clearable style="width: 200px" @clear="loadData" @keyup.enter="loadData" /></el-form-item>
            <el-form-item>
              <el-select v-model="query.status" clearable placeholder="状态" style="width: 120px" @change="loadData">
                <el-option label="在用" value="active" />
                <el-option label="已过期" value="expired" />
                <el-option label="已取消" value="cancelled" />
              </el-select>
            </el-form-item>
            <el-form-item><el-button type="primary" @click="loadData">搜索</el-button></el-form-item>
          </el-form>
          <el-button type="primary" @click="formDialogRef?.openCreate()">新增宽带</el-button>
          <el-button @click="downloadTemplate">下载模板</el-button>
          <el-button type="success" @click="importDialogRef?.open()">导入 Excel</el-button>
          <el-button type="warning" @click="exportExcel">导出 Excel</el-button>
        </el-row>
      </template>
      <el-table v-loading="loading" :data="tableData" stripe border :default-sort="{ prop: 'next_renewal_days', order: 'ascending' }">
        <el-table-column prop="provider" label="运营商" width="120" sortable />
        <el-table-column prop="circuit_id" label="线路编号" width="130" sortable />
        <el-table-column prop="bandwidth_mbps" label="带宽" width="90" align="center" sortable>
          <template #default="{ row }">{{ row.bandwidth_mbps }}M</template>
        </el-table-column>
        <el-table-column prop="renewal_cycle" label="续费周期" width="130" align="center" sortable :sort-method="(a, b) => cycleOrder(a.renewal_cycle) - cycleOrder(b.renewal_cycle)">
          <template #default="{ row }">
            <el-tag size="small" :type="cycleTagType(row.renewal_cycle)">{{ cycleLabel(row.renewal_cycle) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="renewal_cost" label="周期费用" width="110" align="right" sortable>
          <template #default="{ row }">{{ row.renewal_cost != null ? row.renewal_cost.toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="annual_cost" label="年费" width="100" align="right" sortable>
          <template #default="{ row }">{{ row.annual_cost != null ? row.annual_cost.toFixed(0) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="location" label="位置" min-width="130" show-overflow-tooltip sortable />
        <el-table-column prop="contract_end" label="到期日期" width="110" sortable />
        <el-table-column prop="next_renewal_deadline" label="下次续费日" width="150" align="center" sortable :sort-by="(row) => row.status === 'active' ? row.next_renewal_deadline : '9999-12-31'">
          <template #default="{ row }">
            <template v-if="row.status === 'active'">
              <span>{{ row.next_renewal_deadline }}</span>
              <el-tag size="small" :type="row.deadline_type === 'cycle' ? 'warning' : 'info'" style="margin-left: 4px">{{ row.deadline_type === 'cycle' ? '周期' : '合同' }}</el-tag>
            </template>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="next_renewal_days" label="剩余" width="80" align="center" sortable :sort-by="(row) => row.status === 'active' ? row.next_renewal_days : 99999">
          <template #default="{ row }">
            <span v-if="row.status === 'active'" :style="{ color: daysColor(row) }">{{ daysRemaining(row) }}天</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="contact_name" label="联系人" width="80" />
        <el-table-column prop="status" label="状态" width="75">
          <template #default="{ row }">
            <StatusTag :value="row.status" :status-map="statusMap" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="formDialogRef?.openEdit(row)">编辑</el-button>
            <el-button size="small" type="success" :loading="row._notifying" @click="testNotify(row)">通知</el-button>
            <el-button size="small" type="danger" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="query.page"
        style="margin-top: 16px; justify-content: flex-end"
        background
        layout="prev,pager,next,total"
        :total="total"
        :page-size="query.size"
        @current-change="loadData"
      />
    </el-card>
    <!-- 新建/编辑对话框 -->
    <BroadbandFormDialog ref="formDialogRef" @submit="onFormSubmit" />
    <!-- 导入对话框 -->
    <BroadbandImportDialog ref="importDialogRef" @download-template="downloadTemplate" @imported="loadData" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { broadbandApi } from '@/api'
import StatCards from '@/components/common/StatCards.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import BroadbandFormDialog from './BroadbandFormDialog.vue'
import BroadbandImportDialog from './BroadbandImportDialog.vue'

const CYCLE_LABELS = { monthly: '每月', quarterly: '每季度', semi_annual: '每半年', annual: '每年' }
const CYCLE_TAG_TYPES = { monthly: 'warning', quarterly: 'primary', semi_annual: 'success', annual: '' }

const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const formDialogRef = ref(null)
const importDialogRef = ref(null)

const statusMap = {
  active: { label: '在用', type: 'success' },
  expired: { label: '已过期', type: 'danger' },
  cancelled: { label: '已取消', type: 'info' },
}

const dashboard = reactive({ total: 0, active: 0, expired: 0, expiring_30d: 0, expiring_7d: 0, expiring_renewal_30d: 0, expiring_renewal_7d: 0, total_annual_cost: 0 })
const query = reactive({ keyword: '', status: '', page: 1, size: 20 })

const statItems = computed(() => [
  { title: '合同总数', value: dashboard.total },
  { title: '30天内到期', value: dashboard.expiring_renewal_30d },
  { title: '已过期', value: dashboard.expired },
  { title: '年度总费用', value: dashboard.total_annual_cost, suffix: '元' },
])

function cycleLabel(cycle) { return CYCLE_LABELS[cycle] || '每年' }
function cycleTagType(cycle) { return CYCLE_TAG_TYPES[cycle] || '' }
function cycleOrder(cycle) { return { monthly: 1, quarterly: 3, semi_annual: 6, annual: 12 }[cycle] || 99 }
function daysRemaining(row) { return row.next_renewal_days }
function daysColor(row) {
  const d = daysRemaining(row)
  if (d <= 7) return 'var(--ops-danger)'
  if (d <= 30) return 'var(--ops-warning)'
  return 'var(--ops-success)'
}

async function loadData() {
  loading.value = true
  try {
    const r = await broadbandApi.list(query)
    tableData.value = r.items.map((i) => ({ ...i, _notifying: false }))
    total.value = r.total
    const d = await broadbandApi.dashboard()
    Object.assign(dashboard, d)
  } finally {
    loading.value = false
  }
}

async function onFormSubmit({ id, form }) {
  if (id) {
    await broadbandApi.update(id, form)
    ElMessage.success('已更新')
  } else {
    await broadbandApi.create(form)
    ElMessage.success('已创建')
  }
  loadData()
}

async function del(row) {
  await ElMessageBox.confirm('确定删除该合同?', '确认', { type: 'warning' })
  await broadbandApi.delete(row.id)
  ElMessage.success('已删除')
  loadData()
}

async function testNotify(row) {
  row._notifying = true
  try {
    await broadbandApi.testNotify(row.id)
    ElMessage.success('通知已发送，请检查钉钉群')
  } catch (_e) {
    ElMessage.error('发送失败')
  } finally {
    row._notifying = false
  }
}

async function downloadTemplate() {
  try {
    const blob = await broadbandApi.downloadTemplate()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '宽带合同导入模板.xlsx'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (_e) {
    ElMessage.error('模板下载失败')
  }
}

async function exportExcel() {
  try {
    const blob = await broadbandApi.exportExcel({ keyword: query.keyword, status: query.status })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '宽带合同列表.xlsx'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (_e) {
    ElMessage.error('导出失败')
  }
}

onMounted(() => loadData())
</script>
