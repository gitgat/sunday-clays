import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { TrophiesToday } from './TrophiesToday';

function renderToday() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <TrophiesToday date="2026-09-13" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('TrophiesToday', () => {
  it('lists the trophies earned at the event', async () => {
    renderToday();
    const list = await screen.findByRole('list', { name: 'Trophies earned today' });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[1]).toHaveTextContent('McGinnis, Alvin — Events Attended — 100 events');
    expect(within(list).getByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/12',
    );
  });

  it('says so when no trophy was earned', async () => {
    server.use(
      http.get('*/api/events/:date/achievements', () =>
        HttpResponse.json({ event_date: '2026-09-13', awards: [] }),
      ),
    );
    renderToday();
    expect(await screen.findByText('No trophies were earned this Sunday.')).toBeInTheDocument();
  });

  it('shows an error when the API fails', async () => {
    server.use(
      http.get('*/api/events/:date/achievements', () => new HttpResponse(null, { status: 404 })),
    );
    renderToday();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not load trophies for this Sunday.',
    );
  });
});
