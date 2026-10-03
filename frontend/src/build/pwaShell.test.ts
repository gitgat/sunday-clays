import { describe, expect, it, vi } from 'vitest';
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

interface FakeEvent {
  request: { method: string; url: string; mode: string };
  respondWith: ReturnType<typeof vi.fn>;
}

/** Runs the emitted worker in a fake scope and returns a way to fire its fetch listener. */
function runWorker(fetchImpl: (r: unknown) => Promise<Response>, cached: Map<string, Response>) {
  const listeners: Record<string, (event: unknown) => void> = {};
  const self = {
    addEventListener: (type: string, fn: (event: unknown) => void) => {
      listeners[type] = fn;
    },
    location: { origin: 'https://sc.test' },
    skipWaiting: vi.fn(),
    clients: { claim: vi.fn() },
  };
  const put = vi.fn().mockResolvedValue(undefined);
  const match = vi.fn(async (request: string | { url: string }) =>
    cached.get(typeof request === 'string' ? request : new URL(request.url).pathname),
  );
  const caches = {
    match,
    open: vi.fn().mockResolvedValue({ put }),
    keys: vi.fn(),
    delete: vi.fn(),
  };
  const fetchSpy = vi.fn(fetchImpl);
  new Function('self', 'caches', 'fetch', swSource('sc-shell-t', ['/']))(self, caches, fetchSpy);
  const fire = async (method: string, path: string, mode = 'cors') => {
    const event: FakeEvent = {
      request: { method, url: `https://sc.test${path}`, mode },
      respondWith: vi.fn(),
    };
    listeners.fetch?.(event);
    const answered = event.respondWith.mock.calls.length > 0;
    const response = answered
      ? await (event.respondWith.mock.calls[0]?.[0] as Promise<Response>)
      : null;
    return { answered, response };
  };
  return { fire, match, fetchSpy, put };
}

describe('emitted worker behaviour', () => {
  const live = () => new Response('live');
  const cachedIndex = new Response('cached-index');

  it('navigations are network-first and read the cache only when the network fails', async () => {
    const online = runWorker(async () => live(), new Map([['/index.html', cachedIndex]]));
    const ok = await online.fire('GET', '/club', 'navigate');
    expect(await ok.response?.text()).toBe('live');
    expect(online.match).not.toHaveBeenCalled();

    const offline = runWorker(
      () => Promise.reject(new TypeError('offline')),
      new Map([['/index.html', new Response('cached-index')]]),
    );
    const fallback = await offline.fire('GET', '/club', 'navigate');
    expect(await fallback.response?.text()).toBe('cached-index');
    expect(offline.fetchSpy).toHaveBeenCalledTimes(1);
    expect(offline.match).toHaveBeenCalledWith('/index.html', { cacheName: 'sc-shell-t' });
  });

  it('an offline navigation with nothing cached is a network error, not a crash', async () => {
    const offline = runWorker(() => Promise.reject(new TypeError('offline')), new Map());
    const { response } = await offline.fire('GET', '/', 'navigate');
    expect(response?.type).toBe('error');
  });

  it.each([
    ['GET', '/api/x'],
    ['GET', '/l/x'],
    ['POST', '/assets/a.js'],
    ['GET', '/trophies/t.png'],
  ])('%s %s is left to the network (no respondWith)', async (method, path) => {
    const worker = runWorker(async () => live(), new Map());
    expect((await worker.fire(method, path)).answered).toBe(false);
  });

  it('serves /assets/* cache-first and stores a miss', async () => {
    const hit = runWorker(
      async () => live(),
      new Map([['/assets/a.js', new Response('cached-js')]]),
    );
    expect(await (await hit.fire('GET', '/assets/a.js')).response?.text()).toBe('cached-js');
    expect(hit.fetchSpy).not.toHaveBeenCalled();

    const miss = runWorker(async () => live(), new Map());
    expect(await (await miss.fire('GET', '/assets/b.js')).response?.text()).toBe('live');
    expect(miss.put).toHaveBeenCalledTimes(1);
  });

  it('serves icons network-first so a regenerated icon is never stale', async () => {
    const worker = runWorker(
      async () => live(),
      new Map([['/icons/icon-192.png', new Response('old')]]),
    );
    expect(await (await worker.fire('GET', '/icons/icon-192.png')).response?.text()).toBe('live');
    const offline = runWorker(
      () => Promise.reject(new TypeError('offline')),
      new Map([['/icons/icon-192.png', new Response('old')]]),
    );
    expect(await (await offline.fire('GET', '/icons/icon-192.png')).response?.text()).toBe('old');
  });
});
