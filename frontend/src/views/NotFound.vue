<template>
  <div class="not-found">
    <div class="not-found-content">
      <h1 class="error-code">404</h1>
      <p class="error-message">页面未找到</p>
      <p class="error-hint">你访问的页面不存在或已被移除</p>
      <el-button type="primary" @click="goHome">返回首页</el-button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

function goHome() {
  router.push('/')
}
</script>

<style scoped>
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #f5f7fa;
}
.not-found-content {
  text-align: center;
}
.error-code {
  font-size: 120px;
  font-weight: 700;
  color: #001529;
  margin: 0;
  line-height: 1;
}
.error-message {
  font-size: 24px;
  color: #333;
  margin: 16px 0 8px;
}
.error-hint {
  font-size: 14px;
  color: #999;
  margin-bottom: 32px;
}
</style>
