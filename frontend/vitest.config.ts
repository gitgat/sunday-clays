import { defineConfig, mergeConfig } from 'vitest/config';

import viteConfig from './vite.config.ts';

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
      restoreMocks: true,
      unstubGlobals: true,
      coverage: {
        provider: 'v8',
        include: ['src/**/*.{ts,tsx}'],
        exclude: [
          'src/main.tsx',
          'src/api/schema.d.ts',
          '**/*.d.ts',
          'e2e/**',
          'src/test/**',
          'src/**/*.test.{ts,tsx}',
        ],
        reporter: ['text', 'json-summary'],
        thresholds: { lines: 90, branches: 90 },
      },
    },
  }),
);
