// Vue 单文件组件声明
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

// Element Plus locale 模块声明
declare module 'element-plus/dist/locale/zh-cn.mjs' {
  const zhCn: Record<string, unknown>
  export default zhCn
}

// 全局变量声明
interface Window {
  __auth_redirecting?: boolean
}
