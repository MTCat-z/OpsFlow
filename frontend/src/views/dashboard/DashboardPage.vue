<template>
  <div class="dashboard-page">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <span class="title">运维大屏</span>
        <el-select v-if="auth.isAdmin" v-model="selectedOrgId" placeholder="选择组织" size="small" style="width: 200px; margin-left: 16px" @change="onOrgChange">
          <el-option v-for="o in orgOptions" :key="o.id" :label="o.name" :value="o.id" />
        </el-select>
        <el-tag v-else size="small" style="margin-left: 16px">{{ currentOrgName }}</el-tag>
      </div>
      <div class="toolbar-right">
        <el-switch v-model="editMode" active-text="编辑" inactive-text="" size="small" />
        <el-button size="small" @click="loadPanels">刷新</el-button>
        <el-button v-if="editMode" size="small" type="primary" @click="showAddPanel">添加面板</el-button>
        <el-button v-if="editMode" size="small" @click="initDefaults">重置默认</el-button>
      </div>
    </div>

    <!-- 可拖拽面板网格 -->
    <div v-loading="loading" class="grid-wrapper">
      <grid-layout
        v-model:layout="layoutData"
        :col-num="12"
        :row-height="40"
        :is-draggable="editMode"
        :is-resizable="editMode"
        :margin="[10, 10]"
        :use-css-transforms="true"
        @layout-updated="onLayoutUpdated"
      >
        <grid-item
          v-for="item in layoutData"
          :key="item.i"
          :i="item.i"
          :x="item.x"
          :y="item.y"
          :w="item.w"
          :h="item.h"
          :static="!editMode"
        >
          <el-card shadow="hover" class="panel-card">
            <template #header>
              <div class="panel-header">
                <span class="panel-title">{{ item.panel?.title || '未命名' }}</span>
                <div v-if="editMode" class="panel-actions">
                  <el-button size="small" link @click="editPanel(item)">编辑</el-button>
                  <el-button size="small" link type="danger" @click="deletePanel(item)">删除</el-button>
                </div>
                <el-button v-else size="small" link @click="refreshPanel(item)">刷新</el-button>
              </div>
            </template>
            <div class="panel-body" :class="{ loading: item.loading }">
              <div v-if="item.error" class="panel-error">{{ item.error }}</div>
              <PanelRenderer
                v-else
                :chart-type="item.panel?.chart_type"
                :source-type="item.panel?.source_type"
                :data="item.data"
              />
            </div>
          </el-card>
        </grid-item>
      </grid-layout>
      <el-empty v-if="!loading && layoutData.length === 0" description="暂无面板，点击「重置默认」初始化" />
    </div>

    <!-- 面板编辑器 -->
    <el-dialog v-model="editorVisible" :title="editingPanel.id ? '编辑面板' : '添加面板'" width="640px">
      <el-form :model="editingPanel" label-width="100px">
        <el-form-item label="面板标题">
          <el-input v-model="editingPanel.title" placeholder="如：出口接口流量" />
        </el-form-item>
        <el-form-item label="数据源">
          <el-select v-model="editingPanel.source_type" style="width: 100%" @change="onSourceTypeChange">
            <el-option label="Zabbix 监控项（折线图）" value="zabbix_item" />
            <el-option label="最近测速（数值卡）" value="iperf_recent" />
            <el-option label="最近扫描（数值卡）" value="scan_recent" />
            <el-option label="Zabbix 告警（表格）" value="zabbix_problems" />
            <el-option label="探针状态（数值卡）" value="probe_status" />
          </el-select>
        </el-form-item>
        <template v-if="editingPanel.source_type === 'zabbix_item'">
          <el-form-item label="Zabbix 主机">
            <el-select v-model="editingPanelCfg.host_id" placeholder="先选择主机" filterable style="width: 100%" :loading="zbxHostLoading" @change="onHostChange">
              <el-option v-for="h in zbxHosts" :key="h.host_id" :label="h.name" :value="h.host_id" />
            </el-select>
          </el-form-item>
          <el-form-item label="监控项">
            <el-select v-model="editingPanelCfg.item_key" placeholder="先选主机再选 item" filterable style="width: 100%" :loading="zbxItemLoading" :disabled="!editingPanelCfg.host_id">
              <el-option v-for="i in zbxItems" :key="i.key_" :label="i.name" :value="i.key_" />
            </el-select>
          </el-form-item>
          <el-form-item label="时间范围">
            <el-select v-model="editingPanelCfg.period" style="width: 100%">
              <el-option label="最近 1 小时" value="1h" />
              <el-option label="最近 6 小时" value="6h" />
              <el-option label="最近 24 小时" value="24h" />
              <el-option label="最近 7 天" value="7d" />
            </el-select>
          </el-form-item>
          <el-form-item label="图表类型">
            <el-select v-model="editingPanel.chart_type" style="width: 100%">
              <el-option label="折线图" value="line" />
            </el-select>
          </el-form-item>
        </template>
        <el-form-item v-else-if="['iperf_recent','scan_recent','probe_status'].includes(editingPanel.source_type)" label="图表类型">
          <el-select v-model="editingPanel.chart_type" style="width: 100%">
            <el-option label="数值卡" value="stat" />
          </el-select>
        </el-form-item>
        <el-form-item v-else-if="editingPanel.source_type === 'zabbix_problems'" label="图表类型">
          <el-select v-model="editingPanel.chart_type" style="width: 100%">
            <el-option label="表格" value="table" />
          </el-select>
        </el-form-item>
        <el-form-item label="宽度">
          <el-slider v-model="editingPanel.w" :min="2" :max="12" show-input />
        </el-form-item>
        <el-form-item label="高度">
          <el-slider v-model="editingPanel.h" :min="2" :max="16" show-input />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePanel">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { dashboardApi, organizationApi, zabbixApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import PanelRenderer from './PanelRenderer.vue'

const auth = useAuthStore()
const loading = ref(false)
const editMode = ref(false)
const panels = ref([])
const layoutData = ref([])
const orgOptions = ref([])
const selectedOrgId = ref(null)
const editorVisible = ref(false)
const saving = ref(false)
const editingPanel = ref({})
const editingPanelCfg = ref({})
const zbxHosts = ref([])
const zbxItems = ref([])
const zbxHostLoading = ref(false)
const zbxItemLoading = ref(false)

const effectiveOrgId = computed(() => (auth.isAdmin ? selectedOrgId.value : auth.orgId))
const currentOrgName = computed(() => orgOptions.value.find((o) => o.id === auth.orgId)?.name || '当前组织')

async function loadOrgOptions() {
  if (!auth.isAdmin) return
  try {
    const res = await organizationApi.all()
    orgOptions.value = Array.isArray(res) ? res : (res.items || [])
    if (orgOptions.value.length > 0 && !selectedOrgId.value) {
      selectedOrgId.value = orgOptions.value[0].id
    }
  } catch (e) {
    ElMessage.error('加载组织列表失败')
  }
}

async function onOrgChange() {
  await loadPanels()
}

async function loadPanels() {
  if (!effectiveOrgId.value) {
    ElMessage.warning('请先选择组织')
    return
  }
  loading.value = true
  try {
    const res = await dashboardApi.listPanels(effectiveOrgId.value)
    panels.value = res?.items || []
    // 首次访问空大屏 → 自动初始化默认面板（后端幂等，已有配置会跳过）
    if (panels.value.length === 0) {
      try {
        await dashboardApi.initDefaults(effectiveOrgId.value)
        const res2 = await dashboardApi.listPanels(effectiveOrgId.value)
        panels.value = res2?.items || []
      } catch (e) {
        // 初始化失败不阻断，仍展示空状态
      }
    }
    rebuildGridLayout()
    // 并行加载所有面板数据
    await Promise.all(layoutData.value.map((item) => loadPanelData(item)))
  } catch (e) {
    ElMessage.error('加载面板失败')
  } finally {
    loading.value = false
  }
}

function rebuildGridLayout() {
  layoutData.value = panels.value.map((p) => ({
    i: String(p.id),
    x: p.grid_position?.x ?? 0,
    y: p.grid_position?.y ?? 0,
    w: p.grid_position?.w ?? 6,
    h: p.grid_position?.h ?? 4,
    panel: p,
    data: null,
    loading: false,
    error: null,
  }))
}

async function loadPanelData(item) {
  item.loading = true
  item.error = null
  try {
    const data = await dashboardApi.getPanelData(item.panel.id)
    item.data = data
  } catch (e) {
    item.error = e?.response?.data?.detail || '数据加载失败'
    item.data = null
  } finally {
    item.loading = false
  }
}

function refreshPanel(item) {
  loadPanelData(item)
}

let saveTimer = null
function onLayoutUpdated() {
  if (!editMode.value) return
  // 防抖：拖拽停止 800ms 后保存
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(saveLayout, 800)
}

async function saveLayout() {
  if (!effectiveOrgId.value) return
  const layout = layoutData.value.map((item) => ({
    id: parseInt(item.i),
    x: item.x,
    y: item.y,
    w: item.w,
    h: item.h,
  }))
  try {
    await dashboardApi.saveLayout(effectiveOrgId.value, layout)
  } catch (e) {
    ElMessage.error('布局保存失败')
  }
}

function showAddPanel() {
  editingPanel.value = {
    id: null,
    title: '',
    source_type: 'iperf_recent',
    chart_type: 'stat',
    w: 6,
    h: 4,
  }
  editingPanelCfg.value = { period: '1h' }
  editorVisible.value = true
}

function editPanel(item) {
  editingPanel.value = {
    id: item.panel.id,
    title: item.panel.title,
    source_type: item.panel.source_type,
    chart_type: item.panel.chart_type,
    w: item.w,
    h: item.h,
  }
  editingPanelCfg.value = { ...(item.panel.source_config || {}), period: item.panel.source_config?.period || '1h' }
  if (item.panel.source_type === 'zabbix_item') {
    loadZbxHosts()
    if (editingPanelCfg.value.host_id) loadZbxItems(editingPanelCfg.value.host_id)
  }
  editorVisible.value = true
}

async function deletePanel(item) {
  try {
    await ElMessageBox.confirm(`确认删除面板「${item.panel.title}」？`, '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await dashboardApi.deletePanel(item.panel.id)
    ElMessage.success('面板已删除')
    loadPanels()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

async function initDefaults() {
  try {
    await ElMessageBox.confirm('将清空当前面板并创建默认配置，确认？', '重置默认', { type: 'warning' })
  } catch { return }
  try {
    // 先删除现有面板
    for (const p of panels.value) {
      await dashboardApi.deletePanel(p.id)
    }
    await dashboardApi.initDefaults(effectiveOrgId.value)
    ElMessage.success('默认面板已创建')
  } catch (e) {
    ElMessage.error('初始化失败')
  } finally {
    // 关键：无论删除/创建成功或失败，都重新加载面板列表
    // 防止部分删除失败后 UI 与后端状态不一致，导致用户误以为数据仍在
    await loadPanels()
  }
}

function onSourceTypeChange() {
  const st = editingPanel.value.source_type
  if (st === 'zabbix_item') {
    editingPanel.value.chart_type = 'line'
    loadZbxHosts()
  } else if (st === 'zabbix_problems') {
    editingPanel.value.chart_type = 'table'
  } else {
    editingPanel.value.chart_type = 'stat'
  }
}

async function loadZbxHosts() {
  if (!effectiveOrgId.value) return
  zbxHostLoading.value = true
  try {
    const res = await zabbixApi.orgHosts(effectiveOrgId.value)
    // 后端返回 {items, total}；响应拦截器已剥外层 data
    zbxHosts.value = res?.items || []
  } catch (e) {
    zbxHosts.value = []
    ElMessage.warning('Zabbix 主机加载失败，请检查组织 Zabbix 配置')
  } finally {
    zbxHostLoading.value = false
  }
}

async function onHostChange() {
  editingPanelCfg.value.item_key = null
  zbxItems.value = []
  if (editingPanelCfg.value.host_id) {
    await loadZbxItems(editingPanelCfg.value.host_id)
  }
}

async function loadZbxItems(hostId) {
  if (!effectiveOrgId.value) return
  zbxItemLoading.value = true
  try {
    const res = await zabbixApi.orgItems(effectiveOrgId.value, hostId)
    zbxItems.value = res?.items || []
  } catch (e) {
    zbxItems.value = []
  } finally {
    zbxItemLoading.value = false
  }
}

async function savePanel() {
  if (!editingPanel.value.title) return ElMessage.warning('请输入面板标题')
  saving.value = true
  try {
    // 编辑时保留原 x/y，新增时才放到底部
    let gridPos = { x: 0, y: 99, w: editingPanel.value.w, h: editingPanel.value.h }
    if (editingPanel.value.id) {
      const orig = layoutData.value.find((it) => parseInt(it.i) === editingPanel.value.id)
      if (orig) gridPos = { x: orig.x, y: orig.y, w: editingPanel.value.w, h: editingPanel.value.h }
    }
    const payload = {
      title: editingPanel.value.title,
      source_type: editingPanel.value.source_type,
      source_config: editingPanel.value.source_type === 'zabbix_item' ? { ...editingPanelCfg.value } : {},
      chart_type: editingPanel.value.chart_type,
      grid_position: gridPos,
    }
    if (editingPanel.value.id) {
      await dashboardApi.updatePanel(editingPanel.value.id, payload)
      ElMessage.success('面板已更新')
    } else {
      await dashboardApi.createPanel(effectiveOrgId.value, payload)
      ElMessage.success('面板已创建')
    }
    editorVisible.value = false
    loadPanels()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadOrgOptions()
  await loadPanels()
})

// 切换编辑模式后兜底触发图表 resize（手柄显隐可能引起容器尺寸微变）
watch(editMode, async () => {
  await nextTick()
  window.dispatchEvent(new Event('resize'))
})
</script>

<style scoped>
.dashboard-page { padding: 0; }
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding: 8px 0;
}
.toolbar-left { display: flex; align-items: center; }
.toolbar-right { display: flex; align-items: center; gap: 8px; }
.title { font-size: 18px; font-weight: 600; }
.grid-wrapper { min-height: 200px; }
.panel-card { height: 100%; }
.panel-card :deep(.el-card__body) { height: calc(100% - 50px); overflow: auto; }
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel-title { font-weight: 600; font-size: 14px; }
.panel-actions { display: flex; gap: 4px; }
.panel-body {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.panel-body.loading { opacity: 0.5; }
.panel-error {
  color: var(--el-color-danger);
  font-size: 13px;
  text-align: center;
}
.vue-grid-layout { min-height: 100px; }
</style>
