// Build-time only (vite.config.ts): emits /sw.js listing this build's shell files (Plan 19 D16).
import { createHash } from 'node:crypto';
import type { Plugin } from 'vite';

interface ChunkLike {
  type: 'chunk';
  fileName: string;
  isEntry: boolean;
  isDynamicEntry: boolean;
  imports: readonly string[];
  viteMetadata?: { importedCss: ReadonlySet<string> };
}
interface AssetLike {
  type: 'asset';
  fileName: string;
  source: string | Uint8Array;
}
type BundleLike = Readonly<Record<string, ChunkLike | AssetLike>>;

const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icons/icon-192.png'];

/** The entry chunk, its static imports (transitively) and their CSS; never a lazy route chunk. */
export function precacheList(bundle: BundleLike): string[] {
  const chunks = Object.values(bundle).filter((f): f is ChunkLike => f.type === 'chunk');
  const byName = new Map(chunks.map((c) => [c.fileName, c]));
  const files = new Set<string>();
  const visit = (chunk: ChunkLike) => {
    if (files.has(chunk.fileName)) return;
    files.add(chunk.fileName);
    for (const css of chunk.viteMetadata?.importedCss ?? []) files.add(css);
    for (const name of chunk.imports) {
      const imported = byName.get(name);
      if (imported !== undefined) visit(imported);
    }
  };
  for (const chunk of chunks) if (chunk.isEntry) visit(chunk);
  return [...SHELL, ...[...files].sort().map((f) => `/${f}`)];
}

export function cacheNameFor(indexHtml: string | Uint8Array): string {
  return `sc-shell-${createHash('sha256').update(indexHtml).digest('hex').slice(0, 12)}`;
}

/** Every other sc-shell cache except the newest one, so an old tab keeps its lazy chunks. */
export function cachesToDelete(current: string, created: ReadonlyMap<string, number>): string[] {
  const others = [...created].filter(([name]) => name !== current);
  let newest = '';
  let newestStamp = -Infinity;
  for (const [name, stamp] of others) {
    if (stamp > newestStamp) {
      newest = name;
      newestStamp = stamp;
    }
  }
  return others.map(([name]) => name).filter((name) => name !== newest);
}

export function swSource(cacheName: string, precache: readonly string[]): string {
  return `// Sunday Clays app shell (Plan 19 D16). Never caches /api or /l.
const CACHE = ${JSON.stringify(cacheName)};
const PRECACHE = ${JSON.stringify(precache)};
${cachesToDelete.toString()}
self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(PRECACHE);
    await cache.put('/__sc-created', new Response(String(Date.now())));
    await self.skipWaiting();
  })());
});
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = (await caches.keys()).filter((name) => name.startsWith('sc-shell-'));
    const created = new Map();
    for (const name of names) {
      const stamp = await (await caches.open(name)).match('/__sc-created');
      created.set(name, stamp ? Number(await stamp.text()) : 0);
    }
    await Promise.all(cachesToDelete(CACHE, created).map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/l/')) return;
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(async () => (await caches.match('/index.html', { cacheName: CACHE })) || Response.error()),
    );
    return;
  }
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/')) {
    event.respondWith((async () => {
      const hit = await caches.match(request);
      if (hit) return hit;
      const response = await fetch(request);
      if (response.ok) await (await caches.open(CACHE)).put(request, response.clone());
      return response;
    })());
  }
});
`;
}

export function pwaShell(): Plugin {
  return {
    name: 'sunday-clays-pwa-shell',
    apply: 'build',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const files = bundle as unknown as BundleLike;
      const index = files['index.html'];
      const html = index?.type === 'asset' ? index.source : '';
      this.emitFile({
        type: 'asset',
        fileName: 'sw.js',
        source: swSource(cacheNameFor(html), precacheList(files)),
      });
    },
  };
}
