import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    // 主 bundle 拆几个 vendor chunk，让浏览器并行下载 + 变更后细粒度失效缓存
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-vue': ['vue', 'pinia'],
          'vendor-naive': ['naive-ui'],
          'vendor-hljs': ['highlight.js'],
          'vendor-xterm': ['xterm', '@xterm/addon-fit'],
          'vendor-markdown': ['marked'],
        },
      },
    },
    // 阈值放宽到 800 kB，避免每次构建都打印警告；真超了再说
    chunkSizeWarningLimit: 800,
  },
})
