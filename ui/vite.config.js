import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// build -> ui/dist, que es lo que sirve harness/server.py
// dev    -> proxy al mismo servidor, para no duplicar la API
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    port: 5273,
    proxy: { '/api': 'http://127.0.0.1:8770' },
  },
})
