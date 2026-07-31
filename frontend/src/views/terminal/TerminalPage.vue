<template>
  <div class="terminal-container">
    <div class="terminal-header">
      <span class="terminal-title">终端 — {{ assetName }}</span>
      <div class="terminal-actions">
        <el-tag :type="connected ? 'success' : 'danger'" size="small">{{ connected ? '已连接' : '已断开' }}</el-tag>
        <el-button v-if="!connected" size="small" @click="reconnect">重连</el-button>
        <el-button size="small" @click="close">关闭</el-button>
      </div>
    </div>
    <div ref="termDom" class="terminal-body"></div>
  </div>
</template>
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { assetApi } from '@/api'

const route = useRoute()
const router = useRouter()
const assetId = route.params.assetId
const assetName = ref(`资产 #${assetId}`)
const connected = ref(false)
const termDom = ref(null)

let term = null
let fitAddon = null
let ws = null

async function initTerminal() {
  const { Terminal } = await import('@xterm/xterm')
  const { FitAddon } = await import('@xterm/addon-fit')
  await import('@xterm/xterm/css/xterm.css')

  fitAddon = new FitAddon()
  term = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: "'Consolas', 'Monaco', 'Courier New', monospace",
    theme: { background: '#1e1e1e', foreground: '#d4d4d4', cursor: '#d4d4d4' },
    scrollback: 5000,
  })
  term.loadAddon(fitAddon)
  term.open(termDom.value)
  fitAddon.fit()

  connectWs()
}

function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const cols = term.cols
  const rows = term.rows
  const token = localStorage.getItem('token')
  const url = `${proto}//${location.host}/ws/terminal/${assetId}?cols=${cols}&rows=${rows}&token=${token}`

  ws = new WebSocket(url)
  ws.onopen = () => {
    connected.value = true
    term.focus()
  }
  ws.onmessage = (e) => {
    term.write(e.data)
  }
  ws.onclose = (_e) => {
    connected.value = false
    term.write('\r\n\x1b[33m[连接已关闭]\x1b[0m\r\n')
  }
  ws.onerror = () => {
    connected.value = false
    term.write('\r\n\x1b[31m[连接错误]\x1b[0m\r\n')
  }

  // 键盘输入 -> WebSocket
  term.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(data)
    }
  })

  // 窗口 resize
  window.addEventListener('resize', handleResize)
  term.onResize(({ cols, rows }) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send('\x00' + JSON.stringify({ type: 'resize', cols, rows }))
    }
  })
}

function handleResize() {
  if (fitAddon) fitAddon.fit()
}

function reconnect() {
  if (ws) { try { ws.close() } catch(_e) { /* ignore */ } }
  term.clear()
  connectWs()
}

function close() {
  if (ws) { try { ws.close() } catch(_e) { /* ignore */ } }
  router.push('/assets')
}

onMounted(() => {
  initTerminal()
  // 尝试获取资产名称
  assetApi.get(assetId).then(d => {
    if (d.name) assetName.value = `${d.name} (${d.ip_address})`
  }).catch(() => {})
})
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (ws) try { ws.close() } catch(_e) { /* ignore */ }
  if (term) term.dispose()
})
</script>
<style scoped>
.terminal-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--ops-term-bg);
}
.terminal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: var(--ops-term-header);
  border-bottom: 1px solid var(--ops-term-border);
}
.terminal-title {
  color: var(--ops-term-fg);
  font-size: 14px;
  font-weight: 500;
}
.terminal-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.terminal-body {
  flex: 1;
  padding: 4px;
}
</style>
