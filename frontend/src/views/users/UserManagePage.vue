<template>
  <div>
    <el-card shadow="never">
      <template #header>
        <el-row justify="space-between" align="middle">
          <span style="font-weight:600">用户管理</span>
          <div>
            <el-input v-model="keyword" placeholder="搜索用户名" style="width:180px;margin-right:8px" clearable @clear="loadUsers" @keyup.enter="loadUsers" />
            <el-button @click="loadUsers">搜索</el-button>
            <el-button type="primary" @click="showCreate">创建用户</el-button>
          </div>
        </el-row>
      </template>
      <el-table v-loading="loading" :data="users" stripe border>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" min-width="150" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : ''">{{ row.role === 'admin' ? '管理员' : '普通用户' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '正常' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ row.created_at?.replace('T', ' ').substring(0, 19) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="showEdit(row)">编辑</el-button>
            <el-button size="small" type="warning" @click="showResetPwd(row)">重置密码</el-button>
            <el-popconfirm title="确定删除该用户?" @confirm="handleDelete(row)">
              <template #reference>
                <el-button size="small" type="danger" :disabled="row.id === currentUserId">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dlgVisible" :title="isEdit ? '编辑用户' : '创建用户'" width="440px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :disabled="isEdit" />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="密码">
          <el-input v-model="form.password" type="password" placeholder="至少 6 位" show-password />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width:100%">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="isEdit" label="状态">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlgVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog v-model="resetPwdVisible" title="重置密码" width="400px">
      <p style="margin-bottom:12px;color:#666">为用户 <b>{{ resetPwdUser?.username }}</b> 设置新密码：</p>
      <el-input v-model="newPassword" type="password" placeholder="新密码（至少 6 位）" show-password />
      <p style="margin-top:8px;font-size:12px;color:#999">重置后用户下次登录将被强制修改密码</p>
      <template #footer>
        <el-button @click="resetPwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleResetPwd">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { userApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const currentUserId = computed(() => {
  // 从 users 列表中找到当前用户名对应的 id
  return users.value.find(x => x.username === authStore.user?.username)?.id
})

const loading = ref(false), submitting = ref(false)
const users = ref([])
const keyword = ref('')
const dlgVisible = ref(false), isEdit = ref(false), editingId = ref(null)
const resetPwdVisible = ref(false), resetPwdUser = ref(null), newPassword = ref('')

const form = reactive({ username: '', password: '', role: 'user', is_active: true })

async function loadUsers() {
  loading.value = true
  try {
    const r = await userApi.list({ size: 100, keyword: keyword.value || undefined })
    users.value = r.items || []
  } catch (_e) { /* handled by interceptor */ }
  finally { loading.value = false }
}

function showCreate() {
  isEdit.value = false; editingId.value = null
  Object.assign(form, { username: '', password: '', role: 'user', is_active: true })
  dlgVisible.value = true
}

function showEdit(row) {
  isEdit.value = true; editingId.value = row.id
  Object.assign(form, { username: row.username, role: row.role, is_active: row.is_active })
  dlgVisible.value = true
}

async function handleSubmit() {
  submitting.value = true
  try {
    if (isEdit.value) {
      await userApi.update(editingId.value, { role: form.role, is_active: form.is_active })
      ElMessage.success('用户已更新')
    } else {
      if (!form.username) return ElMessage.warning('请输入用户名')
      if (!form.password || form.password.length < 6) return ElMessage.warning('密码至少 6 位')
      await userApi.create({ username: form.username, password: form.password, role: form.role })
      ElMessage.success('用户已创建')
    }
    dlgVisible.value = false
    loadUsers()
  } catch (_e) { /* handled by interceptor */ }
  finally { submitting.value = false }
}

async function handleDelete(row) {
  try {
    await userApi.delete(row.id)
    ElMessage.success('用户已删除')
    loadUsers()
  } catch (_e) { /* handled by interceptor */ }
}

function showResetPwd(row) {
  resetPwdUser.value = row; newPassword.value = ''; resetPwdVisible.value = true
}

async function handleResetPwd() {
  if (!newPassword.value || newPassword.value.length < 6) return ElMessage.warning('密码至少 6 位')
  submitting.value = true
  try {
    await userApi.resetPassword(resetPwdUser.value.id, { new_password: newPassword.value })
    ElMessage.success('密码已重置')
    resetPwdVisible.value = false
  } catch (_e) { /* handled by interceptor */ }
  finally { submitting.value = false }
}

onMounted(loadUsers)
</script>
