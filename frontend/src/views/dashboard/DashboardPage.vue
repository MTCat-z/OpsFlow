<template>
  <div class="dashboard-page">
    <el-row :gutter="12" class="summary-grid">
      <el-col v-for="item in cards" :key="item.label" :xs="12" :sm="8" :md="6" :lg="4">
        <el-card shadow="never" class="summary-card">
          <div class="summary-card__label">{{ item.label }}</div>
          <div class="summary-card__value">{{ item.value }}</div>
          <div class="summary-card__note">{{ item.note }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header>网络与资产</template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="在用资产">{{ data.assets?.active || 0 }}</el-descriptions-item>
            <el-descriptions-item label="拓扑节点">{{ data.network_tasks?.topology_nodes || 0 }}</el-descriptions-item>
            <el-descriptions-item label="扫描任务">{{ data.network_tasks?.scans || 0 }}</el-descriptions-item>
            <el-descriptions-item label="测速任务">{{ data.network_tasks?.iperf || 0 }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header>自动化与风险</template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="巡检异常">{{ data.inspection?.exceptions || 0 }}</el-descriptions-item>
            <el-descriptions-item label="IP 冲突">{{ data.ipam?.conflicts || 0 }}</el-descriptions-item>
            <el-descriptions-item label="30 天到期宽带">{{ data.broadband?.expiring_30d || 0 }}</el-descriptions-item>
            <el-descriptions-item label="配置快照">{{ data.automation?.config_snapshots || 0 }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <!-- 资产类型分布 -->
      <el-col :xs="24" :lg="8">
        <el-card shadow="never">
          <template #header>资产类型分布</template>
          <div ref="chartRef" style="height: 260px" />
        </el-card>
      </el-col>

      <!-- 宽带到期倒计时 -->
      <el-col :xs="24" :lg="8">
        <el-card shadow="never">
          <template #header>宽带到期倒计时</template>
          <el-table v-if="expiringList.length" :data="expiringList" size="small" stripe>
            <el-table-column prop="provider" label="运营商" width="80" />
            <el-table-column prop="circuit_id" label="线路" min-width="100" show-overflow-tooltip />
            <el-table-column prop="next_renewal_deadline" label="续费日" width="100" />
            <el-table-column label="剩余" width="70" align="center">
              <template #default="{ row }">
                <span :style="{ color: row.next_renewal_days <= 7 ? 'var(--ops-danger)' : row.next_renewal_days <= 15 ? 'var(--ops-warning)' : 'var(--ops-success)' }">{{ row.next_renewal_days }}天</span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="无即将到期的宽带" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 最近巡检 -->
      <el-col :xs="24" :lg="8">
        <el-card shadow="never">
          <template #header>最近巡检</template>
          <el-timeline v-if="recentRuns.length">
            <el-timeline-item v-for="r in recentRuns" :key="r.id" :timestamp="r.created_at ? r.created_at.replace('T', ' ').slice(0, 16) : ''" placement="top" :type="r.status === 'completed' ? (r.exception_count > 0 ? 'warning' : 'success') : 'danger'">
              <div style="font-size: 13px">
                <span>{{ r.summary || r.status }}</span>
                <el-tag v-if="r.exception_count" type="danger" size="small" style="margin-left: 4px">{{ r.exception_count }} 异常</el-tag>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无巡检记录" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, nextTick } from 'vue'
import { dashboardApi } from '@/api'

const data = ref({})
const chartRef = ref(null)
let chartInstance = null
let pollTimer = null

const cards = computed(() => [
  { label: '资产总数', value: data.value.assets?.total || 0, note: '纳管设备' },
  { label: '扫描任务', value: data.value.network_tasks?.scans || 0, note: `${data.value.network_tasks?.scan_running || 0} 个运行中` },
  { label: '宽带合同', value: data.value.broadband?.contracts || 0, note: `${data.value.broadband?.expiring_renewal_30d || 0} 个 30 天内到期` },
  { label: '巡检方案', value: data.value.inspection?.plans || 0, note: `${data.value.inspection?.enabled_plans || 0} 个启用` },
  { label: 'IPAM 子网', value: data.value.ipam?.subnets || 0, note: `${data.value.ipam?.addresses || 0} 个地址记录` },
  { label: '批量命令', value: data.value.automation?.command_batches || 0, note: '执行批次' },
])

const expiringList = computed(() => data.value.broadband?.expiring_renewal_list || [])
const recentRuns = computed(() => data.value.inspection?.recent_runs || [])

async function loadData() {
  data.value = await dashboardApi.overview()
  await nextTick()
  renderChart()
}

async function renderChart() {
  if (!chartRef.value) return
  const types = data.value.asset_types || {}
  const entries = Object.entries(types)
  if (!entries.length) return

  try {
    const echarts = await import('echarts')
    if (!chartInstance) {
      chartInstance = echarts.init(chartRef.value)
    }
    chartInstance.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        label: { formatter: '{b}\n{c}' },
        data: entries.map(([name, value]) => ({ name, value })),
      }],
    })
  } catch {
    // ECharts not available
  }
}

function handleResize() {
  chartInstance?.resize()
}

function startPolling() {
  pollTimer = setInterval(loadData, 60000)
}

onMounted(() => {
  loadData()
  startPolling()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  chartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.summary-grid {
  row-gap: 12px;
}

.summary-card {
  min-height: 112px;
}

.summary-card__label {
  color: var(--ops-text-secondary);
  font-size: 13px;
}

.summary-card__value {
  color: var(--ops-text-primary);
  font-size: 28px;
  font-weight: 700;
  line-height: 42px;
}

.summary-card__note {
  color: var(--ops-text-muted);
  font-size: 12px;
}
</style>
