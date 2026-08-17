import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { resolve } from 'path'

// Vitest 环境下 stub 掉 element-plus 等库的 CSS 导入，避免 jsdom 解析 .css 失败
const testOnlyPlugins = process.env.VITEST
  ? [{
      name: 'css-stub',
      enforce: 'pre',
      resolveId(id) {
        if (id.includes('element-plus') && (id.includes('/style/') || id.endsWith('.css'))) {
          return `\0css-stub:${id}`
        }
      },
      load(id) {
        if (id.startsWith('\0css-stub:')) return ''
      },
    }]
  : []

export default defineConfig({
  plugins: [
    ...testOnlyPlugins,
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      imports: ['vue', 'vue-router', 'pinia'],
      dts: 'src/auto-imports.d.ts',
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'src/components.d.ts',
    }),
  ],
  resolve: { alias: { '@': resolve(__dirname, 'src') } },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws': { target: 'http://localhost:8000', ws: true, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    cssCodeSplit: true,
    target: 'es2020',
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia', 'axios'],
        },
      },
    },
  },
  esbuild: {
    drop: process.env.NODE_ENV === 'production' ? ['console', 'debugger'] : [],
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/test/setup.js'],
    css: true,
    deps: {
      inline: [/^element-plus/, 'vue-grid-layout'],
    },
  },
})
