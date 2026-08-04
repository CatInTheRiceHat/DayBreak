import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Pin the dev server to a fixed port so the OAuth redirect URL is always
    // http://localhost:6767 (matches Google/Supabase config). strictPort makes
    // Vite fail loudly if 6767 is taken instead of silently drifting to 6768+.
    port: 6767,
    strictPort: true,
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
