import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Proxy de API en dev: mismo origen que el front (localhost:5173) hacia el
// backend FastAPI (localhost:8000) para que la cookie de sesion (cl_session)
// funcione sin lidiar con CORS/SameSite cross-origin -- mismo truco que se
// usa en produccion, donde el build de este frontend se sirve desde el
// mismo proceso FastAPI (ver web/app.py). A diferencia de Gestiolibra (sin
// prefijo comun), toda la API nueva de Contalibra vive bajo /api/ (decision
// de la migracion, ver wiki/entities/contalibra.md), asi que un solo
// prefijo alcanza.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
