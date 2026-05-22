import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET ?? 'https://ku-helper-production.up.railway.app',
        changeOrigin: true,
      },
    },
  },
})
