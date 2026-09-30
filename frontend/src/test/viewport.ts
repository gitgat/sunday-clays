import { vi } from 'vitest';

/**
 * Makes window.matchMedia answer the C10 layout queries: '(min-width: 1024px)' matches only for
 * 'desktop'; '(pointer: coarse)' matches for 'mobile' unless `touch` says otherwise.
 * It spies on the setup.ts shim; vitest.config.ts's `restoreMocks: true` undoes it after every
 * test, and tests also call vi.restoreAllMocks() in afterEach so they never depend on that.
 */
export function stubViewport(kind: 'desktop' | 'mobile', { touch = kind === 'mobile' } = {}): void {
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches:
          query === '(min-width: 1024px)'
            ? kind === 'desktop'
            : query === '(pointer: coarse)'
              ? touch
              : false,
        media: query,
        onchange: null,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        addListener: () => undefined,
        removeListener: () => undefined,
        dispatchEvent: () => false,
      }) as MediaQueryList,
  );
}
