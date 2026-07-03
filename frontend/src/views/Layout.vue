<template>
  <el-container class="app-layout">
    <el-aside :width="collapsed ? '64px' : '232px'" class="app-sidebar">
      <div class="app-sidebar__header">
        <span class="app-sidebar__logo">OPS</span>
        <span v-show="!collapsed" class="app-sidebar__title">OpsFlow</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
        background-color="#001529"
        text-color="#ffffffa6"
        active-text-color="#ffffff"
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div class="app-header__left">
          <el-button :icon="collapsed ? Expand : Fold" text @click="collapsed = !collapsed" />
          <el-breadcrumb separator="/" class="app-breadcrumb">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-for="item in breadcrumbs" :key="item.path">
              {{ item.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="app-header__right">
          <el-tag size="small" :type="authStore.isAdmin ? 'danger' : ''">
            {{ authStore.isAdmin ? '管理员' : '用户' }}
          </el-tag>
          <span class="app-header__username">{{ authStore.username }}</span>
          <el-button size="small" text @click="changePwdVisible = true">修改密码</el-button>
          <el-button size="small" text type="danger" @click="handleLogout">退出</el-button>
        </div>
      </el-header>

      <el-main class="app-content">
        <router-view />
      </el-main>
    </el-container>

    <el-dialog
      v-model="changePwdVisible"
      title="修改密码"
      width="420px"
      :close-on-click-modal="!authStore.mustChangePassword"
      :close-on-press-escape="!authStore.mustChangePassword"
      :show-close="!authStore.mustChangePassword"
    >
      <el-alert
        v-if="authStore.mustChangePassword"
        type="warning"
        :closable="false"
        style="margin-bottom: 16px"
        title="首次登录请修改默认密码"
      />
      <el-form :model="pwdForm" label-width="90px">
        <el-form-item label="原密码">
          <el-input v-model="pwdForm.oldPassword" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwdForm.newPassword" type="password" placeholder="至少 6 位" show-password />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="pwdForm.confirmPassword" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button v-if="!authStore.mustChangePassword" @click="changePwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdSubmitting" @click="handleChangePassword">确定</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Connection,
  DataAnalysis,
  DataLine,
  Document,
  Files,
  FirstAidKit,
  Fold,
  Grid,
  Histogram,
  Monitor,
  Operation,
  Search,
  Share,
  Timer,
  UserFilled,
  Expand,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const collapsed = ref(false)

const allMenuItems = [
  { path: '/dashboard', title: '运维数据大屏', icon: Histogram, admin: false },
  { path: '/assets', title: '资产管理', icon: Monitor, admin: false },
  { path: '/scan', title: 'Nmap 扫描', icon: Search, admin: false },
  { path: '/iperf', title: '性能测试', icon: Timer, admin: false },
  { path: '/broadband', title: '宽带管理', icon: Connection, admin: false },
  { path: '/topology', title: '网络拓扑', icon: Share, admin: false },
  { path: '/diagnostics', title: '网络诊断', icon: FirstAidKit, admin: false },
  { path: '/zabbix', title: 'Zabbix 监控', icon: DataLine, admin: false },
  { path: '/inspection', title: '自动化巡检', icon: DataAnalysis, admin: false },
  { path: '/config-backup', title: '配置备份', icon: Files, admin: false },
  { path: '/commands', title: '批量命令执行', icon: Operation, admin: false },
  { path: '/ipam', title: 'IPAM', icon: Grid, admin: false },
  { path: '/users', title: '用户管理', icon: UserFilled, admin: true },
  { path: '/audit', title: '审计日志', icon: Document, admin: true },
]

const menuItems = computed(() => allMenuItems.filter((m) => !m.admin || authStore.isAdmin))
const activeMenu = computed(() => route.path)
const breadcrumbs = computed(() => route.matched.filter((r) => r.meta?.title).map((r) => ({ path: r.path, title: r.meta.title })))

const changePwdVisible = ref(false)
const pwdSubmitting = ref(false)
const pwdForm = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })

async function handleChangePassword() {
  if (!pwdForm.oldPassword) return ElMessage.warning('请输入原密码')
  if (!pwdForm.newPassword || pwdForm.newPassword.length < 6) return ElMessage.warning('新密码至少 6 位')
  if (pwdForm.newPassword !== pwdForm.confirmPassword) return ElMessage.warning('两次密码不一致')
  pwdSubmitting.value = true
  try {
    await authStore.changePassword(pwdForm.oldPassword, pwdForm.newPassword)
    ElMessage.success('密码修改成功')
    changePwdVisible.value = false
    Object.assign(pwdForm, { oldPassword: '', newPassword: '', confirmPassword: '' })
  } finally {
    pwdSubmitting.value = false
  }
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

onMounted(() => {
  if (authStore.mustChangePassword) changePwdVisible.value = true
})
</script>

<style scoped>
.app-layout {
  height: 100vh;
}

.app-sidebar {
  background: #001529;
  overflow: hidden;
  transition: width 0.2s ease;
}

.app-sidebar__header {
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  color: #fff;
  display: flex;
  gap: 12px;
  height: 64px;
  padding: 0 18px;
  white-space: nowrap;
}

.app-sidebar__logo {
  align-items: center;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  display: flex;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  height: 28px;
  justify-content: center;
  width: 28px;
}

.app-sidebar__title {
  font-weight: 700;
}

.app-header {
  align-items: center;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  height: 56px !important;
  justify-content: space-between;
  padding: 0 20px;
}

.app-header__left,
.app-header__right {
  align-items: center;
  display: flex;
  gap: 12px;
}

.app-header__username {
  color: #303133;
  font-size: 14px;
}

.app-content {
  background: #f5f7fa;
  padding: 20px;
}
</style>
