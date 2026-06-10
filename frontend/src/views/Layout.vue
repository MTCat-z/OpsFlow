<template>
  <a href="#main-content" class="skip-link">跳转到主要内容</a>
  <el-container class="app-layout">
    <!-- 侧边栏 -->
    <el-aside
      :width="collapsed ? '64px' : '220px'"
      class="app-sidebar"
      :class="{ 'is-collapsed': collapsed }"
      role="navigation"
      aria-label="主导航"
    >
      <div class="app-sidebar__header">
        <span class="app-sidebar__logo">OPS</span>
        <span v-show="!collapsed" class="app-sidebar__title">内网运维平台</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
        background-color="#001529"
        text-color="#ffffffa6"
        active-text-color="#ffffff"
        aria-label="功能菜单"
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶栏 -->
      <el-header class="app-header" role="banner">
        <div class="app-header__left">
          <el-button
            :icon="collapsed ? 'Expand' : 'Fold'"
            text
            :aria-label="collapsed ? '展开侧边栏' : '收起侧边栏'"
            @click="collapsed = !collapsed"
          />
          <el-breadcrumb separator="/" class="app-breadcrumb">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item
              v-for="item in breadcrumbs"
              :key="item.path"
            >
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

      <!-- 内容区 -->
      <el-main id="main-content" class="app-content" role="main" aria-label="页面内容">
        <router-view />
      </el-main>
    </el-container>

    <!-- 修改密码对话框 -->
    <el-dialog
      v-model="changePwdVisible"
      title="修改密码"
      width="400px"
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
      <el-form :model="pwdForm" label-width="80px">
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
import { computed, ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Monitor, Search, Connection, Share, FirstAidKit,
  DataLine, UserFilled, Document, Timer,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const collapsed = ref(false)

const allMenuItems = [
  { path: '/assets', title: '资产管理', icon: Monitor, admin: false },
  { path: '/scan', title: 'Nmap 扫描', icon: Search, admin: false },
  { path: '/iperf', title: '性能测试', icon: Timer, admin: false },
  { path: '/broadband', title: '宽带管理', icon: Connection, admin: false },
  { path: '/topology', title: '网络拓扑', icon: Share, admin: false },
  { path: '/diagnostics', title: '网络诊断', icon: FirstAidKit, admin: false },
  { path: '/zabbix', title: 'Zabbix监控', icon: DataLine, admin: false },
  { path: '/users', title: '用户管理', icon: UserFilled, admin: true },
  { path: '/audit', title: '审计日志', icon: Document, admin: true },
]

const menuItems = computed(() => allMenuItems.filter((m) => !m.admin || authStore.isAdmin))
const activeMenu = computed(() => route.path)

const breadcrumbs = computed(() => {
  const matched = route.matched.filter((r) => r.meta?.title)
  return matched.map((r) => ({ path: r.path, title: r.meta.title }))
})

// 修改密码
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
  } catch (_e) {
    /* handled by interceptor */
  } finally {
    pwdSubmitting.value = false
  }
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

// 首次登录强制改密
onMounted(() => {
  if (authStore.mustChangePassword) {
    changePwdVisible.value = true
  }
})
</script>

<style scoped>
.app-layout {
  height: 100vh;
}

.app-sidebar {
  background: var(--ops-brand, #001529);
  transition: width var(--ops-transition-normal, 300ms ease);
  overflow: hidden;
}

.app-sidebar__header {
  height: var(--ops-sidebar-header-h, 64px);
  display: flex;
  align-items: center;
  padding: 0 var(--ops-space-5, 20px);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  gap: var(--ops-space-3, 12px);
  white-space: nowrap;
  overflow: hidden;
}

.app-sidebar__logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: var(--ops-radius-sm, 4px);
  font-weight: 700;
  font-size: 12px;
  flex-shrink: 0;
}

.app-sidebar__title {
  overflow: hidden;
  text-overflow: ellipsis;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid var(--ops-border, #f0f0f0);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--ops-space-6, 24px);
  height: var(--ops-header-h, 56px) !important;
}

.app-header__left {
  display: flex;
  align-items: center;
  gap: var(--ops-space-2, 8px);
}

.app-header__right {
  display: flex;
  align-items: center;
  gap: var(--ops-space-3, 12px);
}

.app-header__username {
  font-size: 14px;
  color: var(--ops-text-primary, #333);
}

.app-breadcrumb {
  font-size: 14px;
}

.app-content {
  background: var(--ops-bg-page, #f5f7fa);
  padding: var(--ops-space-5, 20px);
}
</style>
