<template>
  <div class="topology-page">
    <!-- 工具栏 -->
    <el-card shadow="never" style="margin-bottom: 12px">
      <el-row :gutter="12" align="middle">
        <el-col :span="8">
          <el-input v-model="discoverSubnet" placeholder="扫描子网 如 192.168.1.0/24" style="width: 220px" />
          <el-button type="primary" style="margin-left: 8px" :loading="discovering" @click="startDiscover">自动发现</el-button>
        </el-col>
        <el-col :span="8">
          <el-button @click="topoDialogsRef?.openNode()">添加节点</el-button>
          <el-button @click="topoDialogsRef?.openEdge()">添加连线</el-button>
          <el-select v-model="layoutType" style="width: 120px; margin-left: 8px" @change="reloadGraph">
            <el-option label="层次布局" value="dagre" />
            <el-option label="力导向" value="force" />
            <el-option label="环形" value="circular" />
          </el-select>
        </el-col>
        <el-col :span="8" style="text-align: right">
          <el-button size="small" @click="loadGraph">刷新</el-button>
          <el-tag v-if="nodes.length" style="margin-left: 8px">节点: {{ nodes.length }}</el-tag>
          <el-tag v-if="edges.length" style="margin-left: 4px">连线: {{ edges.length }}</el-tag>
        </el-col>
      </el-row>
    </el-card>
    <!-- 主区域 -->
    <el-row :gutter="12">
      <!-- 画布 -->
      <el-col :span="18">
        <el-card shadow="never" body-style="padding: 0">
          <div ref="graphDom" class="graph-container"></div>
        </el-card>
      </el-col>
      <!-- 右侧面板 -->
      <el-col :span="6">
        <TopologySidebar
          :tasks="tasks"
          :selected-node="selectedNode"
          :selected-edge="selectedEdge"
          @delete-task="deleteTask"
          @import-node="importNode"
          @delete-node="deleteNode"
          @delete-edge="deleteEdge"
        />
      </el-col>
    </el-row>
    <!-- 对话框 -->
    <TopologyDialogs
      ref="topoDialogsRef"
      :nodes="nodes"
      @submit-node="onSubmitNode"
      @submit-edge="onSubmitEdge"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { topologyApi } from '@/api'
import { useTopologyGraph } from '@/composables/useTopologyGraph'
import TopologySidebar from './TopologySidebar.vue'
import TopologyDialogs from './TopologyDialogs.vue'

// ── 数据状态 ──
const nodes = ref([])
const edges = ref([])
const tasks = ref([])
const discovering = ref(false)
const discoverSubnet = ref('')
const layoutType = ref('dagre')
const selectedNode = ref(null)
const selectedEdge = ref(null)
const topoDialogsRef = ref(null)
let pollTimer = null

// ── G6 图形 composable ──
const { graphDom, renderGraph: renderG6, resize, destroy } = useTopologyGraph({
  onNodeClick: (node) => {
    selectedNode.value = node
    selectedEdge.value = null
  },
  onEdgeClick: (edge) => {
    selectedEdge.value = edge
    selectedNode.value = null
  },
  onCanvasClick: () => {
    selectedNode.value = null
    selectedEdge.value = null
  },
  onNodeDragEnd: async (rawNode, pos) => {
    try {
      await topologyApi.updateNodePosition(rawNode.id, pos)
    } catch (_e) {
      /* ignore */
    }
  },
})

async function loadGraph() {
  try {
    const data = await topologyApi.getGraph({})
    nodes.value = data.nodes || []
    edges.value = data.edges || []
    await nextTick()
    renderG6(nodes.value, edges.value, layoutType.value)
  } catch (e) {
    console.error('加载拓扑图失败', e)
  }
}

function reloadGraph() {
  loadGraph()
}

// ── 自动发现 ──
async function startDiscover() {
  if (!discoverSubnet.value) return ElMessage.warning('请输入子网')
  discovering.value = true
  try {
    const task = await topologyApi.discover({ target_subnet: discoverSubnet.value })
    ElMessage.success('发现任务已提交')
    tasks.value.unshift(task)
    pollTasks()
  } finally {
    discovering.value = false
  }
}

function pollTasks() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    let allDone = true
    for (let i = 0; i < tasks.value.length; i++) {
      if (tasks.value[i].status === 'pending' || tasks.value[i].status === 'running') {
        try {
          const t = await topologyApi.getDiscoveryTask(tasks.value[i].id)
          tasks.value[i] = t
        } catch (_e) {
          /* ignore */
        }
        allDone = false
      }
    }
    if (allDone) {
      clearInterval(pollTimer)
      pollTimer = null
      loadGraph()
    }
  }, 3000)
}

// ── 节点/边 CRUD ──
async function onSubmitNode(form) {
  await topologyApi.addNode({ ...form, position_x: 200 + Math.random() * 400, position_y: 200 + Math.random() * 300 })
  ElMessage.success('节点已添加')
  loadGraph()
}

async function onSubmitEdge(form) {
  await topologyApi.addEdge(form)
  ElMessage.success('连线已添加')
  loadGraph()
}

async function deleteNode(node) {
  await ElMessageBox.confirm('确定删除该节点及其连线?', '确认', { type: 'warning' })
  await topologyApi.deleteNode(node.id)
  ElMessage.success('已删除')
  selectedNode.value = null
  loadGraph()
}

async function deleteEdge(edge) {
  await topologyApi.deleteEdge(edge.id)
  ElMessage.success('已删除')
  selectedEdge.value = null
  loadGraph()
}

async function deleteTask(task) {
  try {
    await ElMessageBox.confirm('确定删除该发现任务及其发现的节点和连线？', '确认', { type: 'warning' })
    await topologyApi.deleteDiscoveryTask(task.id)
    ElMessage.success('任务已删除')
    tasks.value = tasks.value.filter((t) => t.id !== task.id)
    loadGraph()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function importNode(node) {
  await topologyApi.importNode(node.id, { name: node.name, device_type: node.device_type })
  ElMessage.success('已导入资产管理')
  loadGraph()
}

// ── 历史任务加载 ──
async function loadTasks() {
  try {
    const r = await topologyApi.listDiscoveryTasks({ size: 20 })
    tasks.value = r.items || []
    if (tasks.value.some((t) => t.status === 'pending' || t.status === 'running')) {
      pollTasks()
    }
  } catch (e) {
    console.error('加载发现任务列表失败', e)
  }
}

// ── 生命周期 ──
function handleResize() {
  resize()
}

onMounted(() => {
  loadGraph()
  loadTasks()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  destroy()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.topology-page {
  height: 100%;
}
.graph-container {
  width: 100%;
  height: 540px;
  background: var(--ops-bg-elevated);
  border-radius: 4px;
  position: relative;
  overflow: hidden;
}
</style>
