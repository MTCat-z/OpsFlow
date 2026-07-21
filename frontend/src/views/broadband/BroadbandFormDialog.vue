<template>
  <el-dialog v-model="visible" :title="editId ? '编辑宽带合同' : '新增宽带合同'" width="720px" destroy-on-close>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-row :gutter="16">
        <el-col :span="12"><el-form-item label="运营商" prop="provider"><el-input v-model="form.provider" placeholder="中国电信/联通/移动" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="线路编号"><el-input v-model="form.circuit_id" placeholder="可选" /></el-form-item></el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :span="8"><el-form-item label="带宽(Mbps)" prop="bandwidth_mbps"><el-input-number v-model="form.bandwidth_mbps" :min="1" style="width: 100%" /></el-form-item></el-col>
        <el-col :span="8">
          <el-form-item label="续费周期" prop="renewal_cycle">
            <el-select v-model="form.renewal_cycle" style="width: 100%" @change="onCycleChange">
              <el-option label="每月" value="monthly" />
              <el-option label="每季度（3个月）" value="quarterly" />
              <el-option label="每半年（6个月）" value="semi_annual" />
              <el-option label="每年" value="annual" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8"><el-form-item label="周期费用(元)"><el-input-number v-model="form.renewal_cost" :min="0" :precision="2" style="width: 100%" @change="onCycleChange" /></el-form-item></el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="年费(元，自动)">
            <el-input-number v-model="form.annual_cost" :min="0" :precision="2" style="width: 100%" />
            <div style="font-size: 12px; color: var(--ops-text-muted); margin-top: 4px">根据周期费用自动计算，可手动修改</div>
          </el-form-item>
        </el-col>
        <el-col :span="12"><el-form-item label="位置"><el-input v-model="form.location" /></el-form-item></el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :span="12"><el-form-item label="合同开始" prop="contract_start"><el-date-picker v-model="form.contract_start" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="合同到期" prop="contract_end"><el-date-picker v-model="form.contract_end" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item></el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :span="12"><el-form-item label="联系人"><el-input v-model="form.contact_name" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="联系电话"><el-input v-model="form.contact_phone" /></el-form-item></el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :span="8"><el-form-item label="自动续费"><el-switch v-model="form.auto_renew" /></el-form-item></el-col>
        <el-col :span="8">
          <el-form-item label="状态">
            <el-select v-model="form.status" style="width: 100%">
              <el-option label="在用" value="active" />
              <el-option label="已过期" value="expired" />
              <el-option label="已取消" value="cancelled" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8"><el-form-item label="月费(元)"><el-input-number v-model="form.monthly_cost" :min="0" :precision="2" style="width: 100%" /></el-form-item></el-col>
      </el-row>
      <el-form-item label="提醒天数">
        <el-select v-model="reminderDays" multiple placeholder="选择提醒天数" style="width: 100%">
          <el-option v-for="d in [90, 60, 30, 15, 7, 3, 1]" :key="d" :label="`到期前 ${d} 天`" :value="d" />
        </el-select>
      </el-form-item>
      <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive } from 'vue'

const CYCLE_MONTHS = { monthly: 1, quarterly: 3, semi_annual: 6, annual: 12 }
const DEFAULT_FORM = {
  provider: '', circuit_id: '', bandwidth_mbps: 100, renewal_cycle: 'annual',
  renewal_cost: null, annual_cost: null, monthly_cost: null, location: '',
  contract_start: '', contract_end: '', auto_renew: false,
  contact_name: '', contact_phone: '', status: 'active', notes: '',
}

const emit = defineEmits(['submit'])

const visible = ref(false)
const editId = ref(null)
const submitting = ref(false)
const formRef = ref(null)
const form = reactive({ ...DEFAULT_FORM })
const reminderDays = ref([30, 15, 7])

const rules = {
  provider: [{ required: true, message: '请输入运营商' }],
  bandwidth_mbps: [{ required: true, message: '请输入带宽' }],
  contract_start: [{ required: true, message: '请选择合同开始日期' }],
  contract_end: [{ required: true, message: '请选择合同到期日期' }],
}

function calcAnnualFromCycle(cost, cycle) {
  if (cost == null || !cycle) return null
  const months = CYCLE_MONTHS[cycle] || 12
  return Math.round((cost * (12 / months)) * 100) / 100
}

function onCycleChange() {
  form.annual_cost = calcAnnualFromCycle(form.renewal_cost, form.renewal_cycle)
}

function openCreate() {
  editId.value = null
  Object.assign(form, { ...DEFAULT_FORM })
  reminderDays.value = [30, 15, 7]
  visible.value = true
}

function openEdit(row) {
  editId.value = row.id
  Object.assign(form, {
    provider: row.provider, circuit_id: row.circuit_id || '', bandwidth_mbps: row.bandwidth_mbps,
    renewal_cycle: row.renewal_cycle || 'annual', renewal_cost: row.renewal_cost,
    annual_cost: row.annual_cost, monthly_cost: row.monthly_cost, location: row.location || '',
    contract_start: row.contract_start, contract_end: row.contract_end, auto_renew: row.auto_renew,
    contact_name: row.contact_name || '', contact_phone: row.contact_phone || '',
    status: row.status, notes: row.notes || '',
  })
  reminderDays.value = (row.reminder_days || '30,15,7').split(',').map(Number).filter(Boolean)
  visible.value = true
}

async function submit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    emit('submit', {
      id: editId.value,
      form: { ...form, reminder_days: reminderDays.value.join(',') },
    })
    visible.value = false
  } finally {
    submitting.value = false
  }
}

defineExpose({ openCreate, openEdit })
</script>
