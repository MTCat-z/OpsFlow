<template>
  <div class="panel-renderer">
    <!-- 数据源 error 优先展示（不视为 empty） -->
    <div v-if="data?.error" class="panel-error">{{ data.error }}</div>

    <!-- 空数据 -->
    <div v-else-if="isEmpty" class="empty">暂无数据</div>

    <!-- 折线图：Zabbix history -->
    <div v-else-if="chartType === 'line'" ref="chartRef" class="chart-box"></div>

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
      <div v-else class="empty">无活跃告警</div>
    </div>

    <div v-else class="empty">不支持的图表类型</div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  chartType: String,
  sourceType: String,
  data: Object,
})

const chartRef = ref(null)
let chartInstance = null
let resizeObserver = null
let echartsModule = null
// 防止并发初始化创建多个 echarts 实例（ResizeObserver / window resize / props.data 同时触发）
let initPromise = null

const isEmpty = computed(() => {
  if (!props.data) return true
  if (props.data.empty) return true
  if (props.chartType === 'line' && !props.data.series?.length) return true
  if (props.chartType === 'table' && !props.data.items?.length) return true
  if (props.chartType === 'stat' && !props.data.values) return true
  return false
})

function buildLineOption() {
  const series = props.data?.series || []
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 16, top: 16, bottom: 30 },
    xAxis: { type: 'time' },
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
}

function hasSize() {
  if (!chartRef.value) return false
  const r = chartRef.value.getBoundingClientRect()
  return r.width > 0 && r.height > 0
}

function disposeChart() {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
}

function setupObserver() {
  if (!chartRef.value || typeof ResizeObserver === 'undefined' || resizeObserver) return
  resizeObserver = new ResizeObserver(() => resizeChart())
  resizeObserver.observe(chartRef.value)
}

async function renderChart() {
  if (props.chartType !== 'line' || !chartRef.value || isEmpty.value) return
  await nextTick()
  // 已有初始化进行中 → 复用同一份 Promise，避免产生多个 echarts 实例
  if (initPromise) return initPromise
  initPromise = (async () => {
    if (!echartsModule) echartsModule = await import('echarts')
    // await 期间 props 可能已变化（如 chartType 切走），再次校验
    if (props.chartType !== 'line' || !chartRef.value || isEmpty.value) return
    // 容器尺寸还是 0 时（grid-item 仍在 transition）→ 等 ResizeObserver 触发再初始化
    if (!hasSize()) return
    if (!chartInstance) {
      chartInstance = echartsModule.init(chartRef.value)
    }
    chartInstance.setOption(buildLineOption(), true)
  })()
  try {
    await initPromise
  } finally {
    initPromise = null
  }
}

function resizeChart() {
  if (chartInstance) {
    // 容器尺寸恢复后再 resize，避免 0 尺寸导致图表缩没
    if (hasSize()) chartInstance.resize()
  } else if (props.chartType === 'line' && hasSize()) {
    // 之前因 0 尺寸跳过 init，现在尺寸可用了 → 重新渲染
    renderChart()
  }
}

watch(() => props.data, () => {
  if (props.chartType === 'line') renderChart()
}, { deep: true })

// chartType 切换时清理或恢复图表，防止非 line 类型下残留 echarts 实例和 ResizeObserver
watch(() => props.chartType, async (newType) => {
  if (newType !== 'line') {
    // 等待可能正在进行的初始化完成后再 dispose，避免 dispose 后又创建出孤立实例
    if (initPromise) await initPromise
    disposeChart()
  } else {
    await nextTick()
    setupObserver()
    await renderChart()
  }
})

onMounted(() => {
  if (props.chartType === 'line') {
    renderChart()
    setupObserver()
  }
  window.addEventListener('resize', resizeChart)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeChart)
  disposeChart()
})

defineExpose({ resize: resizeChart })

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
.panel-error {
  color: var(--el-color-danger);
  font-size: 13px;
  text-align: center;
  padding: 16px;
  word-break: break-all;
}
.chart-box { height: 100%; min-height: 200px; width: 100%; }
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
