import react from '@vitejs/plugin-react'
import tailwind from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

const PUERTO_SERVIDOR = 4317

// El build mete todo en un unico index.html. Es lo que permite abrir la
// carpeta con doble clic el dia de la grabacion: los modulos ES no cargan
// desde file://, pero un script en linea si.
export default defineConfig({
  base: './',
  plugins: [react(), tailwind(), viteSingleFile()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: `http://localhost:${PUERTO_SERVIDOR}`,
        changeOrigin: true,
        // El SSE del vigia no se puede bufferizar.
        configure: (proxy) => {
          proxy.on('proxyRes', (res) => {
            res.headers['cache-control'] = 'no-cache'
          })
        },
      },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 4000,
  },
})
