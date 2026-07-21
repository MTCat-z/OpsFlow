import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { User, Lock } from '@element-plus/icons-vue'
import './styles/global.css'
import { initTheme } from '@/composables/useTheme'
import App from './App.vue'
import router from './router'

// 尽早应用主题，防止首屏闪烁（FOUC）
initTheme()

const app = createApp(App)

// 仅注册通过字符串引用的图标（如 prefix-icon="User"）
app.component('User', User)
app.component('Lock', Lock)

// ElementPlus 组件和样式由 unplugin-vue-components 按需自动导入
// 全局 locale 通过 App.vue 中的 ElConfigProvider 配置
app.use(createPinia())
app.use(router)
app.mount('#app')
