<template>
  <div>
    <el-card shadow="never" style="margin-bottom:16px">
      <el-row :gutter="12" align="middle">
        <el-col :span="6"><el-input v-model="query.keyword" placeholder="搜索名称/IP/位置" clearable @change="loadData" /></el-col>
        <el-col :span="4"><el-select v-model="query.device_type" placeholder="设备类型" clearable @change="loadData"><el-option v-for="t in deviceTypes" :key="t.value" :label="t.label" :value="t.value" /></el-select></el-col>
        <el-col :span="4"><el-select v-model="query.status" placeholder="状态" clearable @change="loadData"><el-option label="在用" value="active" /><el-option label="停用" value="inactive" /></el-select></el-col>
        <el-col :span="10" style="text-align:right"><el-button v-if="authStore.isOrgAdmin" type="primary" @click="openCreate">新增资产</el-button><el-button @click="assetApi.export()">导出Excel</el-button></el-col>
      </el-row>
    </el-card>
    <el-card shadow="never">
      <el-table v-loading="loading" :data="tableData" stripe border>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="设备名称" min-width="140" />
        <el-table-column prop="ip_address" label="IP地址" width="140" />
        <el-table-column prop="device_type" label="类型" width="100" />
        <el-table-column prop="location" label="位置" min-width="120" />
        <el-table-column prop="owner" label="负责人" width="100" />
        <el-table-column prop="status" label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status==='active'?'success':'info'">{{ row.status==='active'?'在用':'停用' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button v-if="authStore.isAdmin" size="small" @click="viewCred(row)">账号</el-button>
            <el-button size="small" type="success" @click="openTerminal(row)">终端</el-button>
            <el-button v-if="authStore.isOrgAdmin" size="small" type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="authStore.isOrgAdmin" size="small" type="danger" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="query.page" v-model:page-size="query.size" :total="total" layout="total,prev,pager,next" style="margin-top:16px;text-align:right" @change="loadData" />
    </el-card>
    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dlg" :title="editId?'编辑资产':'新增资产'" width="680px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="设备名称" prop="name"><el-input v-model="form.name" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="IP地址" prop="ip_address"><el-input v-model="form.ip_address" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="设备类型"><el-select v-model="form.device_type" style="width:100%"><el-option v-for="t in deviceTypes" :key="t.value" :label="t.label" :value="t.value" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="位置"><el-input v-model="form.location" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="负责人"><el-input v-model="form.owner" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="协议"><el-select v-model="form.protocol" style="width:100%"><el-option label="SSH" value="ssh" /><el-option label="Telnet" value="telnet" /></el-select></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="端口"><el-input-number v-model="form.ssh_port" :min="1" :max="65535" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="认证方式"><el-select v-model="form.auth_type" style="width:100%"><el-option label="密码认证" value="password" /><el-option label="密钥认证" value="key" /><el-option label="密码+密钥" value="both" /></el-select></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="密码"><el-input v-model="form.password" type="password" show-password /></el-form-item></el-col>
        </el-row>
        <el-form-item v-if="form.auth_type !== 'password'" label="SSH 私钥">
          <el-input v-model="form.ssh_private_key" type="textarea" :rows="5" placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;...&#10;-----END RSA PRIVATE KEY-----" style="font-family:monospace;font-size:12px" />
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="dlg=false">取消</el-button><el-button type="primary" :loading="submitting" @click="submit">确定</el-button></template>
    </el-dialog>
    <!-- 凭据查看对话框 -->
    <el-dialog v-model="credDlg" title="账号信息" width="480px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="认证方式">{{ authTypeLabel }}</el-descriptions-item>
        <el-descriptions-item label="用户名">{{ cred.username || '-' }}</el-descriptions-item>
        <el-descriptions-item v-if="cred.auth_type !== 'key'" label="密码">
          <span style="font-family:monospace">{{ showPwd ? cred.password : '••••••••' }}</span>
          <el-button size="small" style="margin-left:8px" @click="showPwd=!showPwd">{{ showPwd ? '隐藏' : '显示' }}</el-button>
        </el-descriptions-item>
        <el-descriptions-item label="SSH 私钥">
          <el-tag v-if="cred.ssh_private_key" type="success" size="small">已配置</el-tag>
          <span v-else style="color:var(--ops-text-muted)">未配置</span>
          <el-button v-if="cred.ssh_private_key" size="small" style="margin-left:8px" @click="showKey=!showKey">{{ showKey ? '隐藏' : '查看' }}</el-button>
          <pre v-if="showKey && cred.ssh_private_key" style="margin-top:8px;font-size:11px;max-height:200px;overflow:auto;background:var(--ops-bg-elevated);padding:8px;border-radius:4px">{{ cred.ssh_private_key }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>
<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { assetApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const loading = ref(false), submitting = ref(false), tableData = ref([]), total = ref(0)
const dlg = ref(false), credDlg = ref(false), editId = ref(null), formRef = ref(null)
const showPwd = ref(false), showKey = ref(false), cred = ref({})
const query = reactive({ keyword: '', device_type: '', status: '', page: 1, size: 20 })
const deviceTypes = [{ label: '服务器', value: 'server' }, { label: '交换机', value: 'switch' }, { label: '路由器', value: 'router' }, { label: '防火墙', value: 'firewall' }, { label: '其他', value: 'other' }]
const rules = { name: [{ required: true, message: '请输入设备名称' }], ip_address: [{ required: true, message: '请输入IP地址' }] }

const defaultForm = { name: '', ip_address: '', device_type: 'server', location: '', owner: '', username: '', password: '', protocol: 'ssh', ssh_port: 22, auth_type: 'password', ssh_private_key: '' }
const form = reactive({ ...defaultForm })

const authTypeLabel = computed(() => {
  const map = { password: '密码认证', key: '密钥认证', both: '密码+密钥' }
  return map[cred.value.auth_type] || '密码认证'
})

async function loadData() { loading.value = true; try { const r = await assetApi.list(query); tableData.value = r.items; total.value = r.total } finally { loading.value = false } }
function openCreate() { editId.value = null; Object.assign(form, { ...defaultForm }); dlg.value = true }
function openEdit(row) {
  editId.value = row.id
  Object.assign(form, { name: row.name, ip_address: row.ip_address, device_type: row.device_type || 'server', location: row.location || '', owner: row.owner || '', username: '', password: '', protocol: row.protocol || 'ssh', ssh_port: row.ssh_port || 22, auth_type: row.auth_type || 'password', ssh_private_key: '' })
  dlg.value = true
}
async function submit() {
  await formRef.value.validate(); submitting.value = true
  try {
    if (editId.value) { await assetApi.update(editId.value, form) } else { await assetApi.create(form) }
    ElMessage.success('操作成功'); dlg.value = false; loadData()
  } finally { submitting.value = false }
}
async function del(row) { await ElMessageBox.confirm('确定删除?', '确认', { type: 'warning' }); await assetApi.delete(row.id); ElMessage.success('已删除'); loadData() }
async function viewCred(row) { showPwd.value = false; showKey.value = false; cred.value = await assetApi.getCredentials(row.id); credDlg.value = true }
function openTerminal(row) { window.open(`/terminal/${row.id}`, '_blank') }
onMounted(loadData)
</script>
