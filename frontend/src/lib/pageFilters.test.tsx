import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderRoutes } from '../test/render';
import { BOTH_FILTERS, NO_FILTERS, ROUND_TYPE_ONLY, usePageFilters } from './pageFilters';

function Probe() {
  const { roundType, window } = usePageFilters();
  return (
    <p>
      rt:{String(roundType)} w:{String(window)}
    </p>
  );
}

function renderAt(route: string) {
  return renderRoutes(
    [
      {
        path: '/',
        element: <Probe />,
        handle: { filters: NO_FILTERS },
        children: [
          { path: 'both', element: <Probe />, handle: { filters: BOTH_FILTERS } },
          { path: 'rt', element: <Probe />, handle: { filters: ROUND_TYPE_ONLY } },
          { path: 'undeclared', element: <Probe /> },
        ],
      },
    ],
    { route },
  );
}

describe('page filter declarations', () => {
  it('names the three shapes', () => {
    expect(NO_FILTERS).toEqual({ roundType: false, window: false });
    expect(ROUND_TYPE_ONLY).toEqual({ roundType: true, window: false });
    expect(BOTH_FILTERS).toEqual({ roundType: true, window: true });
  });

  it.each([
    ['/both', 'rt:true w:true'],
    ['/rt', 'rt:true w:false'],
  ])('reads the declaration of the page at %s', (route, text) => {
    renderAt(route);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it('treats a route with no declaration as honouring neither filter', () => {
    renderAt('/undeclared');
    expect(screen.getByText('rt:false w:false')).toBeInTheDocument();
  });

  it('uses the deepest declaration, not a layout route above it', () => {
    renderAt('/both');
    expect(screen.getByText('rt:true w:true')).toBeInTheDocument();
  });
});
