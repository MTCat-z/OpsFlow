<template>
  <el-tag
    :type="statusConfig?.type || 'info'"
    :size="size"
    :aria-label="`状态：${statusConfig?.label || value}`"
  >
    {{ statusConfig?.label || value }}
  </el-tag>
</template>

<script setup>
import { computed } from 'vue'

/**
 * 统一状态标签
 * @prop {string} value - 状态值
 * @prop {Object} statusMap - 状态映射 { value: { label, type } }
 * @prop {string} size - 标签尺寸
 */
const props = defineProps({
  value: { type: String, required: true },
  statusMap: { type: Object, required: true },
  size: { type: String, default: 'small' },
})

const statusConfig = computed(() => props.statusMap[props.value])
</script>
