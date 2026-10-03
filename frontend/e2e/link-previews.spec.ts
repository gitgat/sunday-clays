import { readFileSync } from 'node:fs';
import { request as pwRequest, type APIRequestContext } from '@playwright/test';
import { expect, test } from './fixtures';

/**
 * Link previews through Caddy (Plan 19 §3.1, §5.3). The stack runs with link_previews on
 * (FEATURES_DEFAULT_ON). The UA cases come from deploy/caddy/user-agents.tsv, the same table the
 * Caddy script reads.
 */

const DAY = '2026-09-27';
const FB = 'facebookexternalhit/1.1';
const WHATSAPP = 'WhatsApp/2.23.20.0 A';
const BROWSER =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36';
const BASE = 'https://sundayclays.claysmasher.com';
const ROUND_TYPES: Record<string, string> = {
  sporting: 'Sporting',
  super_sporting: 'Super Sporting',
};

const table = readFileSync(new URL('../../deploy/caddy/user-agents.tsv', import.meta.url), 'utf8')
  .split('\n')
  .filter((line) => line.trim() !== '')
  .map((line) => {
    const [expectation, ua] = line.split('\t');
    return { expectation: expectation as 'crawler' | 'person', ua: ua as string };
  });

async function get(api: APIRequestContext, path: string, ua: string) {
  return api.get(path, { headers: { 'User-Agent': ua }, maxRedirects: 0 });
}

function meta(html: string, property: string): string | null {
  const match = new RegExp(`(?:property|name)="${property}" content="([^"]*)"`).exec(html);
  return match?.[1] ?? null;
}

test.describe('link previews', () => {
  test('a crawler on a Sunday gets its date, turnout and round type', async ({ request }) => {
    const event = (await (await request.get(`/api/events/${DAY}`)).json()) as {
      n_shooters: number;
      round_type: string;
    };
    const html = await (await get(request, `/events/${DAY}`, FB)).text();
    expect(meta(html, 'og:description')).toBe(
      `Sunday, Sep 27, 2026 · ${String(event.n_shooters)} shooters · ${ROUND_TYPES[event.round_type] ?? ''}`,
    );
    const image = meta(html, 'og:image') ?? '';
    expect(image.startsWith(`${BASE}/api/og/image/sunday/${DAY}.png?v=`)).toBe(true);
    const png = await request.get(new URL(image).pathname + new URL(image).search);
    expect(png.headers()['content-type']).toBe('image/png');
    const bytes = await png.body();
    // PNG IHDR: width and height are big-endian at bytes 16..23
    expect(bytes.readUInt32BE(16)).toBe(1200);
    expect(bytes.readUInt32BE(20)).toBe(630);
  });

  test('profiles and Home are generic', async ({ request }) => {
    for (const path of ['/shooters/3', '/']) {
      const html = await (await get(request, path, FB)).text();
      expect(meta(html, 'og:description'), path).toBe(
        'Scores, trophies and stats for the Sunday Clays group at Tri-County Gun Club.',
      );
    }
  });

  test('a crawler on the share prefix gets the meta page, not a 302', async ({ request }) => {
    for (const ua of [FB, WHATSAPP]) {
      const response = await get(request, `/l/events/${DAY}`, ua);
      expect(response.status(), ua).toBe(200);
      const html = await response.text();
      expect(meta(html, 'og:description'), ua).toMatch(/^Sunday, Sep 27, 2026 · /);
      expect(meta(html, 'og:url'), ua).toBe(`${BASE}/l/events/${DAY}`);
    }
  });

  test('HEAD works for crawlers and images', async ({ request }) => {
    const page = await request.head(`/l/events/${DAY}`, { headers: { 'User-Agent': FB } });
    expect(page.status()).toBe(200);
    expect(page.headers()['content-type']).toMatch(/^text\/html/);
    const image = await request.head('/api/og/image/generic.png');
    expect(image.status()).toBe(200);
    expect(image.headers()['content-type']).toBe('image/png');
  });

  test('people on a share link are redirected, query kept', async ({ request }) => {
    const plain = await get(request, `/l/events/${DAY}`, BROWSER);
    expect(plain.status()).toBe(302);
    expect(plain.headers()['location']).toBe(`/events/${DAY}`);
    const query = await get(request, `/l/events/${DAY}?w=3m`, BROWSER);
    expect(query.headers()['location']).toBe(`/events/${DAY}?w=3m`);
  });

  test('the open-redirect guard sends unsafe share paths home', async ({ request }) => {
    for (const path of ['/l//evil.com', '/l/%2F%2Fevil.com', '/l/%5Cevil.com']) {
      const response = await get(request, path, BROWSER);
      expect(response.status(), path).toBe(302);
      expect(response.headers()['location'], path).toBe('/');
    }
  });

  test('the meta page is private, varies by UA and carries the CSP', async ({ request }) => {
    const response = await get(request, `/events/${DAY}`, FB);
    const headers = response.headers();
    expect(headers['cache-control']).toBe('private, no-cache');
    expect(headers['vary']).toMatch(/User-Agent/);
    expect(headers['content-security-policy']).toContain("default-src 'self'");
  });

  for (const { expectation, ua } of table) {
    test(`${expectation}: ${ua}`, async ({ request }) => {
      const html = await (await get(request, `/events/${DAY}`, ua)).text();
      if (expectation === 'crawler') {
        expect(meta(html, 'og:title')).toBe('Sunday Clays · Tri-County Gun Club');
      } else {
        expect(meta(html, 'og:title')).toBeNull();
        expect(html).toContain('<div id="root">');
      }
    });
  }

  test('a spoofed crawler UA with a session gets the same name-free bytes', async ({
    request,
    baseURL,
  }) => {
    const anonymous = await pwRequest.newContext({ baseURL });
    try {
      const withCookie = await (await get(request, `/events/${DAY}`, FB)).text();
      const without = await (await get(anonymous, `/events/${DAY}`, FB)).text();
      expect(withCookie).toBe(without);
      for (const name of ['Finnegan', 'Stockton', 'Hadley', 'Kaplan']) {
        expect(withCookie).not.toContain(name);
      }
    } finally {
      await anonymous.dispose();
    }
  });
});
