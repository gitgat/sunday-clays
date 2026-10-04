import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { pwaShell } from './src/build/pwaShell.ts';

/** Font files stay files: Caddy's CSP is `font-src 'self'`, which blocks `data:` fonts. */
const FONT_FILE = /\.(?:woff2?|ttf|otf|eot)(?:$|\?)/i;
/** ECharts and its renderer, zrender (pnpm path: …/node_modules/.pnpm/echarts@x/node_modules/echarts/…). */
const ECHARTS_MODULE = /[\\/]node_modules[\\/](?:echarts|zrender)[\\/]/;

export default defineConfig({
  plugins: [react(), tailwindcss(), pwaShell()],
  server: {
    // Same origin in dev as in production: the SPA and /api share one host (C8 CSRF, cookies).
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: false } },
  },
  build: {
    manifest: true,
    // `undefined` keeps Vite's default 4 KiB rule for every other asset.
    assetsInlineLimit: (filePath) => (FONT_FILE.test(filePath) ? false : undefined),
    rolldownOptions: {
      output: {
        // One `echarts` vendor chunk shared by every lazy chart page, instead of a copy of ECharts
        // in the first page chunk that imports it. No page in the entry imports it (C11 budget).
        codeSplitting: { groups: [{ name: 'echarts', test: ECHARTS_MODULE }] },
      },
    },
  },
});
