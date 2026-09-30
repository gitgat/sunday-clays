/**
 * Every jsdom shim the app's tests need (C10). Never edited after Plan 01 T2: a test that needs
 * different behaviour overrides it for itself with vi.stubGlobal / vi.spyOn
 * (vitest.config.ts sets unstubGlobals and restoreMocks, so overrides never leak).
 */
import '@testing-library/jest-dom/vitest';
import 'vitest-canvas-mock';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll } from 'vitest';

import { server } from './msw/server';

function mediaQueryList(query: string): MediaQueryList {
  return {
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  };
}

class ResizeObserverStub implements ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

class IntersectionObserverStub implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin = '0px';
  readonly scrollMargin = '0px';
  readonly thresholds: readonly number[] = [0];
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

Object.defineProperty(window, 'matchMedia', { writable: true, value: mediaQueryList });
Object.defineProperty(window, 'scrollTo', { writable: true, value: () => undefined });
globalThis.ResizeObserver = ResizeObserverStub;
globalThis.IntersectionObserver = IntersectionObserverStub;
URL.createObjectURL = () => 'blob:mock-object-url';
URL.revokeObjectURL = () => undefined;
Element.prototype.scrollIntoView = () => undefined;
Element.prototype.hasPointerCapture = () => false;
Element.prototype.setPointerCapture = () => undefined;
Element.prototype.releasePointerCapture = () => undefined;
Object.defineProperty(navigator, 'share', { writable: true, value: () => Promise.resolve() });
Object.defineProperty(navigator, 'canShare', { writable: true, value: () => false });
// Node's fetch/Request (undici) reject relative URLs, but the SPA calls same-origin '/api/...'
// paths (C10 `baseUrl: ''`): resolve them against the jsdom page origin, as a browser does.
(globalThis as Record<symbol, unknown>)[Symbol.for('undici.globalOrigin.1')] = new URL(
  window.location.origin,
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => server.close());
