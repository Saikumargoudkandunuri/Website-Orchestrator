import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/crawl': 'http://127.0.0.1:8000',
      '/issues': 'http://127.0.0.1:8000',
      '/fixes': 'http://127.0.0.1:8000',
      '/audit-log': 'http://127.0.0.1:8000',
      '/agentic': 'http://127.0.0.1:8000',
      '/v1': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
