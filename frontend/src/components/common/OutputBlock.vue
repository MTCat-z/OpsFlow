<template>
  <div class="ops-output-block" role="log" aria-label="命令输出">
    <slot>{{ content }}</slot>
  </div>
</template>

<script setup>
/**
 * 终端风格输出块
 * @prop {string} content - 输出内容（也可用 slot）
 */
defineProps({
  content: { type: String, default: '' },
})
</script>
