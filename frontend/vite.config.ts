import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import {defineConfig} from 'vite';

// `npm run dev` proxies the API to a running `python ui/server.py --port 8766` (never 8765, the owner's).
// `npm run build` writes frontend/dist, which ui/server.py serves at "/".
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/',
  build: {outDir: 'dist', emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 700},
  server: {
    port: 5173,
    proxy: {'/api': 'http://127.0.0.1:8766', '/files': 'http://127.0.0.1:8766'},
  },
});
