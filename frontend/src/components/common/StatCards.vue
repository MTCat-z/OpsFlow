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
      <el-card shadow="never" class="stat-card">
        <div class="stat-card__title">{{ item.title }}</div>
        <div class="stat-card__value">
          <span v-if="item.prefix" class="stat-card__prefix">{{ item.prefix }}</span>
          <span class="stat-card__num">{{ item.value }}</span>
          <span v-if="item.suffix" class="stat-card__suffix">{{ item.suffix }}</span>
        </div>
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

<style scoped>
.stat-card {
  min-height: 100px;
}

.stat-card__title {
  color: var(--ops-text-secondary);
  font-size: 13px;
  line-height: 20px;
}

.stat-card__value {
  color: var(--ops-text-primary);
  font-size: 28px;
  font-weight: 700;
  line-height: 42px;
  white-space: nowrap;
}

.stat-card__prefix,
.stat-card__suffix {
  font-size: 14px;
  font-weight: 400;
  color: var(--ops-text-muted);
}

.stat-card__num {
  font-family: var(--ops-font-mono, inherit);
}
</style>
