import { act, render, screen } from '@testing-library/react';
import { renderToString } from 'react-dom/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { stubViewport } from '../test/viewport';
import { useIsDesktop, useIsTouch } from './useMediaQuery';

type Listener = () => void;

function stubMatchMedia(initial: Record<string, boolean>) {
  const state = { ...initial };
  const listeners = new Map<string, Set<Listener>>();
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        get matches() {
          return state[query] ?? false;
        },
        media: query,
        addEventListener: (_: string, l: Listener) => {
          listeners.set(query, (listeners.get(query) ?? new Set()).add(l));
        },
        removeEventListener: (_: string, l: Listener) => listeners.get(query)?.delete(l),
      }) as unknown as MediaQueryList,
  );
  return {
    set(query: string, matches: boolean) {
      state[query] = matches;
      listeners.get(query)?.forEach((l) => l());
    },
    listenerCount: (query: string) => listeners.get(query)?.size ?? 0,
  };
}

function Probe() {
  return (
    <p>
      desktop:{String(useIsDesktop())} touch:{String(useIsTouch())}
    </p>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useMediaQuery', () => {
  it('matches the C10 desktop and touch queries as stubbed by stubViewport', () => {
    stubViewport('desktop');
    render(<Probe />);
    expect(screen.getByText('desktop:true touch:false')).toBeInTheDocument();
  });

  it('treats a phone as touch-first', () => {
    stubViewport('mobile');
    render(<Probe />);
    expect(screen.getByText('desktop:false touch:true')).toBeInTheDocument();
  });

  it('reads the current match and follows changes', () => {
    const media = stubMatchMedia({ '(min-width: 1024px)': false, '(pointer: coarse)': true });
    render(<Probe />);
    expect(screen.getByText('desktop:false touch:true')).toBeInTheDocument();
    act(() => media.set('(min-width: 1024px)', true));
    expect(screen.getByText('desktop:true touch:true')).toBeInTheDocument();
  });

  it('reports no match while rendering on the server', () => {
    stubViewport('mobile');
    const html = document.createElement('div');
    html.innerHTML = renderToString(<Probe />);
    expect(html.textContent).toBe('desktop:false touch:false');
  });

  it('unsubscribes on unmount', () => {
    const media = stubMatchMedia({});
    const { unmount } = render(<Probe />);
    expect(media.listenerCount('(min-width: 1024px)')).toBe(1);
    unmount();
    expect(media.listenerCount('(min-width: 1024px)')).toBe(0);
  });
});
