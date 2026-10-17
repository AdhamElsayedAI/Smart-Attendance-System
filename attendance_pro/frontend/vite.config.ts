import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => ({
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: { '/api': `http://127.0.0.1:${loadEnv(mode, '.', 'ATTENDANCE_').ATTENDANCE_API_PORT || '8000'}` },
  },
}))
