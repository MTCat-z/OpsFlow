<template>
  <div class="topology-sidebar">
    <!-- 发现任务状态 -->
    <el-card shadow="never" style="margin-bottom: 12px">
      <template #header><span style="font-weight: 600">发现任务</span></template>
      <div v-if="!tasks.length" style="color: #999; font-size: 13px">暂无任务</div>
      <div
        v-for="t in tasks"
        :key="t.id"
        style="margin-bottom: 8px; padding: 8px; background: #fafafa; border-radius: 4px"
      >
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-size: 13px">{{ t.target_subnet }}</span>
          <el-button
            size="small"
            type="danger"
            link
            :disabled="t.status === 'running'"
            @click="$emit('deleteTask', t)"
          >
            删除
          </el-button>
        </div>
        <el-progress
          :percentage="t.progress"
          :status="t.status === 'completed' ? 'success' : t.status === 'failed' ? 'exception' : ''"
          :stroke-width="6"
          style="margin: 4px 0"
        />
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-size: 12px; color: #999">节点: {{ t.nodes_discovered }} | 连线: {{ t.edges_inferred }}</span>
          <el-tag v-if="t.status === 'failed'" size="small" type="danger" style="font-size: 11px" :title="t.error_message">失败</el-tag>
          <el-tag v-else-if="t.status === 'running'" size="small" type="warning" style="font-size: 11px">运行中</el-tag>
          <el-tag v-else-if="t.status === 'completed'" size="small" type="success" style="font-size: 11px">完成</el-tag>
          <el-tag v-else size="small" style="font-size: 11px">{{ t.status }}</el-tag>
        </div>
        <div
          v-if="t.status === 'failed' && t.error_message"
          style="font-size: 11px; color: #f56c6c; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis"
          :title="t.error_message"
        >
          {{ t.error_message }}
        </div>
      </div>
    </el-card>
    <!-- 节点详情 -->
    <el-card v-if="selectedNode" shadow="never">
      <template #header><span style="font-weight: 600">节点详情</span></template>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="名称">{{ selectedNode.name }}</el-descriptions-item>
        <el-descriptions-item label="IP">{{ selectedNode.ip_address || '-' }}</el-descriptions-item>
        <el-descriptions-item label="MAC">{{ selectedNode.mac_address || '-' }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ selectedNode.device_type }}</el-descriptions-item>
        <el-descriptions-item label="厂商">{{ selectedNode.vendor || '-' }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ selectedNode.is_manual ? '手动' : '自动发现' }}</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 12px; display: flex; gap: 8px">
        <el-button v-if="!selectedNode.asset_id" size="small" type="primary" @click="$emit('importNode', selectedNode)">导入资产</el-button>
        <el-button size="small" type="danger" @click="$emit('deleteNode', selectedNode)">删除</el-button>
      </div>
    </el-card>
    <!-- 边详情 -->
    <el-card v-if="selectedEdge" shadow="never" style="margin-top: 12px">
      <template #header><span style="font-weight: 600">连线详情</span></template>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="类型">{{ selectedEdge.link_type }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ selectedEdge.is_manual ? '手动' : '自动推断' }}</el-descriptions-item>
      </el-descriptions>
      <el-button size="small" type="danger" style="margin-top: 8px" @click="$emit('deleteEdge', selectedEdge)">删除连线</el-button>
    </el-card>
  </div>
</template>

<script setup>
/**
 * 拓扑右侧面板：发现任务列表 + 节点/边详情
 */
defineProps({
  tasks: { type: Array, default: () => [] },
  selectedNode: { type: Object, default: null },
  selectedEdge: { type: Object, default: null },
})

defineEmits(['deleteTask', 'importNode', 'deleteNode', 'deleteEdge'])
</script>
