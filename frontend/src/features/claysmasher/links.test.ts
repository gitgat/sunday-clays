import { describe, expect, it } from 'vitest';
import { claysmasherSchemeUrl, claysmasherWebUrl } from './links';

describe('ClaySmasher link URLs', () => {
  it('points the web link at the claysmasher.com page the app claims', () => {
    expect(claysmasherWebUrl(17)).toBe('https://claysmasher.com/link/sunday-clays?shooter=17');
  });

  it('links to another host than this site, so iOS hands the tap to the app (U1)', () => {
    const url = new URL(claysmasherWebUrl(17));

    expect(url.host).toBe('claysmasher.com');
    expect(url.searchParams.get('shooter')).toBe('17');
  });

  it('points the scheme link at the URI the app normalizes to the same route', () => {
    expect(claysmasherSchemeUrl(17)).toBe('claysmasher://sunday-clays/link?shooter=17');
  });
});
