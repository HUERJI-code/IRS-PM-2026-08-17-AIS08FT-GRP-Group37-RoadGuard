import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'ROADGUARD_')
  const proxy = {
    '/api': {
      target: env.ROADGUARD_API_TARGET || 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  }
  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      proxy,
      fs: {
        allow: [
          '.',
          '../model/label_schema.json',
          '../../Miscellaneous/geography',
        ].map((path) => fileURLToPath(new URL(path, import.meta.url))),
      },
    },
    preview: { port: 4173, strictPort: true, proxy },
  }
})
