import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAuthStore } from '@/stores/auth'

// Mock authApi
vi.mock('@/api', () => ({
  authApi: {
    login: vi.fn(),
    changePassword: vi.fn(),
  },
}))

const { authApi } = await import('@/api')

describe('useAuthStore', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  describe('初始状态', () => {
    it('无 token 时 isLoggedIn 为 false', () => {
      const store = useAuthStore()
      expect(store.isLoggedIn).toBe(false)
      expect(store.user).toBeNull()
    })

    it('从 localStorage 恢复 token 和 user', () => {
      localStorage.setItem('token', 'test-token')
      localStorage.setItem('user', JSON.stringify({ username: 'admin', role: 'admin' }))
      const store = useAuthStore()
      expect(store.isLoggedIn).toBe(true)
      expect(store.user?.username).toBe('admin')
      expect(store.isAdmin).toBe(true)
    })

    it('localStorage 中 user 为非法 JSON 时 user 为 null', () => {
      localStorage.setItem('token', 'test-token')
      localStorage.setItem('user', '{invalid json}')
      const store = useAuthStore()
      expect(store.user).toBeNull()
    })
  })

  describe('login()', () => {
    it('成功后设置 token + user + localStorage', async () => {
      authApi.login.mockResolvedValue({
        access_token: 'jwt-123',
        username: 'testuser',
        role: 'user',
        must_change_password: false,
      })

      const store = useAuthStore()
      await store.login('testuser', 'password')

      expect(store.isLoggedIn).toBe(true)
      expect(store.token).toBe('jwt-123')
      expect(store.user?.username).toBe('testuser')
      expect(store.isAdmin).toBe(false)
      expect(localStorage.getItem('token')).toBe('jwt-123')
      expect(JSON.parse(localStorage.getItem('user'))).toEqual(
        expect.objectContaining({ username: 'testuser', role: 'user' }),
      )
    })

    it('must_change_password 为 true 时状态正确', async () => {
      authApi.login.mockResolvedValue({
        access_token: 'jwt-456',
        username: 'newuser',
        role: 'user',
        must_change_password: true,
      })

      const store = useAuthStore()
      await store.login('newuser', 'password')
      expect(store.mustChangePassword).toBe(true)
    })

    it('API 失败时不修改状态', async () => {
      authApi.login.mockRejectedValue(new Error('auth failed'))

      const store = useAuthStore()
      await expect(store.login('user', 'wrong')).rejects.toThrow()
      expect(store.isLoggedIn).toBe(false)
      expect(store.token).toBe('')
    })
  })

  describe('logout()', () => {
    it('清除 token + user + localStorage', async () => {
      authApi.login.mockResolvedValue({
        access_token: 'jwt-789',
        username: 'admin',
        role: 'admin',
        must_change_password: false,
      })

      const store = useAuthStore()
      await store.login('admin', 'password')
      expect(store.isLoggedIn).toBe(true)

      store.logout()
      expect(store.isLoggedIn).toBe(false)
      expect(store.user).toBeNull()
      expect(store.token).toBe('')
      expect(localStorage.getItem('token')).toBeNull()
      expect(localStorage.getItem('user')).toBeNull()
    })
  })

  describe('changePassword()', () => {
    it('成功后清除 must_change_password 标记', async () => {
      authApi.login.mockResolvedValue({
        access_token: 'jwt-cp',
        username: 'user1',
        role: 'user',
        must_change_password: true,
      })
      authApi.changePassword.mockResolvedValue({})

      const store = useAuthStore()
      await store.login('user1', 'password')
      expect(store.mustChangePassword).toBe(true)

      await store.changePassword('password', 'newpassword')
      expect(store.mustChangePassword).toBe(false)
    })

    it('user 为 null 时不报错', async () => {
      authApi.changePassword.mockResolvedValue({})
      const store = useAuthStore()
      // user is null initially
      await store.changePassword('old', 'new')
      // Should not throw
    })
  })

  describe('Computed 属性', () => {
    it('isAdmin 根据 role 正确计算', async () => {
      authApi.login.mockResolvedValue({
        access_token: 'jwt-admin',
        username: 'admin',
        role: 'admin',
        must_change_password: false,
      })

      const store = useAuthStore()
      await store.login('admin', 'password')
      expect(store.isAdmin).toBe(true)
    })

    it('username 取值安全', () => {
      const store = useAuthStore()
      expect(store.username).toBe('')
    })
  })
})
