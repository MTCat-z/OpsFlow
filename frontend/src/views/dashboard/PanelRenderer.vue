<template>
  <div class="panel-renderer">
    <!-- 空数据 -->
    <div v-if="isEmpty" class="empty">暂无数据</div>

    <!-- 折线图：Zabbix history -->
    <div v-else-if="chartType === 'line'" class="chart-box">
      <v-chart :option="lineOption" autoresize style="height: 100%; width: 100%" />
    </div>

    <!-- 数值卡：iperf / scan / probe -->
    <div v-else-if="chartType === 'stat'" class="stat-box">
      <template v-if="sourceType === 'iperf_recent'">
        <div class="stat-grid">
          <div class="stat-item">
            <div class="stat-label">带宽</div>
            <div class="stat-value">{{ fmt(data?.values?.bandwidth_mbps) }}<span class="unit">Mbps</span></div>
          </div>
          <div class="stat-item">
            <div class="stat-label">抖动</div>
            <div class="stat-value">{{ fmt(data?.values?.jitter_ms) }}<span class="unit">ms</span></div>
          </div>
          <div class="stat-item">
            <div class="stat-label">丢包</div>
            <div class="stat-value">{{ fmt(data?.values?.lost_percent) }}<span class="unit">%</span></div>
          </div>
          <div class="stat-item">
            <div class="stat-label">重传</div>
            <div class="stat-value">{{ fmt(data?.values?.retransmits) }}</div>
          </div>
        </div>
        <div v-if="data?.finished_at" class="stat-note">{{ data.server_host }} · {{ data.protocol }} · {{ formatTime(data.finished_at) }}</div>
      </template>
      <template v-else-if="sourceType === 'scan_recent'">
        <div class="stat-grid">
          <div class="stat-item">
            <div class="stat-label">发现主机</div>
            <div class="stat-value">{{ data?.values?.host_count ?? '—' }}</div>
          </div>
          <div class="stat-item">
            <div class="stat-label">开放端口</div>
            <div class="stat-value">{{ data?.values?.port_count ?? '—' }}</div>
          </div>
        </div>
        <div v-if="data?.finished_at" class="stat-note">{{ data.target }} · {{ formatTime(data.finished_at) }}</div>
      </template>
      <template v-else-if="sourceType === 'probe_status'">
        <div class="stat-grid">
          <div class="stat-item">
            <div class="stat-label">探针状态</div>
            <div class="stat-value" :class="data?.values?.online ? 'ok' : 'bad'">
              {{ data?.values?.online ? '在线' : (data?.values?.configured ? '离线' : '未配置') }}
            </div>
          </div>
        </div>
        <div v-if="data?.probe_last_heartbeat" class="stat-note">心跳: {{ formatTime(data.probe_last_heartbeat) }} · {{ data.wg_tunnel_ip || '—' }}</div>
      </template>
    </div>

    <!-- 表格：Zabbix 告警 -->
    <div v-else-if="chartType === 'table'" class="table-box">
      <el-table v-if="data?.items?.length" :data="data.items" size="small" border style="width: 100%" max-height="300">
        <el-table-column prop="name" label="告警" min-width="200" show-overflow-tooltip />
        <el-table-column label="级别" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="severityType(row.severity)">{{ severityLabel(row.severity) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ formatTime(row.clock) }}</template>
        </el-table-column>
      </el-table>
      <div v-else class="empty">{{ data?.error || '无活跃告警' }}</div>
    </div>

    <div v-else class="empty">不支持的图表类型</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, TitleComponent])

const props = defineProps({
  chartType: String,
  sourceType: String,
  data: Object,
})

const isEmpty = computed(() => {
  if (!props.data) return true
  if (props.data.empty) return true
  if (props.chartType === 'line' && !props.data.series?.length) return true
  if (props.chartType === 'table' && !props.data.items?.length) return true
  if (props.chartType === 'stat' && !props.data.values) return true
  return false
})

const lineOption = computed(() => {
  const series = props.data?.series || []
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 16, top: 16, bottom: 30 },
    xAxis: {
      type: 'time',
    },
    yAxis: { type: 'value', scale: true },
    series: [{
      type: 'line',
      showSymbol: false,
      data: series.map((p) => [p.t * 1000, p.v]),
      name: props.data?.item_name || '',
      lineStyle: { width: 2 },
      areaStyle: { opacity: 0.1 },
    }],
  }
})

function fmt(v) {
  if (v === null || v === undefined) return '—'
  return Number.isFinite(v) ? v.toFixed(2).replace(/\.?0+$/, '') : v
}

function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const SEVERITY = [
  { label: '未分类', type: 'info' },
  { label: '信息', type: 'info' },
  { label: '警告', type: 'warning' },
  { label: '一般严重', type: 'warning' },
  { label: '严重', type: 'danger' },
  { label: '灾难', type: 'danger' },
]
function severityLabel(s) {
  return SEVERITY[s]?.label || '未知'
}
function severityType(s) {
  return SEVERITY[s]?.type || 'info'
}
</script>

<style scoped>
.panel-renderer { width: 100%; height: 100%; }
.empty {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  text-align: center;
  padding: 20px;
}
.chart-box { height: 100%; min-height: 200px; }
.stat-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  width: 100%;
}
.stat-grid {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 16px 24px;
  width: 100%;
}
.stat-item { text-align: center; }
.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  font-family: var(--ops-font-mono, 'Consolas', monospace);
}
.stat-value .unit {
  font-size: 12px;
  font-weight: 400;
  margin-left: 4px;
  color: var(--el-text-color-secondary);
}
.stat-value.ok { color: var(--el-color-success); }
.stat-value.bad { color: var(--el-color-danger); }
.stat-note {
  margin-top: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.table-box { width: 100%; }
</style>
