import { afterEach, describe, expect, it, vi } from 'vitest';
import { takePendingLinkPassword } from './linkLogin';

describe('main.tsx startup order', () => {
  afterEach(() => {
    takePendingLinkPassword();
    document.body.innerHTML = '';
    window.history.replaceState(null, '', '/');
    vi.resetModules();
  });

  it('strips p from the address bar before the App module (and its router) is created', async () => {
    document.body.innerHTML = '<div id="root"></div>';
    window.history.replaceState(null, '', '/events/1?p=secret&x=1');
    const seenAtAppImport: string[] = [];
    vi.doMock('../../app/App', () => {
      seenAtAppImport.push(window.location.pathname + window.location.search);
      return { App: () => null };
    });
    vi.doMock('../../lib/chunkReload', () => ({
      installChunkReload: () => {
        seenAtAppImport.push(`chunkReload:${window.location.search}`);
      },
    }));
    await import('../../main');
    expect(seenAtAppImport).toEqual(['/events/1?x=1', 'chunkReload:?x=1']);
    expect(takePendingLinkPassword()).toBe('secret');
  });
});
