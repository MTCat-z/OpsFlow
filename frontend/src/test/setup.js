import { createPinia, setActivePinia } from 'pinia'
import { beforeEach } from 'vitest'

// 每个测试前重置 Pinia
beforeEach(() => {
  setActivePinia(createPinia())
})
