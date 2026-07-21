import { computed, ref } from 'vue'

const STORAGE_KEY = 'ops-theme'
const VALID_THEMES = ['light', 'dark']

// 模块级单例：保证所有调用方共享同一份主题状态
const theme = ref('light')

function applyTheme(value) {
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = value
  }
}

function persist(value) {
  try {
    localStorage.setItem(STORAGE_KEY, value)
  } catch {
    // localStorage 不可用时静默忽略
  }
}

function readStoredTheme() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && VALID_THEMES.includes(saved)) return saved
  } catch {
    // localStorage 不可用时静默忽略
  }
  return 'light'
}

// 模块加载时立即读取并应用主题，防止首屏闪烁（FOUC）
theme.value = readStoredTheme()
applyTheme(theme.value)

function setTheme(value) {
  if (!VALID_THEMES.includes(value)) return
  theme.value = value
  applyTheme(value)
  persist(value)
}

function toggleTheme() {
  setTheme(theme.value === 'dark' ? 'light' : 'dark')
}

/**
 * 主题 composable，跨组件共享同一份状态
 * @returns {{ theme: import('vue').Ref<string>, isDark: import('vue').ComputedRef<boolean>, toggleTheme: () => void, setTheme: (value: string) => void }}
 */
export function useTheme() {
  const isDark = computed(() => theme.value === 'dark')
  return { theme, isDark, toggleTheme, setTheme }
}

/**
 * 早期初始化主题：设置 data-theme 根属性。
 * 模块加载时已自动执行一次；可在 main.js 早期显式调用以确保顺序。
 */
export function initTheme() {
  applyTheme(theme.value)
}
