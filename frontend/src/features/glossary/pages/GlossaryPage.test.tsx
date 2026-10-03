import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderRoutes } from '../../../test/render';
import { GLOSSARY_TERMS } from '../terms';
import { routes } from '../routes';

const on = () =>
  server.use(
    http.get('*/api/features', () => HttpResponse.json({ switches: { tour_glossary: true } })),
  );

function renderAt(route: string, role: 'viewer' | 'admin' = 'viewer') {
  return renderRoutes(
    [
      {
        path: '/',
        HydrateFallback: () => null,
        children: [...routes, { index: true, element: <p>home</p> }],
      },
    ],
    { route, role },
  );
}

describe('GlossaryPage', () => {
  beforeEach(() => on());

  it('lists every term in order with its anchor', async () => {
    renderAt('/glossary');
    expect(await screen.findByRole('heading', { level: 1, name: 'Glossary' })).toBeInTheDocument();
    expect(screen.getByText('The words Sunday Clays uses, in plain English.')).toBeInTheDocument();
    const terms = screen.getAllByRole('term');
    expect(terms.map((t) => t.id)).toEqual(GLOSSARY_TERMS.map((t) => t.id));
    expect(terms[0]).toHaveTextContent('Clays thrown and broken');
  });

  it('scrolls to and highlights the hash term for 2 s', async () => {
    const scroll = vi.spyOn(Element.prototype, 'scrollIntoView');
    renderAt('/glossary#percentile');
    const term = await screen.findByText('Percentile', { selector: 'dt' });
    await vi.waitFor(() => expect(term).toHaveClass('bg-elevated'));
    expect(scroll).toHaveBeenCalled();
    await vi.waitFor(() => expect(term).not.toHaveClass('bg-elevated'), { timeout: 3000 });
  });

  it('"Take the tour again" goes to /?tour=1', async () => {
    const { user, router } = renderAt('/glossary');
    await user.click(await screen.findByRole('button', { name: 'Take the tour again' }));
    expect(router.state.location.pathname + router.state.location.search).toBe('/?tour=1');
  });

  it('is "Page not found" for a viewer while the switch is off, with the badge for an admin', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));
    const viewer = renderAt('/glossary');
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    viewer.unmount();
    renderAt('/glossary', 'admin');
    expect(await screen.findByText('Admin preview')).toBeInTheDocument();
  });

  it('ignores a hash that names no term', async () => {
    const scroll = vi.spyOn(Element.prototype, 'scrollIntoView');
    scroll.mockClear();
    renderAt('/glossary#nope');
    expect(await screen.findByRole('heading', { level: 1, name: 'Glossary' })).toBeInTheDocument();
    expect(scroll).not.toHaveBeenCalled();
  });
});
