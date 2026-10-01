import { toBlob } from 'html-to-image';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { shareElementAsImage, shareLink } from './share';

vi.mock('html-to-image', () => ({ toBlob: vi.fn() }));

const png = new Blob(['png-bytes'], { type: 'image/png' });

beforeEach(() => {
  vi.mocked(toBlob).mockResolvedValue(png);
});

afterEach(() => {
  vi.restoreAllMocks();
});

function captureDownloads(): string[] {
  const names: string[] = [];
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    names.push(this.download);
  });
  return names;
}

describe('shareElementAsImage', () => {
  it('shares a PNG file through the Web Share API when files can be shared', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    const share = vi.spyOn(navigator, 'share').mockResolvedValue(undefined);
    const el = document.createElement('div');
    await expect(shareElementAsImage(el, 'event-2026-09-13')).resolves.toBe('shared');
    expect(vi.mocked(toBlob).mock.calls[0]?.[0]).toBe(el);
    const file = share.mock.calls[0]?.[0]?.files?.[0];
    expect(file?.name).toBe('event-2026-09-13.png');
    expect(file?.type).toBe('image/png');
  });

  it('leaves out anything marked data-share-exclude', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(false);
    captureDownloads();
    await shareElementAsImage(document.createElement('div'), 'x');
    const filter = vi.mocked(toBlob).mock.calls[0]?.[1]?.filter;
    const hidden = document.createElement('div');
    hidden.dataset.shareExclude = '';
    expect(filter?.(hidden)).toBe(false);
    expect(filter?.(document.createElement('div'))).toBe(true);
    // No <base> is ever created: the CSP forbids it (base-uri 'none').
    expect(vi.mocked(toBlob).mock.calls[0]?.[1]?.skipFonts).toBe(true);
  });

  it('downloads the PNG when the browser cannot share files', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(false);
    const names = captureDownloads();
    await expect(shareElementAsImage(document.createElement('div'), 'odometer.png')).resolves.toBe(
      'downloaded',
    );
    expect(names).toEqual(['odometer.png']);
  });

  it('downloads when canShare is not supported at all', async () => {
    vi.stubGlobal('navigator', { ...navigator, canShare: undefined });
    const names = captureDownloads();
    await expect(shareElementAsImage(document.createElement('div'), 'x')).resolves.toBe(
      'downloaded',
    );
    expect(names).toEqual(['x.png']);
    vi.unstubAllGlobals();
  });

  it('reports a dismissed share sheet as cancelled and rethrows other failures', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    const share = vi.spyOn(navigator, 'share');
    share.mockRejectedValueOnce(new DOMException('dismissed', 'AbortError'));
    await expect(shareElementAsImage(document.createElement('div'), 'a')).resolves.toBe(
      'cancelled',
    );
    share.mockRejectedValueOnce(new DOMException('bad data', 'DataError'));
    await expect(shareElementAsImage(document.createElement('div'), 'a')).rejects.toThrow(
      'bad data',
    );
    share.mockRejectedValueOnce(new TypeError('share failed'));
    await expect(shareElementAsImage(document.createElement('div'), 'a')).rejects.toThrow(
      'share failed',
    );
  });

  it('downloads instead when the browser refuses to share (Safari after the async render)', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    vi.spyOn(navigator, 'share').mockRejectedValue(new DOMException('nope', 'NotAllowedError'));
    const names = captureDownloads();
    await expect(shareElementAsImage(document.createElement('div'), 'event')).resolves.toBe(
      'downloaded',
    );
    expect(names).toEqual(['event.png']);
  });

  it('fails loudly when the element cannot be rendered', async () => {
    vi.mocked(toBlob).mockResolvedValue(null);
    await expect(shareElementAsImage(document.createElement('div'), 'a')).rejects.toThrow(
      'Could not render the image',
    );
  });
});

describe('Roboto embedding', () => {
  function stubSheets(faces: Array<Record<string, string>>) {
    const rules = faces.map((face) => ({
      cssText: face.cssText ?? '@font-face { }',
      style: { getPropertyValue: (prop: string) => face[prop] ?? '' },
    }));
    vi.spyOn(document, 'styleSheets', 'get').mockReturnValue([
      { cssRules: [{ cssText: 'body { }' }, ...rules] },
    ] as unknown as StyleSheetList);
  }
  const latin = {
    'font-family': 'Roboto',
    'font-style': 'normal',
    'font-weight': '400',
    'font-display': 'swap',
    'unicode-range': 'U+0-FF, U+131',
    src: 'url(/assets/roboto-latin-400.woff2) format("woff2"), url(/assets/x.woff) format("woff")',
  };

  beforeEach(async () => {
    const { resetFontCache } = await import('./share');
    resetFontCache();
    vi.spyOn(navigator, 'canShare').mockReturnValue(false);
    captureDownloads();
  });

  it('passes the page’s Latin Roboto faces as data: URLs and skips other faces', async () => {
    stubSheets([
      latin,
      { ...latin, 'unicode-range': 'U+0370-03FF' },
      { ...latin, 'font-family': 'Other' },
      { ...latin, src: 'url(/a.ttf)' },
    ]);
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(['font'])) }),
    );
    await shareElementAsImage(document.createElement('div'), 'a');
    const css = vi.mocked(toBlob).mock.calls[0]?.[1]?.fontEmbedCSS ?? '';
    expect(css).toContain('font-family:Roboto');
    expect(css).toContain('src:url(data:');
    expect(css.match(/@font-face/g)).toHaveLength(1);
    expect(fetch).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });

  it('also accepts the un-normalised Latin range', async () => {
    stubSheets([{ ...latin, 'unicode-range': 'U+0000-00FF, U+0131' }]);
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(['f'])) }),
    );
    await shareElementAsImage(document.createElement('div'), 'a');
    expect(vi.mocked(toBlob).mock.calls[0]?.[1]?.fontEmbedCSS).toContain('data:');
    vi.unstubAllGlobals();
  });

  it('gives no font CSS when a font file cannot be fetched', async () => {
    stubSheets([latin]);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    await shareElementAsImage(document.createElement('div'), 'a');
    expect(vi.mocked(toBlob).mock.calls[0]?.[1]?.fontEmbedCSS).toBe('');
    vi.unstubAllGlobals();
  });

  it('gives no font CSS when the style sheets cannot be read', async () => {
    vi.spyOn(document, 'styleSheets', 'get').mockImplementation(() => {
      throw new Error('blocked');
    });
    await shareElementAsImage(document.createElement('div'), 'a');
    expect(vi.mocked(toBlob).mock.calls[0]?.[1]?.fontEmbedCSS).toBe('');
  });

  it('reads the fonts once and reuses them', async () => {
    stubSheets([latin]);
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(['f'])) }),
    );
    await shareElementAsImage(document.createElement('div'), 'a');
    await shareElementAsImage(document.createElement('div'), 'b');
    expect(fetch).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });
});

describe('shareLink', () => {
  const data = {
    title: 'The Sunday Sheet',
    text: '23 shooters',
    url: 'https://x.test/sheet/2026-09-27',
  };

  function stubClipboard() {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    return writeText;
  }

  it('shares through the Web Share API when the browser can', async () => {
    const share = vi.spyOn(navigator, 'share').mockResolvedValue(undefined);
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    await expect(shareLink(data)).resolves.toBe('shared');
    expect(share).toHaveBeenCalledWith(data);
  });

  it('is cancelled when the share sheet is dismissed', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    vi.spyOn(navigator, 'share').mockRejectedValue(new DOMException('no', 'AbortError'));
    await expect(shareLink(data)).resolves.toBe('cancelled');
  });

  it('copies the text and link when sharing is refused or missing', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    vi.spyOn(navigator, 'share').mockRejectedValue(new DOMException('no', 'NotAllowedError'));
    const writeText = stubClipboard();
    await expect(shareLink(data)).resolves.toBe('copied');
    expect(writeText).toHaveBeenCalledWith('23 shooters\nhttps://x.test/sheet/2026-09-27');
  });

  it('copies when the browser cannot share this link', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(false);
    const writeText = stubClipboard();
    await expect(shareLink(data)).resolves.toBe('copied');
    expect(writeText).toHaveBeenCalledTimes(1);
  });

  it('passes any other share failure on', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    vi.spyOn(navigator, 'share').mockRejectedValue(new DOMException('no', 'DataError'));
    await expect(shareLink(data)).rejects.toThrow('no');
    vi.spyOn(navigator, 'share').mockRejectedValue(new TypeError('bad'));
    await expect(shareLink(data)).rejects.toThrow('bad');
  });

  it('copies when the browser has no Web Share API at all', async () => {
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
    await expect(shareLink(data)).resolves.toBe('copied');
    vi.unstubAllGlobals();
  });

  it('rejects, for the caller to handle, when there is no clipboard either', async () => {
    vi.stubGlobal('navigator', {});
    await expect(shareLink(data)).rejects.toThrow(TypeError);
    vi.unstubAllGlobals();
  });
});
