import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': process.env.DONGBA_PROXY_TARGET || 'http://127.0.0.1:8010',
      '/media': process.env.DONGBA_PROXY_TARGET || 'http://127.0.0.1:8010',
    },
  },
  build: {
    rollupOptions: {
      output: { manualChunks: { 'element-plus': ['element-plus'], vue: ['vue', 'vue-router'] } },
    },
    chunkSizeWarningLimit: 1100,
  },
})
