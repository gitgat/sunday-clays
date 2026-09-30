import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { App } from './App';

// A page that reads React Router's context, standing in for every real feature page. vi.mock is
// hoisted above the JSX runtime import, so the factory builds elements with createElement.
vi.mock('./registry', async () => {
  const { createElement } = await import('react');
  const { useLocation } = await import('react-router');
  function Where() {
    return createElement('p', null, `at:${useLocation().pathname}`);
  }
  return { featureRoutes: [{ index: true, element: createElement(Where) }], navItems: [] };
});

describe('App', () => {
  it('renders routed pages that use React Router hooks (one router instance)', async () => {
    render(<App />);
    expect(await screen.findByText('at:/')).toBeInTheDocument();
  });
});
