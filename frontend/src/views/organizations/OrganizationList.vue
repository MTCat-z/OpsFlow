<template>
  <div>
    <!-- 统计卡片 -->
    <StatCards :items="statItems" />
    <!-- 筛选 + 表格 -->
    <el-card shadow="never">
      <template #header>
        <el-row justify="space-between" align="middle">
          <el-form :model="query" inline>
            <el-form-item>
              <el-input v-model="query.keyword" placeholder="组织名称/编码" clearable style="width: 200px" @clear="loadData" @keyup.enter="loadData" />
            </el-form-item>
            <el-form-item>
              <el-select v-model="query.is_active" clearable placeholder="状态" style="width: 120px" @change="loadData">
                <el-option label="活跃" :value="true" />
                <el-option label="禁用" :value="false" />
              </el-select>
            </el-form-item>
            <el-form-item><el-button type="primary" @click="loadData">搜索</el-button></el-form-item>
          </el-form>
          <el-button type="primary" @click="showCreate">新增组织</el-button>
        </el-row>
      </template>
      <el-table v-loading="loading" :data="tableData" stripe border>
        <el-table-column prop="name" label="组织名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="code" label="编码" width="130" />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <StatusTag :value="row.is_active ? 'active' : 'inactive'" :status-map="statusMap" />
          </template>
        </el-table-column>
        <el-table-column prop="user_count" label="用户数" width="90" align="center" sortable />
        <el-table-column prop="asset_count" label="资产数" width="90" align="center" sortable />
        <el-table-column label="探针状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.probe_key" size="small" :type="row.probe_online ? 'success' : 'danger'">
              {{ row.probe_online ? '在线' : '离线' }}
            </el-tag>
            <el-tag v-else size="small" type="info">未配置</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="钉钉配置" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.dingtalk_webhook ? 'success' : 'info'">{{ row.dingtalk_webhook ? '已配置' : '未配置' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Zabbix配置" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.zabbix_url ? 'success' : 'info'">{{ row.zabbix_url ? '已配置' : '未配置' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ row.created_at?.replace('T', ' ').substring(0, 19) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="360" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="showEdit(row)">编辑</el-button>
            <el-button size="small" type="warning" @click="generateProbe(row)">生成探针</el-button>
            <el-button size="small" type="success" @click="downloadProbeConfig(row)" :disabled="!row.probe_key">下载配置</el-button>
            <el-button size="small" type="danger" @click="clearProbe(row)" :disabled="!row.probe_key">清理探针</el-button>
            <el-button size="small" type="danger" plain @click="del(row)">删除</el-button>
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

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dlgVisible" :title="isEdit ? '编辑组织' : '新增组织'" width="520px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="组织名称">
          <el-input v-model="form.name" placeholder="请输入组织名称" />
        </el-form-item>
        <el-form-item label="组织编码">
          <el-input v-model="form.code" placeholder="唯一编码，如 ORG001" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="钉钉 Webhook">
          <el-input v-model="form.dingtalk_webhook" placeholder="钉钉机器人 Webhook 地址" />
        </el-form-item>
        <el-form-item label="钉钉 Secret">
          <el-input v-model="form.dingtalk_secret" placeholder="加签密钥（可选）" show-password />
        </el-form-item>
        <el-form-item label="Zabbix URL">
          <el-input v-model="form.zabbix_url" placeholder="Zabbix API 地址" />
        </el-form-item>
        <el-form-item label="Zabbix Token">
          <el-input v-model="form.zabbix_token" placeholder="Zabbix API Token" show-password />
        </el-form-item>
        <el-form-item v-if="isEdit" label="状态">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlgVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { organizationApi } from '@/api'
import StatCards from '@/components/common/StatCards.vue'
import StatusTag from '@/components/common/StatusTag.vue'

const loading = ref(false)
const submitting = ref(false)
const tableData = ref([])
const total = ref(0)
const allOrgs = ref([])

const query = reactive({ keyword: '', is_active: '', page: 1, size: 20 })

const statusMap = {
  active: { label: '活跃', type: 'success' },
  inactive: { label: '禁用', type: 'info' },
}

const statItems = computed(() => {
  const orgs = allOrgs.value
  return [
    { title: '组织总数', value: orgs.length },
    { title: '活跃组织', value: orgs.filter((o) => o.is_active).length },
    { title: '总用户数', value: orgs.reduce((s, o) => s + (o.user_count || 0), 0) },
    { title: '总资产数', value: orgs.reduce((s, o) => s + (o.asset_count || 0), 0) },
  ]
})

const dlgVisible = ref(false)
const isEdit = ref(false)
const editingId = ref(null)
const form = reactive({
  name: '',
  code: '',
  dingtalk_webhook: '',
  dingtalk_secret: '',
  zabbix_url: '',
  zabbix_token: '',
  is_active: true,
})

async function loadData() {
  loading.value = true
  try {
    const r = await organizationApi.list(query)
    tableData.value = r.items || []
    total.value = r.total || 0
    const all = await organizationApi.all()
    allOrgs.value = Array.isArray(all) ? all : (all.items || [])
  } finally {
    loading.value = false
  }
}

function showCreate() {
  isEdit.value = false
  editingId.value = null
  Object.assign(form, {
    name: '',
    code: '',
    dingtalk_webhook: '',
    dingtalk_secret: '',
    zabbix_url: '',
    zabbix_token: '',
    is_active: true,
  })
  dlgVisible.value = true
}

function showEdit(row) {
  isEdit.value = true
  editingId.value = row.id
  Object.assign(form, {
    name: row.name || '',
    code: row.code || '',
    dingtalk_webhook: row.dingtalk_webhook || '',
    dingtalk_secret: row.dingtalk_secret || '',
    zabbix_url: row.zabbix_url || '',
    zabbix_token: row.zabbix_token || '',
    is_active: row.is_active,
  })
  dlgVisible.value = true
}

async function handleSubmit() {
  if (!form.name) return ElMessage.warning('请输入组织名称')
  if (!form.code) return ElMessage.warning('请输入组织编码')
  submitting.value = true
  try {
    if (isEdit.value) {
      await organizationApi.update(editingId.value, { ...form })
      ElMessage.success('组织已更新')
    } else {
      await organizationApi.create({ ...form })
      ElMessage.success('组织已创建')
    }
    dlgVisible.value = false
    loadData()
  } finally {
    submitting.value = false
  }
}

async function del(row) {
  await ElMessageBox.confirm(`确定删除组织「${row.name}」?`, '确认', { type: 'warning' })
  await organizationApi.delete(row.id)
  ElMessage.success('已删除')
  loadData()
}

async function generateProbe(row) {
  try {
    await ElMessageBox.confirm(
      `为「${row.name}」生成探针配置？\n将自动生成 VPN 密钥和认证密钥。`,
      '生成探针配置',
      { type: 'warning', confirmButtonText: '生成', cancelButtonText: '取消' }
    )
  } catch (_e) {
    return
  }
  try {
    const r = await organizationApi.generateProbe(row.id)
    ElMessageBox.alert(
      `探针配置已生成！\n\n` +
      `组织编码: ${r.org_code}\n` +
      `探针密钥: ${r.probe_key}\n` +
      `隧道 IP: ${r.wg_tunnel_ip}\n\n` +
      `请点击"下载配置"获取部署包，发给分公司 IT 人员。`,
      '生成成功',
      { type: 'success' }
    )
    loadData()
  } catch (e) {
    ElMessage.error('生成失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
}

async function clearProbe(row) {
  try {
    await ElMessageBox.confirm(
      `确认清理「${row.name}」的探针配置？\n\n` +
      `将执行以下操作：\n` +
      `• 移除中心服务器的 WireGuard peer\n` +
      `• 清空探针密钥、VPN 密钥、隧道 IP、心跳记录\n` +
      `• 该组织回到「未配置探针」状态\n\n` +
      `历史扫描/测速任务记录会保留。\n` +
      `分公司探针容器需手动停止（docker compose down）。`,
      '清理探针配置',
      { type: 'warning', confirmButtonText: '确认清理', cancelButtonText: '取消' }
    )
  } catch (_e) {
    return
  }
  try {
    await organizationApi.clearProbe(row.id)
    ElMessage.success('探针配置已清理')
    loadData()
  } catch (e) {
    ElMessage.error('清理失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
}

async function downloadProbeConfig(row) {
  try {
    const blob = await organizationApi.downloadProbeConfig(row.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `deploy-probe-${row.code}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('配置包已下载')
  } catch (e) {
    ElMessage.error('下载失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'))
  }
}

onMounted(() => loadData())
</script>
