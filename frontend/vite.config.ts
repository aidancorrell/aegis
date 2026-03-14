import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiTarget = process.env.VITE_API_URL ?? 'http://localhost:8000'

const proxyPaths = ['/events', '/stats', '/hardening', '/wizard', '/proxy', '/settings']

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: Object.fromEntries(
      proxyPaths.map((path) => [path, { target: apiTarget, changeOrigin: true }])
    ),
  },
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
  },
})
