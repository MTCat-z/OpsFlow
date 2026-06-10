import { ref, onMounted, onUnmounted } from 'vue'

/**
 * 通用轮询 composable
 * @param {Function} callback - 轮询回调（支持 async）
 * @param {Object} options - { interval, immediate, autoStart }
 */
export function usePolling(callback, options = {}) {
  const { interval = 5000, immediate = true, autoStart = true } = options

  const isActive = ref(false)
  let timer = null

  async function tick() {
    try {
      await callback()
    } catch (e) {
      console.error('[polling error]', e)
    }
  }

  function start() {
    if (isActive.value) return
    isActive.value = true
    if (immediate) tick()
    timer = setInterval(tick, interval)
  }

  function stop() {
    isActive.value = false
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  if (autoStart) {
    onMounted(start)
  }
  onUnmounted(stop)

  return { isActive, start, stop }
}
