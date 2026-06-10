<template>
  <el-row :gutter="16" style="margin-bottom: 16px">
    <el-col
      v-for="item in items"
      :key="item.title"
      :xs="12"
      :sm="12"
      :md="6"
      :lg="6"
    >
      <el-card shadow="never">
        <el-statistic
          :title="item.title"
          :value="item.value"
          :suffix="item.suffix"
          :aria-label="`${item.title}：${item.value}${item.suffix || ''}`"
        >
          <template v-if="item.prefix" #prefix>{{ item.prefix }}</template>
        </el-statistic>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
/**
 * 统计卡片行
 * @prop {Array<{title: string, value: number|string, suffix?: string, prefix?: string}>} items
 */
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})
</script>
