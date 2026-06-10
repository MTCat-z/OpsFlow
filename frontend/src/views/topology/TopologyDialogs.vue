<template>
  <!-- 添加节点对话框 -->
  <el-dialog v-model="nodeDlg" title="添加节点" width="440px">
    <el-form :model="nodeForm" label-width="80px">
      <el-form-item label="名称"><el-input v-model="nodeForm.name" /></el-form-item>
      <el-form-item label="IP"><el-input v-model="nodeForm.ip_address" placeholder="可选" /></el-form-item>
      <el-form-item label="类型">
        <el-select v-model="nodeForm.device_type" style="width: 100%">
          <el-option v-for="t in NODE_TYPES" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="nodeDlg = false">取消</el-button>
      <el-button type="primary" @click="submitNode">确定</el-button>
    </template>
  </el-dialog>
  <!-- 添加连线对话框 -->
  <el-dialog v-model="edgeDlg" title="添加连线" width="440px">
    <el-form :model="edgeForm" label-width="80px">
      <el-form-item label="起始节点">
        <el-select v-model="edgeForm.source_node_id" style="width: 100%">
          <el-option v-for="n in nodes" :key="n.id" :label="`${n.name} (${n.ip_address || ''})`" :value="n.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="目标节点">
        <el-select v-model="edgeForm.target_node_id" style="width: 100%">
          <el-option v-for="n in nodes" :key="n.id" :label="`${n.name} (${n.ip_address || ''})`" :value="n.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="连线类型">
        <el-select v-model="edgeForm.link_type" style="width: 100%">
          <el-option v-for="t in LINK_TYPES" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="edgeDlg = false">取消</el-button>
      <el-button type="primary" @click="submitEdge">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'

const NODE_TYPES = ['router', 'switch', 'server', 'firewall', 'ap', 'endpoint', 'unknown']
const LINK_TYPES = ['ethernet', 'wifi', 'fiber', 'uplink', 'logical']

defineProps({
  nodes: { type: Array, default: () => [] },
})

const emit = defineEmits(['submitNode', 'submitEdge'])

const nodeDlg = ref(false)
const edgeDlg = ref(false)
const nodeForm = reactive({ name: '', ip_address: '', device_type: 'server' })
const edgeForm = reactive({ source_node_id: null, target_node_id: null, link_type: 'ethernet' })

function openNode() {
  Object.assign(nodeForm, { name: '', ip_address: '', device_type: 'server' })
  nodeDlg.value = true
}

function openEdge() {
  Object.assign(edgeForm, { source_node_id: null, target_node_id: null, link_type: 'ethernet' })
  edgeDlg.value = true
}

function submitNode() {
  if (!nodeForm.name) return ElMessage.warning('请输入名称')
  emit('submitNode', { ...nodeForm })
  nodeDlg.value = false
}

function submitEdge() {
  if (!edgeForm.source_node_id || !edgeForm.target_node_id) return ElMessage.warning('请选择节点')
  emit('submitEdge', { ...edgeForm })
  edgeDlg.value = false
}

defineExpose({ openNode, openEdge })
</script>
