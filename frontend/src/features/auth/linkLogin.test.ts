import { afterEach, describe, expect, it, vi } from 'vitest';
import { captureLinkPassword, extractLinkPassword, takePendingLinkPassword } from './linkLogin';

describe('extractLinkPassword', () => {
  it.each([
    ['/?p=secret', 'secret', '/'],
    ['/events/2026-11-01?p=secret', 'secret', '/events/2026-11-01'],
    ['/?p=secret&rt=sporting', 'secret', '/?rt=sporting'],
    ['/?rt=sporting&p=secret', 'secret', '/?rt=sporting'],
    ['/?a=1&p=secret&b=2', 'secret', '/?a=1&b=2'],
    ['/x?p=secret#top', 'secret', '/x#top'],
    ['/x?p=secret&a=b#top', 'secret', '/x?a=b#top'],
    ['/?p=a%20b', 'a b', '/'],
    ['/?p=a+b', 'a b', '/'],
    ['/?p=a%2Bb', 'a+b', '/'],
    ['/?p=a%26b%3Dc', 'a&b=c', '/'],
    ['/?p=first&p=second', 'first', '/'],
    ['/?p=first&a=1&p=second', 'first', '/?a=1'],
    ['/?p=%E0%A4%A', '\uFFFD%A', '/'],
    ['/?p=a%26b%', 'a&b%', '/'],
    ['//?p=secret', 'secret', '/'],
    ['//events?p=secret&x=1', 'secret', '/events?x=1'],
    ['//[/?p=secret', 'secret', '/[/'],
    ['///a?p=secret', 'secret', '/a'],
    ['https://example.test/events?p=secret&x=1', 'secret', '/events?x=1'],
  ])('%s', (url, password, cleanedUrl) => {
    expect(extractLinkPassword(url)).toEqual({ password, cleanedUrl });
  });

  it.each([
    ['/?p=', '/'],
    ['/?p', '/'],
    ['/?p=&a=1', '/?a=1'],
    ['/?p=&p=secret', '/'],
  ])('strips but ignores an empty p: %s', (url, cleanedUrl) => {
    expect(extractLinkPassword(url)).toEqual({ password: null, cleanedUrl });
  });

  it.each(['/', '/events?rt=sporting#x', '/?pp=1&q=p', '/?P=secret', '/?next=%2F%3Fp%3D1'])(
    'leaves a URL without p untouched: %s',
    (url) => {
      expect(extractLinkPassword(url)).toEqual({ password: null, cleanedUrl: url });
    },
  );

  it.each(['//', '//events', '//[/', '//events?x=1#a'])(
    'leaves a doubled-slash path alone and does not throw: %s',
    (url) => {
      expect(extractLinkPassword(url)).toEqual({ password: null, cleanedUrl: url });
    },
  );

  it.each([
    ['/explorer?m=rounds&p=0..0.25', '/explorer?m=rounds&rain=0..0.25'],
    ['/explorer?p=..1', '/explorer?rain=..1'],
    ['/explorer?p=0.5..', '/explorer?rain=0.5..'],
  ])('maps the old Explorer rain range to its new parameter: %s', (url, cleanedUrl) => {
    expect(extractLinkPassword(url)).toEqual({ password: null, cleanedUrl });
  });

  it('only maps a range on the Explorer page', () => {
    expect(extractLinkPassword('/events?p=0..0.25').password).toBe('0..0.25');
  });

  it('keeps the other parameters byte for byte', () => {
    expect(extractLinkPassword('/?q=a%20b+c&p=x&r=%7E').cleanedUrl).toBe('/?q=a%20b+c&r=%7E');
  });
});

function fakeWindow(url: string) {
  const u = new URL(url, 'http://localhost');
  const replaceState = vi.fn();
  return {
    win: {
      location: { pathname: u.pathname, search: u.search, hash: u.hash },
      history: { state: { idx: 3 }, replaceState },
    },
    replaceState,
  };
}

describe('captureLinkPassword', () => {
  afterEach(() => {
    takePendingLinkPassword();
  });

  it('rewrites the address bar without a new history entry and holds the password once', () => {
    const { win, replaceState } = fakeWindow('/events?p=secret&rt=sporting#top');
    captureLinkPassword(win);
    expect(replaceState).toHaveBeenCalledExactlyOnceWith({ idx: 3 }, '', '/events?rt=sporting#top');
    expect(takePendingLinkPassword()).toBe('secret');
    expect(takePendingLinkPassword()).toBeNull();
  });

  it('strips an empty p but holds nothing', () => {
    const { win, replaceState } = fakeWindow('/?p=');
    captureLinkPassword(win);
    expect(replaceState).toHaveBeenCalledWith({ idx: 3 }, '', '/');
    expect(takePendingLinkPassword()).toBeNull();
  });

  it('leaves an Explorer rain filter alone: no password, no request, filter kept', () => {
    const { win, replaceState } = fakeWindow('/explorer?m=rounds&p=0..0.25');
    captureLinkPassword(win);
    expect(takePendingLinkPassword()).toBeNull();
    expect(replaceState).toHaveBeenCalledExactlyOnceWith(
      { idx: 3 },
      '',
      '/explorer?m=rounds&rain=0..0.25',
    );
  });

  it('hands replaceState a single-slash URL for doubled-slash paths, and survives a refused rewrite', () => {
    for (const [pathname, search, expected] of [
      ['//', '?p=hunter2-fake', '/'],
      ['//events', '?p=hunter2-fake&x=1', '/events?x=1'],
      ['//[/', '?p=hunter2-fake', '/[/'],
    ] as const) {
      const replaceState = vi.fn();
      const win = {
        location: { pathname, search, hash: '' },
        history: { state: null, replaceState },
      };
      captureLinkPassword(win);
      expect(replaceState).toHaveBeenCalledWith(null, '', expected);
      expect(takePendingLinkPassword()).toBe('hunter2-fake');
    }
    const throwing = {
      location: { pathname: '/', search: '?p=hunter2-fake', hash: '' },
      history: {
        state: null,
        replaceState: () => {
          throw new Error('refused');
        },
      },
    };
    expect(() => captureLinkPassword(throwing)).not.toThrow();
    expect(takePendingLinkPassword()).toBe('hunter2-fake');
  });

  it('does nothing for a URL without p', () => {
    const { win, replaceState } = fakeWindow('/events?rt=sporting');
    captureLinkPassword(win);
    expect(replaceState).not.toHaveBeenCalled();
    expect(takePendingLinkPassword()).toBeNull();
  });

  it('writes the password to no web storage and no cookie', () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    const { win } = fakeWindow('/?p=secret');
    captureLinkPassword(win);
    expect(setItem).not.toHaveBeenCalled();
    expect(document.cookie).not.toContain('secret');
  });

  it('works on the real window', () => {
    window.history.replaceState(null, '', '/events?p=secret&x=1');
    captureLinkPassword();
    expect(window.location.pathname + window.location.search).toBe('/events?x=1');
    expect(takePendingLinkPassword()).toBe('secret');
  });
});
