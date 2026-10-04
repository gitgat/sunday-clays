import { toBlob } from 'html-to-image';
import { downloadBlob } from './download';

export type ShareOutcome = 'shared' | 'downloaded' | 'cancelled';

/** Anything marked `data-share-exclude` (a card's disclosure buttons, say) is left out of the image. */
function keepInImage(node: Node): boolean {
  return !(node instanceof HTMLElement && node.hasAttribute('data-share-exclude'));
}

// Browsers normalise the range: fontsource's U+0000-00FF reads back as U+0-FF.
const LATIN_RANGE = /U\+0(?:000)?-(?:00)?FF/i;
const LATIN_RANGE_TEXT = 'U+0-FF';
let robotoCss: Promise<string> | undefined;

function readAsDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

async function fontFaceWithDataUrl(rule: CSSStyleRule): Promise<string> {
  const src = rule.style.getPropertyValue('src');
  const url = /url\(["']?([^"')]+\.woff2)["']?\)/.exec(src)?.[1];
  if (url === undefined) return '';
  const response = await fetch(url);
  if (!response.ok) return '';
  const data = await readAsDataUrl(await response.blob());
  const { style } = rule;
  const family = style.getPropertyValue('font-family');
  const declarations = ['font-style', 'font-weight', 'font-display']
    .map((prop) => `${prop}:${style.getPropertyValue(prop)};`)
    .join('');
  return `@font-face{font-family:${family};${declarations}src:url(${data}) format("woff2");unicode-range:${LATIN_RANGE_TEXT};}`;
}

/**
 * The Latin Roboto faces the page already loads, re-written with data: URLs, for the image.
 * html-to-image's own font embedding needs a temporary <base>, which the Content-Security-Policy
 * (base-uri 'none') blocks; fetching the same-origin files ourselves (connect-src 'self') does not.
 * Any failure gives '' and the image falls back to the system sans-serif.
 */
function robotoFontCss(): Promise<string> {
  robotoCss ??= (async () => {
    try {
      const rules: CSSStyleRule[] = [];
      for (const sheet of Array.from(document.styleSheets)) {
        for (const rule of Array.from(sheet.cssRules)) {
          const face = rule as CSSStyleRule;
          if (
            rule.cssText.startsWith('@font-face') &&
            /roboto/i.test(face.style.getPropertyValue('font-family')) &&
            LATIN_RANGE.test(face.style.getPropertyValue('unicode-range'))
          ) {
            rules.push(face);
          }
        }
      }
      return (await Promise.all(rules.map(fontFaceWithDataUrl))).join('');
    } catch {
      return '';
    }
  })();
  return robotoCss;
}

/** Forgets the cached font CSS (tests only). */
export function resetFontCache(): void {
  robotoCss = undefined;
}

function pngName(filename: string): string {
  return filename.endsWith('.png') ? filename : `${filename}.png`;
}

/** Renders `el` to a PNG blob (2x, Roboto embedded, `data-share-exclude` left out). */
export async function renderElementToPng(el: HTMLElement): Promise<Blob> {
  const blob = await toBlob(el, {
    pixelRatio: 2,
    cacheBust: true,
    filter: keepInImage,
    // html-to-image's own font embedding uses a temporary <base>, which the CSP blocks (see above).
    skipFonts: true,
    fontEmbedCSS: await robotoFontCss(),
    backgroundColor: getComputedStyle(document.body).backgroundColor,
  });
  if (!blob) throw new Error('Could not render the image');
  return blob;
}

/** Renders `el` and saves it as a file; never opens the share sheet (Plan 19 D20). */
export async function downloadElementAsImage(el: HTMLElement, filename: string): Promise<void> {
  downloadBlob(await renderElementToPng(el), pngName(filename));
}

/**
 * Renders `el` to a PNG and hands it to the Web Share API when the browser can share files,
 * otherwise downloads it. Resolves 'cancelled' when the user dismisses the share sheet. A
 * NotAllowedError also downloads: Safari drops the tap's transient activation during the async
 * render, so it refuses the share even though canShare said yes.
 */
export async function shareElementAsImage(
  el: HTMLElement,
  filename: string,
): Promise<ShareOutcome> {
  const name = pngName(filename);
  const blob = await renderElementToPng(el);
  const file = new File([blob], name, { type: 'image/png' });
  if (typeof navigator.canShare === 'function' && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: name });
      return 'shared';
    } catch (error) {
      if (!(error instanceof DOMException)) throw error;
      if (error.name === 'AbortError') return 'cancelled';
      if (error.name !== 'NotAllowedError') throw error;
    }
  }
  downloadBlob(blob, name);
  return 'downloaded';
}
