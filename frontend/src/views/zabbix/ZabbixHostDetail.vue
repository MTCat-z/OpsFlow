<template>
  <div>
    <el-page-header style="margin-bottom:16px" @back="$router.push('/zabbix/hosts')"><template #content>主机详情 — {{ hostInfo.name || hostId }}</template></el-page-header>
    <el-alert v-if="connStatus !== 'ok'" :type="connStatus === 'cached' ? 'warning' : 'error'" :closable="false" style="margin-bottom:12px" :title="connStatus === 'cached' ? '显示缓存数据' : 'Zabbix 不可达'" />
    <el-alert v-if="loadError" type="error" :closable="false" style="margin-bottom:12px" :title="'数据加载失败: ' + loadError" />
    <!-- 主机信息 -->
    <el-card shadow="never" style="margin-bottom:16px">
      <el-descriptions :column="4" border>
        <el-descriptions-item label="主机名">{{ hostInfo.name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="Host">{{ hostInfo.host || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag :type="hostInfo.status==='active'?'success':'danger'" size="small">{{ hostInfo.status === 'active' ? '可用' : '不可用' }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="IP">{{ hostInfo.ip || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
    <!-- 时间选择 -->
    <el-row style="margin-bottom:12px"><el-radio-group v-model="period" size="small" @change="loadMetrics"><el-radio-button value="1h">1小时</el-radio-button><el-radio-button value="6h">6小时</el-radio-button><el-radio-button value="24h">24小时</el-radio-button><el-radio-button value="7d">7天</el-radio-button></el-radio-group></el-row>
    <!-- 指标图表 -->
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" style="margin-bottom:16px">
          <template #header>CPU 使用率 (%)</template>
          <div v-if="!hasCpuData" class="empty-chart">暂无 CPU 数据</div>
          <div v-else ref="cpuChart" style="height:200px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" style="margin-bottom:16px">
          <template #header>内存 (GB)</template>
          <div v-if="!hasMemData" class="empty-chart">暂无内存数据</div>
          <div v-else ref="memChart" style="height:200px"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { zabbixApi } from '@/api'

const route = useRoute()
const hostId = route.params.id
const period = ref('1h')
const connStatus = ref('ok')
const hostInfo = ref({})
const loadError = ref('')
const hasCpuData = ref(false)
const hasMemData = ref(false)
const cpuChart = ref(null), memChart = ref(null)
let cpuInstance = null, memInstance = null

async function loadHost() {
  try {
    const r = await zabbixApi.hostDetail(hostId)
    connStatus.value = r.zabbix_status
    hostInfo.value = r.data || {}
  } catch (e) {
    console.error('加载主机详情失败', e)
    loadError.value = '主机详情加载失败: ' + (e.message || e)
    connStatus.value = 'unavailable'
  }
}

async function loadMetrics() {
  loadError.value = ''
  try {
    const r = await zabbixApi.hostMetrics(hostId, { period: period.value })
    connStatus.value = r.zabbix_status
    const data = r.data || {}

    hasCpuData.value = Array.isArray(data.cpu) && data.cpu.length > 0
    hasMemData.value = Array.isArray(data.memory) && data.memory.length > 0

    await nextTick()
    if (hasCpuData.value || hasMemData.value) {
      await renderCharts(data)
    }
  } catch (e) {
    console.error('加载监控指标失败', e)
    loadError.value = '监控指标加载失败: ' + (e.message || e)
  }
}

async function renderCharts(data) {
  try {
    const echarts = await import('echarts')

    // CPU
    if (cpuChart.value && hasCpuData.value) {
      if (cpuInstance) cpuInstance.dispose()
      cpuInstance = echarts.init(cpuChart.value)
      cpuInstance.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'time' },
        yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
        series: [{ type: 'line', data: (data.cpu || []).map(p => [p.t * 1000, p.v]), areaStyle: { opacity: 0.3 }, smooth: true, lineStyle: { width: 1.5 } }],
        grid: { top: 10, bottom: 30, left: 50, right: 20 },
      })
    }
    // Memory
    if (memChart.value && hasMemData.value) {
      if (memInstance) memInstance.dispose()
      memInstance = echarts.init(memChart.value)
      memInstance.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'time' },
        yAxis: { type: 'value', axisLabel: { formatter: '{value} GB' } },
        series: [{ type: 'line', data: (data.memory || []).map(p => [p.t * 1000, p.v]), areaStyle: { opacity: 0.3 }, smooth: true, lineStyle: { width: 1.5 } }],
        grid: { top: 10, bottom: 30, left: 50, right: 20 },
      })
    }
  } catch (e) {
    console.error('图表渲染失败', e)
    loadError.value = '图表渲染失败: ' + (e.message || e)
  }
}

function handleResize() { cpuInstance?.resize(); memInstance?.resize() }
onMounted(async () => {
  await loadHost()
  await loadMetrics()
  window.addEventListener('resize', handleResize)
})
onUnmounted(() => { window.removeEventListener('resize', handleResize); cpuInstance?.dispose(); memInstance?.dispose() })
</script>
<style scoped>
.empty-chart {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  font-size: 14px;
  background: #fafafa;
  border-radius: 4px;
}
</style>
