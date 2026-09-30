import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { YIR_2025 } from '../mocks';
import { YirIndexPage } from './YirIndexPage';

function renderIndex() {
  return renderWithProviders(
    <Routes>
      <Route path="/yir" element={<YirIndexPage />} />
      <Route path="/yir/:year" element={<p>Year page</p>} />
    </Routes>,
    { route: '/yir' },
  );
}

describe('YirIndexPage', () => {
  it('opens the latest year with scores', async () => {
    server.use(http.get('*/api/yir/:year', () => HttpResponse.json(YIR_2025)));
    const { router } = renderIndex();
    expect(await screen.findByText('Year page')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/yir/2026');
  });

  it('explains when there are no scores yet', async () => {
    server.use(http.get('*/api/yir/:year', () => HttpResponse.json({ ...YIR_2025, years: [] })));
    renderIndex();
    expect(await screen.findByText('No scores have been imported yet.')).toBeInTheDocument();
  });

  it('keeps the page heading while loading', () => {
    server.use(http.get('*/api/yir/:year', () => new Promise(() => {})));
    renderIndex();
    expect(screen.getByRole('heading', { name: 'Year in Review' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Loading Year in Review…');
  });

  it('reports a failed request', async () => {
    server.use(
      http.get('*/api/yir/:year', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'x' } }, { status: 500 }),
      ),
    );
    renderIndex();
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load Year in Review.');
    expect(screen.getByRole('heading', { name: 'Year in Review' })).toBeInTheDocument();
  });
});
