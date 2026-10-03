import { describe, expect, it } from 'vitest';
import { cacheNameFor, cachesToDelete, precacheList, pwaShell, swSource } from './pwaShell';

const bundle = {
  'index.html': { type: 'asset', fileName: 'index.html', source: '<html>v1</html>' },
  'assets/index-AAA.js': {
    type: 'chunk',
    fileName: 'assets/index-AAA.js',
    isEntry: true,
    isDynamicEntry: false,
    imports: ['assets/vendor-BBB.js'],
    viteMetadata: { importedCss: new Set(['assets/index-CCC.css']) },
  },
  'assets/vendor-BBB.js': {
    type: 'chunk',
    fileName: 'assets/vendor-BBB.js',
    isEntry: false,
    isDynamicEntry: false,
    imports: [],
    viteMetadata: { importedCss: new Set<string>() },
  },
  'assets/ClubPage-DDD.js': {
    type: 'chunk',
    fileName: 'assets/ClubPage-DDD.js',
    isEntry: false,
    isDynamicEntry: true,
    imports: ['assets/vendor-BBB.js'],
    viteMetadata: { importedCss: new Set(['assets/ClubPage-EEE.css']) },
  },
} as const;

describe('pwaShell', () => {
  it('precaches the shell, the entry chunk, its static imports and CSS, never a lazy chunk', () => {
    expect(precacheList(bundle)).toEqual([
      '/',
      '/index.html',
      '/manifest.webmanifest',
      '/icons/icon-192.png',
      '/assets/index-AAA.js',
      '/assets/index-CCC.css',
      '/assets/vendor-BBB.js',
    ]);
  });

  it('names the cache after the first 12 hex of sha256(index.html)', () => {
    expect(cacheNameFor('<html>v1</html>')).toMatch(/^sc-shell-[0-9a-f]{12}$/);
    expect(cacheNameFor('<html>v1</html>')).not.toBe(cacheNameFor('<html>v2</html>'));
  });

  it('keeps the current cache and the newest previous one', () => {
    const created = new Map([
      ['sc-shell-old', 1],
      ['sc-shell-prev', 5],
      ['sc-shell-now', 9],
    ]);
    expect(cachesToDelete('sc-shell-now', created)).toEqual(['sc-shell-old']);
    expect(cachesToDelete('sc-shell-now', new Map([['sc-shell-now', 9]]))).toEqual([]);
  });

  it('emits a worker that never touches /api or /l and stamps each cache', () => {
    const source = swSource('sc-shell-abc', ['/', '/index.html']);
    expect(source).toContain('const CACHE = "sc-shell-abc"');
    expect(source).toContain("url.pathname.startsWith('/api/')");
    expect(source).toContain("url.pathname.startsWith('/l/')");
    expect(source).toContain('/__sc-created');
    expect(source).toContain('skipWaiting');
    expect(source).toContain('clients.claim');
    expect(source).toContain('function cachesToDelete');
    expect(() => new Function(source)).not.toThrow(); // valid JavaScript
  });

  it('copes with a chunk without CSS metadata, a missing import and a shared import', () => {
    const odd = {
      'index.html': { type: 'asset', fileName: 'index.html', source: 'x' },
      'a.js': {
        type: 'chunk',
        fileName: 'a.js',
        isEntry: true,
        isDynamicEntry: false,
        imports: ['gone.js', 'b.js', 'c.js'],
      },
      'b.js': {
        type: 'chunk',
        fileName: 'b.js',
        isEntry: false,
        isDynamicEntry: false,
        imports: ['c.js'],
      },
      'c.js': {
        type: 'chunk',
        fileName: 'c.js',
        isEntry: false,
        isDynamicEntry: false,
        imports: [],
      },
    } as const;
    expect(precacheList(odd).slice(4)).toEqual(['/a.js', '/b.js', '/c.js']);
  });

  it('breaks ties by the earlier entry and handles an empty map', () => {
    const tied = new Map([
      ['sc-shell-a', 4],
      ['sc-shell-b', 4],
      ['sc-shell-c', 1],
    ]);
    expect(cachesToDelete('sc-shell-now', tied)).toEqual(['sc-shell-b', 'sc-shell-c']);
    expect(cachesToDelete('sc-shell-now', new Map())).toEqual([]);
  });

  it('emits sw.js from generateBundle', () => {
    const plugin = pwaShell();
    const emitted: { fileName: string; source: string }[] = [];
    const hook = plugin.generateBundle as (this: unknown, o: unknown, b: unknown) => void;
    hook.call(
      { emitFile: (f: { fileName: string; source: string }) => emitted.push(f) },
      {},
      bundle,
    );
    expect(emitted.map((f) => f.fileName)).toEqual(['sw.js']);
    expect(emitted[0]?.source).toContain('/assets/index-AAA.js');
    expect(emitted[0]?.source).not.toContain('ClubPage-DDD');
    expect(plugin.apply).toBe('build');
    const none: { fileName: string; source: string }[] = [];
    hook.call({ emitFile: (f: { fileName: string; source: string }) => none.push(f) }, {}, {});
    expect(none.map((f) => f.fileName)).toEqual(['sw.js']); // still emits with no index.html
  });
});
