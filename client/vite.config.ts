import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    proxy: {
      // Catch-all pattern — add new backend routes here instead of separate entries.
      '^/(stream|health|usage)': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
