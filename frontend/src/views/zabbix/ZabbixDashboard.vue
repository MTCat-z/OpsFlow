<template>
  <div>
    <!-- 状态横幅 -->
    <el-alert v-if="connStatus === 'unavailable'" type="error" :closable="false" style="margin-bottom:12px" title="Zabbix 服务不可达" description="请在 .env 中配置 ZABBIX_URL 和 ZABBIX_API_TOKEN" />
    <el-alert v-if="connStatus === 'cached'" type="warning" :closable="false" style="margin-bottom:12px" title="Zabbix 连接异常，显示缓存数据" />
    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="6"><el-card shadow="never"><el-statistic title="监控主机" :value="dashboard.total_hosts" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="never"><el-statistic title="问题主机" :value="dashboard.problem_host_count" :value-style="{ color: dashboard.problem_host_count > 0 ? '#f56c6c' : '#67c23a' }" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="never"><el-statistic title="严重告警" :value="dashboard.problems_by_severity?.critical || 0" :value-style="{ color: (dashboard.problems_by_severity?.critical || 0) > 0 ? '#f56c6c' : '#67c23a' }" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="never"><el-statistic title="总问题数" :value="dashboard.total_problems" /></el-card></el-col>
    </el-row>
    <!-- 问题列表 -->
    <el-card shadow="never" style="margin-bottom:16px">
      <template #header><el-row justify="space-between" align="middle"><span>活跃问题</span><el-button size="small" @click="loadData">刷新</el-button></el-row></template>
      <el-table v-loading="loading" :data="problems" stripe border max-height="360">
        <el-table-column label="严重级别" width="100"><template #default="{ row }"><el-tag :type="severityType(row.severity)" size="small">{{ severityLabel(row.severity) }}</el-tag></template></el-table-column>
        <el-table-column prop="name" label="问题名称" min-width="300" show-overflow-tooltip />
        <el-table-column prop="clock" label="时间" width="160"><template #default="{ row }">{{ formatTime(row.clock) }}</template></el-table-column>
        <el-table-column label="已确认" width="80" align="center"><template #default="{ row }">{{ row.acknowledged ? '是' : '否' }}</template></el-table-column>
      </el-table>
    </el-card>
    <!-- 主机入口 -->
    <el-card shadow="never">
      <template #header><span>快捷入口</span></template>
      <el-row :gutter="16">
        <el-col :span="8"><el-button style="width:100%" @click="$router.push('/zabbix/hosts')">查看监控主机</el-button></el-col>
        <el-col :span="8"><el-button style="width:100%" @click="clearZabbixCache">清除缓存</el-button></el-col>
      </el-row>
    </el-card>
  </div>
</template>
<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { zabbixApi } from '@/api'

const loading = ref(false), connStatus = ref('ok')
const dashboard = reactive({ total_hosts: 0, active_hosts: 0, total_problems: 0, problem_host_count: 0, problems_by_severity: {} })
const problems = ref([])

const severityMap = { 0: '未分类', 1: '信息', 2: '警告', 3: '一般', 4: '严重', 5: '灾难' }
const severityTypeMap = { 0: 'info', 1: 'info', 2: 'warning', 3: 'warning', 4: 'danger', 5: 'danger' }
function severityLabel(s) { return severityMap[s] || '未分类' }
function severityType(s) { return severityTypeMap[s] || 'info' }
function formatTime(ts) { if (!ts) return '-'; const d = new Date(parseInt(ts) * 1000); return d.toLocaleString('zh-CN') }

async function loadData() {
  loading.value = true
  try {
    const status = await zabbixApi.status()
    connStatus.value = status.available ? 'ok' : 'unavailable'
    if (!status.available) { loading.value = false; return }
    const d = await zabbixApi.dashboard()
    connStatus.value = d.zabbix_status
    if (d.data) Object.assign(dashboard, d.data)
    const p = await zabbixApi.problems()
    connStatus.value = p.zabbix_status
    problems.value = p.data || []
  } catch (_e) { connStatus.value = 'unavailable' }
  finally { loading.value = false }
}

async function clearZabbixCache() { await zabbixApi.clearCache(); ElMessage.success('缓存已清除'); loadData() }

let timer = null
onMounted(() => { loadData(); timer = setInterval(loadData, 30000) })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>
