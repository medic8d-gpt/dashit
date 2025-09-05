import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Local dev helper: forward /api -> FastAPI at :4000
      '/api': {
        target: process.env.API_PROXY_TARGET || 'http://127.0.0.1:4000',
        changeOrigin: true,
        // Keep trailing slash behavior predictable
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})

