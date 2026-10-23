import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  publicDir: '../frontend_common/public',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@shared': path.resolve(__dirname, '../frontend_common'),
    },
  },
  server: {
    port: 5173,
    host: "0.0.0.0",
  },
})
