<template>
  <div>
    <el-alert v-if="connStatus !== 'ok'" :type="connStatus === 'cached' ? 'warning' : 'error'" :closable="false" style="margin-bottom:12px" :title="connStatus === 'cached' ? '显示缓存数据' : 'Zabbix 不可达'" />
    <el-card shadow="never">
      <template #header><el-row justify="space-between" align="middle"><span>监控主机列表</span><el-button size="small" @click="loadData">刷新</el-button></el-row></template>
      <el-table v-loading="loading" :data="hosts" stripe border>
        <el-table-column prop="name" label="主机名" min-width="160" />
        <el-table-column prop="ip" label="IP" width="140" />
        <el-table-column prop="status" label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status==='active'?'success':'danger'" size="small">{{ row.status==='active'?'可用':'不可用' }}</el-tag></template></el-table-column>
        <el-table-column label="主机组" min-width="200"><template #default="{ row }"><el-tag v-for="g in (row.groups||[]).slice(0,3)" :key="g" size="small" style="margin:2px">{{ g }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="100"><template #default="{ row }"><el-button size="small" type="primary" @click="$router.push('/zabbix/hosts/' + row.host_id)">详情</el-button></template></el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { zabbixApi } from '@/api'
const loading = ref(false), hosts = ref([]), connStatus = ref('ok')
async function loadData() {
  loading.value = true
  try {
    const r = await zabbixApi.hosts({})
    connStatus.value = r.zabbix_status
    hosts.value = r.data || []
  } finally { loading.value = false }
}
onMounted(loadData)
</script>
