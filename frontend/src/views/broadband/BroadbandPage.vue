<template>
  <div>
    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="6"><el-card shadow="never"><el-statistic title="合同总数" :value="dashboard.total" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="never"><el-statistic title="30天内到期" :value="dashboard.expiring_30d" :value-style="{ color: dashboard.expiring_30d > 0 ? '#e6a23c' : '#67c23a' }" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="never"><el-statistic title="已过期" :value="dashboard.expired" :value-style="{ color: dashboard.expired > 0 ? '#f56c6c' : '#67c23a' }" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="never"><el-statistic title="年度总费用" :value="dashboard.total_annual_cost" suffix="元" :precision="2" /></el-card></el-col>
    </el-row>
    <!-- 筛选 + 表格 -->
    <el-card shadow="never">
      <template #header>
        <el-row justify="space-between" align="middle">
          <el-form :model="query" inline>
            <el-form-item><el-input v-model="query.keyword" placeholder="运营商/线路/位置" clearable style="width:200px" @clear="loadData" @keyup.enter="loadData" /></el-form-item>
            <el-form-item><el-select v-model="query.status" clearable placeholder="状态" style="width:120px" @change="loadData"><el-option label="在用" value="active" /><el-option label="已过期" value="expired" /><el-option label="已取消" value="cancelled" /></el-select></el-form-item>
            <el-form-item><el-button type="primary" @click="loadData">搜索</el-button></el-form-item>
          </el-form>
          <el-button type="primary" @click="openCreate">新增宽带</el-button>
          <el-button @click="downloadTemplate">下载模板</el-button>
          <el-button type="success" @click="importDlg = true">导入 Excel</el-button>
        </el-row>
      </template>
      <el-table :data="tableData" v-loading="loading" stripe border>
        <el-table-column prop="provider" label="运营商" width="120" />
        <el-table-column prop="circuit_id" label="线路编号" width="130" />
        <el-table-column prop="bandwidth_mbps" label="带宽" width="90" align="center"><template #default="{ row }">{{ row.bandwidth_mbps }}M</template></el-table-column>
        <el-table-column label="续费周期" width="130" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="cycleTagType(row.renewal_cycle)">{{ cycleLabel(row.renewal_cycle) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="renewal_cost" label="周期费用" width="110" align="right">
          <template #default="{ row }">{{ row.renewal_cost != null ? row.renewal_cost.toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="annual_cost" label="年费" width="100" align="right"><template #default="{ row }">{{ row.annual_cost != null ? row.annual_cost.toFixed(0) : '-' }}</template></el-table-column>
        <el-table-column prop="location" label="位置" min-width="130" show-overflow-tooltip />
        <el-table-column prop="contract_end" label="到期日期" width="110" />
        <el-table-column label="剩余" width="80" align="center">
          <template #default="{ row }">
            <span :style="{ color: daysColor(row) }" v-if="row.status==='active'">{{ daysRemaining(row) }}天</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="contact_name" label="联系人" width="80" />
        <el-table-column prop="status" label="状态" width="75"><template #default="{ row }"><el-tag :type="statusMap[row.status]?.type" size="small">{{ statusMap[row.status]?.label }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="success" @click="testNotify(row)" :loading="row._notifying">通知</el-button>
            <el-button size="small" type="danger" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="prev,pager,next,total" :total="total" :page-size="query.size" v-model:current-page="query.page" @current-change="loadData" />
    </el-card>
    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dlg" :title="editId ? '编辑宽带合同' : '新增宽带合同'" width="720px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="运营商" prop="provider"><el-input v-model="form.provider" placeholder="中国电信/联通/移动" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="线路编号"><el-input v-model="form.circuit_id" placeholder="可选" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="带宽(Mbps)" prop="bandwidth_mbps"><el-input-number v-model="form.bandwidth_mbps" :min="1" style="width:100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="续费周期" prop="renewal_cycle">
            <el-select v-model="form.renewal_cycle" style="width:100%" @change="onCycleChange">
              <el-option label="每月" value="monthly" />
              <el-option label="每季度（3个月）" value="quarterly" />
              <el-option label="每半年（6个月）" value="semi_annual" />
              <el-option label="每年" value="annual" />
            </el-select>
          </el-form-item></el-col>
          <el-col :span="8"><el-form-item label="周期费用(元)">
            <el-input-number v-model="form.renewal_cost" :min="0" :precision="2" style="width:100%" @change="onCycleChange" />
          </el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="年费(元，自动)">
            <el-input-number v-model="form.annual_cost" :min="0" :precision="2" style="width:100%" />
            <div style="font-size:12px;color:#999;margin-top:4px">根据周期费用自动计算，可手动修改</div>
          </el-form-item></el-col>
          <el-col :span="12"><el-form-item label="位置"><el-input v-model="form.location" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="合同开始" prop="contract_start"><el-date-picker v-model="form.contract_start" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="合同到期" prop="contract_end"><el-date-picker v-model="form.contract_end" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="联系人"><el-input v-model="form.contact_name" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="联系电话"><el-input v-model="form.contact_phone" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="自动续费"><el-switch v-model="form.auto_renew" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="状态"><el-select v-model="form.status" style="width:100%"><el-option label="在用" value="active" /><el-option label="已过期" value="expired" /><el-option label="已取消" value="cancelled" /></el-select></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="月费(元)"><el-input-number v-model="form.monthly_cost" :min="0" :precision="2" style="width:100%" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="提醒天数">
          <el-select v-model="reminderDays" multiple placeholder="选择提醒天数" style="width:100%">
            <el-option v-for="d in [90,60,30,15,7,3,1]" :key="d" :label="`到期前 ${d} 天`" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dlg=false">取消</el-button><el-button type="primary" :loading="submitting" @click="submit">确定</el-button></template>
    </el-dialog>
    <!-- 导入对话框 -->
    <el-dialog v-model="importDlg" title="批量导入宽带合同" width="500px" :close-on-click-modal="false">
      <el-alert type="info" :closable="false" style="margin-bottom:16px">
        <template #title>
          请先<a href="#" @click.prevent="downloadTemplate" style="color:#409eff">下载模板</a>，
          按格式填写后上传 Excel 文件
        </template>
      </el-alert>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :show-file-list="true"
        :limit="1"
        accept=".xlsx,.xls"
        @change="onFileChange"
      >
        <template #trigger>
          <el-button type="primary">选择文件</el-button>
        </template>
        <span style="margin-left:12px;font-size:13px;color:#999">仅支持 .xlsx 格式</span>
      </el-upload>
      <div v-if="importResult" style="margin-top:16px">
        <el-alert
          :title="importResult.message"
          :type="importResult.errors?.length ? 'warning' : 'success'"
          :closable="false"
        />
        <div v-if="importResult.errors?.length" style="margin-top:8px;max-height:200px;overflow:auto">
          <p v-for="(e, i) in importResult.errors" :key="i" style="font-size:13px;color:#e6a23c;margin:2px 0">{{ e }}</p>
        </div>
      </div>
      <template #footer>
        <el-button @click="importDlg = false; importResult = null">关闭</el-button>
        <el-button type="primary" :loading="importing" :disabled="!selectedFile" @click="doImport">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ElUpload } from 'element-plus'
import { broadbandApi } from '@/api'

const loading = ref(false), submitting = ref(false), tableData = ref([]), total = ref(0), dlg = ref(false), editId = ref(null), formRef = ref(null)
const importDlg = ref(false), importing = ref(false), selectedFile = ref(null), importResult = ref(null)
const dashboard = reactive({ total: 0, active: 0, expired: 0, expiring_30d: 0, expiring_7d: 0, total_annual_cost: 0 })
const query = reactive({ keyword: '', status: '', page: 1, size: 20 })
const statusMap = { active: { label: '在用', type: 'success' }, expired: { label: '已过期', type: 'danger' }, cancelled: { label: '已取消', type: 'info' } }

const cycleMonths = { monthly: 1, quarterly: 3, semi_annual: 6, annual: 12 }
const cycleLabels = { monthly: '每月', quarterly: '每季度', semi_annual: '每半年', annual: '每年' }

function cycleLabel(cycle) { return cycleLabels[cycle] || '每年' }
function cycleTagType(cycle) {
  const map = { monthly: 'warning', quarterly: 'primary', semi_annual: 'success', annual: '' }
  return map[cycle] || ''
}

function calcAnnualFromCycle(cost, cycle) {
  if (cost == null || !cycle) return null
  const months = cycleMonths[cycle] || 12
  return Math.round(cost * (12 / months) * 100) / 100
}

function onCycleChange() {
  form.annual_cost = calcAnnualFromCycle(form.renewal_cost, form.renewal_cycle)
}

const defaultForm = { provider: '', circuit_id: '', bandwidth_mbps: 100, renewal_cycle: 'annual', renewal_cost: null, annual_cost: null, monthly_cost: null, location: '', contract_start: '', contract_end: '', auto_renew: false, contact_name: '', contact_phone: '', status: 'active', notes: '' }
const form = reactive({ ...defaultForm })
const reminderDays = ref([30, 15, 7])
const rules = {
  provider: [{ required: true, message: '请输入运营商' }],
  bandwidth_mbps: [{ required: true, message: '请输入带宽' }],
  contract_start: [{ required: true, message: '请选择合同开始日期' }],
  contract_end: [{ required: true, message: '请选择合同到期日期' }],
}

function daysRemaining(row) {
  const diff = Math.ceil((new Date(row.contract_end) - new Date()) / 86400000)
  return diff
}
function daysColor(row) {
  const d = daysRemaining(row)
  if (d <= 0) return '#f56c6c'
  if (d <= 7) return '#f56c6c'
  if (d <= 30) return '#e6a23c'
  return '#67c23a'
}

async function loadData() {
  loading.value = true
  try {
    const r = await broadbandApi.list(query)
    tableData.value = r.items.map(i => ({ ...i, _notifying: false }))
    total.value = r.total
    const d = await broadbandApi.dashboard()
    Object.assign(dashboard, d)
  } finally { loading.value = false }
}

function openCreate() {
  editId.value = null
  Object.assign(form, { ...defaultForm })
  reminderDays.value = [30, 15, 7]
  dlg.value = true
}
function openEdit(row) {
  editId.value = row.id
  Object.assign(form, { provider: row.provider, circuit_id: row.circuit_id || '', bandwidth_mbps: row.bandwidth_mbps, renewal_cycle: row.renewal_cycle || 'annual', renewal_cost: row.renewal_cost, annual_cost: row.annual_cost, monthly_cost: row.monthly_cost, location: row.location || '', contract_start: row.contract_start, contract_end: row.contract_end, auto_renew: row.auto_renew, contact_name: row.contact_name || '', contact_phone: row.contact_phone || '', status: row.status, notes: row.notes || '' })
  reminderDays.value = (row.reminder_days || '30,15,7').split(',').map(Number).filter(Boolean)
  dlg.value = true
}

async function submit() {
  await formRef.value.validate()
  form.reminder_days = reminderDays.value.join(',')
  submitting.value = true
  try {
    if (editId.value) { await broadbandApi.update(editId.value, form); ElMessage.success('已更新') }
    else { await broadbandApi.create(form); ElMessage.success('已创建') }
    dlg.value = false; loadData()
  } finally { submitting.value = false }
}

async function del(row) {
  await ElMessageBox.confirm('确定删除该合同?', '确认', { type: 'warning' })
  await broadbandApi.delete(row.id)
  ElMessage.success('已删除'); loadData()
}

async function testNotify(row) {
  row._notifying = true
  try {
    await broadbandApi.testNotify(row.id)
    ElMessage.success('通知已发送，请检查钉钉群')
  } catch (e) {
    ElMessage.error('发送失败')
  } finally { row._notifying = false }
}

// ── 导入导出 ──
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
  } catch (e) {
    ElMessage.error('模板下载失败')
  }
}

function onFileChange(uploadFile) {
  selectedFile.value = uploadFile.raw
  importResult.value = null
}

async function doImport() {
  if (!selectedFile.value) return ElMessage.warning('请先选择文件')
  importing.value = true
  try {
    const r = await broadbandApi.importExcel(selectedFile.value)
    importResult.value = r
    if (r.imported > 0) {
      ElMessage.success(`成功导入 ${r.imported} 条记录`)
      loadData()
    }
  } catch (e) {
    ElMessage.error('导入失败，请检查文件格式')
  } finally {
    importing.value = false
  }
}

onMounted(() => loadData())
</script>
