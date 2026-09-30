import { describe, expect, it } from 'vitest';
import viteConfig from '../../vite.config.ts';

describe('font assets', () => {
  it('are never inlined as data: URIs (the CSP is font-src self), other assets keep the default', () => {
    const limit = viteConfig.build?.assetsInlineLimit;
    expect(limit).toBeTypeOf('function');
    if (typeof limit !== 'function') return;
    const tiny = Buffer.from('x');
    for (const file of [
      'roboto-greek-ext-400-normal.woff2',
      'roboto-greek-ext-400-normal.woff',
      'x.ttf',
      'x.otf',
      'x.eot',
    ]) {
      expect(limit(`/node_modules/@fontsource/roboto/files/${file}`, tiny), file).toBe(false);
    }
    expect(limit('/src/assets/icon.png', tiny)).toBeUndefined();
  });
});
