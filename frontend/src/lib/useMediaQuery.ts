import { useCallback, useSyncExternalStore } from 'react';

export const DESKTOP_QUERY = '(min-width: 1024px)';
export const COARSE_POINTER_QUERY = '(pointer: coarse)';

export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = window.matchMedia(query);
      list.addEventListener('change', onChange);
      return () => list.removeEventListener('change', onChange);
    },
    [query],
  );
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false,
  );
}

/** ≥1024px: side navigation layout (C10). */
export function useIsDesktop(): boolean {
  return useMediaQuery(DESKTOP_QUERY);
}

/** Touch-first device: charts pan only in fullscreen (C10 zoom rules). */
export function useIsTouch(): boolean {
  return useMediaQuery(COARSE_POINTER_QUERY);
}
