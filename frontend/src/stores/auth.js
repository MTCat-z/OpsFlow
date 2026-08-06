import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  function safeParseUser() {
    try {
      return JSON.parse(localStorage.getItem('user') || 'null')
    } catch {
      return null
    }
  }
  const user = ref(safeParseUser())

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const orgId = computed(() => user.value?.org_id ?? null)
  const username = computed(() => user.value?.username || '')
  const mustChangePassword = computed(() => user.value?.must_change_password === true)

  async function login(username, password) {
    const res = await authApi.login({ username, password })
    token.value = res.access_token
    user.value = {
      username: res.username,
      role: res.role,
      org_id: res.org_id,
      must_change_password: res.must_change_password,
    }
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('user', JSON.stringify(user.value))
    return res
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  async function changePassword(oldPassword, newPassword) {
    await authApi.changePassword({ old_password: oldPassword, new_password: newPassword })
    // 改完密码后清除强制改密标记
    if (user.value) {
      user.value.must_change_password = false
      localStorage.setItem('user', JSON.stringify(user.value))
    }
  }

  return { token, user, isLoggedIn, isAdmin, orgId, username, mustChangePassword, login, logout, changePassword }
})
