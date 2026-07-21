<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <div class="login-brand" aria-hidden="true">OF</div>
        <h2>内网运维平台</h2>
        <p>请登录以继续</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" size="large" prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" size="large" prefix-icon="Lock" show-password @keyup.enter="handleLogin" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" style="width:100%" :loading="loading" @click="handleLogin">登 录</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const formRef = ref(null)
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名' }],
  password: [{ required: true, message: '请输入密码' }],
}

async function handleLogin() {
  await formRef.value.validate()
  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    const redirect = route.query.redirect || '/assets'
    router.push(redirect)
  } catch (_e) {
    // 错误已由 axios 拦截器处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--ops-brand) 0%, var(--ops-primary-dark) 55%, var(--ops-primary) 100%);
  font-family: var(--ops-font-sans);
}
.login-card {
  width: 400px;
  padding: 40px;
  background: var(--ops-bg-card);
  border-radius: var(--ops-radius-lg);
  border: 1px solid var(--ops-border);
  box-shadow: var(--ops-shadow-lg);
  transition: transform var(--ops-transition-normal), box-shadow var(--ops-transition-normal);
}
.login-card:hover {
  transform: translateY(-2px);
}
.login-header {
  text-align: center;
  margin-bottom: 32px;
}
.login-brand {
  width: 56px;
  height: 56px;
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--ops-primary) 0%, var(--ops-primary-light) 100%);
  color: var(--ops-bg-card);
  font-weight: 700;
  font-size: 20px;
  letter-spacing: 1px;
  box-shadow: var(--ops-shadow-md);
}
.login-header h2 {
  margin: 0 0 8px;
  font-size: 24px;
  color: var(--ops-brand);
}
.login-header p {
  margin: 0;
  color: var(--ops-text-muted);
  font-size: 14px;
}
@media (prefers-reduced-motion: reduce) {
  .login-card,
  .login-card:hover {
    transition: none;
    transform: none;
  }
}
</style>
