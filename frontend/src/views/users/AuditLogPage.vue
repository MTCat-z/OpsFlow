<template>
  <div>
    <el-card shadow="never">
      <template #header>
        <el-row justify="space-between" align="middle">
          <span style="font-weight:600">审计日志</span>
          <div>
            <el-select v-model="filter.action" placeholder="操作类型" clearable style="width:120px;margin-right:8px" @change="loadLogs">
              <el-option label="登录" value="login" />
              <el-option label="创建" value="create" />
              <el-option label="修改" value="update" />
              <el-option label="删除" value="delete" />
            </el-select>
            <el-select v-model="filter.resource_type" placeholder="资源类型" clearable style="width:130px;margin-right:8px" @change="loadLogs">
              <el-option label="用户" value="user" />
              <el-option label="资产" value="asset" />
              <el-option label="扫描任务" value="scan_task" />
              <el-option label="拓扑节点" value="topology_node" />
              <el-option label="认证" value="auth" />
            </el-select>
            <el-input v-model="filter.username" placeholder="用户名" clearable style="width:140px;margin-right:8px" @clear="loadLogs" @keyup.enter="loadLogs" />
            <el-button @click="loadLogs">查询</el-button>
          </div>
        </el-row>
      </template>
      <el-table v-loading="loading" :data="logs" stripe border>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="操作人" width="100" />
        <el-table-column prop="action" label="操作" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="actionType(row.action)">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resource_type" label="资源" width="100">
          <template #default="{ row }">{{ resourceLabel(row.resource_type) }}</template>
        </el-table-column>
        <el-table-column prop="detail" label="详情" min-width="300" show-overflow-tooltip />
        <el-table-column prop="ip_address" label="IP" width="130" />
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ row.created_at?.replace('T', ' ').substring(0, 19) }}</template>
        </el-table-column>
      </el-table>
      <div style="margin-top:12px;text-align:right">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadLogs"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { auditApi } from '@/api'

const loading = ref(false)
const logs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const filter = reactive({ action: '', resource_type: '', username: '' })

const actionMap = { login: '登录', logout: '登出', create: '创建', update: '修改', delete: '删除' }
const actionTypeMap = { login: 'success', logout: 'info', create: '', update: 'warning', delete: 'danger' }
const resourceMap = { user: '用户', asset: '资产', scan_task: '扫描任务', topology_node: '拓扑节点', auth: '认证' }

function actionLabel(a) { return actionMap[a] || a }
function actionType(a) { return actionTypeMap[a] || 'info' }
function resourceLabel(r) { return resourceMap[r] || r }

async function loadLogs() {
  loading.value = true
  try {
    const params = { page: page.value, size: pageSize }
    if (filter.action) params.action = filter.action
    if (filter.resource_type) params.resource_type = filter.resource_type
    if (filter.username) params.username = filter.username
    const r = await auditApi.list(params)
    logs.value = r.items || []
    total.value = r.total || 0
  } catch (_e) { /* handled by interceptor */ }
  finally { loading.value = false }
}

onMounted(loadLogs)
</script>
