import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { expectExplainer } from '../../../test/charts';
import { renderWithProviders } from '../../../test/render';
import { eventSummaries, meta } from '../mocks';
import { EventsPage } from './EventsPage';

/** Headings start at h1 and never skip a level (h1 → h3). */
function expectUnbrokenOutline(): void {
  const levels = [...document.querySelectorAll('h1, h2, h3, h4, h5, h6')].map((h) =>
    Number(h.tagName.slice(1)),
  );
  expect(levels[0]).toBe(1);
  expect(levels.filter((level, i) => i > 0 && level > (levels[i - 1] ?? 0) + 1)).toEqual([]);
}

describe('EventsPage', () => {
  beforeEach(() => {
    server.use(
      http.get('*/api/meta', () => HttpResponse.json(meta)),
      http.get('*/api/events', ({ request }) => {
        const year = new URL(request.url).searchParams.get('year') ?? '';
        return HttpResponse.json(eventSummaries.filter((e) => e.event_date.startsWith(year)));
      }),
    );
  });

  it('defaults to the latest season and shows its calendar and list', async () => {
    renderWithProviders(<EventsPage />, { route: '/events' });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sundays 2026' }),
    ).toBeInTheDocument();
    const list = await screen.findByRole('list', { name: 'Sundays in 2026' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(4);
    expect(screen.getByRole('region', { name: 'Calendar 2026' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Next year' })).toBeDisabled();
  });

  it('explains the calendar and says the year arrows set its period', async () => {
    renderWithProviders(<EventsPage />, { route: '/events' });
    const region = await screen.findByRole('region', { name: 'Calendar 2026' });
    await expectExplainer(region, 'About this chart', { read: true });
    expect(within(region).getByText('One year at a time')).toBeInTheDocument();
    expect(within(region).queryByText('All time')).toBeNull();
  });

  it('previous-season button loads that season, including attendance-only events', async () => {
    const user = userEvent.setup();
    renderWithProviders(<EventsPage />, { route: '/events' });
    await user.click(await screen.findByRole('button', { name: 'Previous year' }));
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sundays 2025' }),
    ).toBeInTheDocument();
    expect(await screen.findByText('Attendance only · 21 shooters')).toBeInTheDocument();
  });

  it('next-season button moves forward to the following season', async () => {
    const user = userEvent.setup();
    renderWithProviders(<EventsPage />, { route: '/events?year=2025' });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sundays 2025' }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next year' }));
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sundays 2026' }),
    ).toBeInTheDocument();
    expect(await screen.findByRole('list', { name: 'Sundays in 2026' })).toBeInTheDocument();
  });

  it('disables the previous-season button at the first season', async () => {
    renderWithProviders(<EventsPage />, { route: '/events?year=2018' });
    expect(
      await screen.findByRole('heading', { level: 2, name: 'No Sundays in 2018' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous year' })).toBeDisabled();
    expectUnbrokenOutline();
  });

  it.each([
    ['9999', 'Sundays 2026'],
    ['2027', 'Sundays 2026'],
    ['2017', 'Sundays 2018'],
    ['-5', 'Sundays 2018'],
  ])('clamps ?year=%s into the seasons with events (%s)', async (param, heading) => {
    const requested: string[] = [];
    server.use(
      http.get('*/api/events', ({ request }) => {
        requested.push(new URL(request.url).searchParams.get('year') ?? '');
        return HttpResponse.json([]);
      }),
    );
    renderWithProviders(<EventsPage />, { route: `/events?year=${param}` });
    expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeInTheDocument();
    await waitFor(() => expect(requested).toEqual([heading.slice(-4)]));
  });

  it('treats an unreadable year parameter as the latest season', async () => {
    renderWithProviders(<EventsPage />, { route: '/events?year=abc' });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sundays 2026' }),
    ).toBeInTheDocument();
  });

  it('appends the global round-type filter to the events request', async () => {
    const seen: string[][] = [];
    server.use(
      http.get('*/api/events', ({ request }) => {
        seen.push(new URL(request.url).searchParams.getAll('round_type'));
        return HttpResponse.json([]);
      }),
    );
    renderWithProviders(<EventsPage />, { route: '/events?year=2026&rt=sporting' });
    expect(await screen.findByText('No Sundays in 2026')).toBeInTheDocument();
    // The filtered request, plus the unfiltered one that finds Sundays the filter hides.
    expect(seen).toContainEqual(['sporting']);
    expect(seen).toContainEqual([]);
  });

  it('falls back to the current year when nothing has been imported', async () => {
    server.use(
      http.get('*/api/meta', () =>
        HttpResponse.json({ ...meta, first_event_date: null, last_event_date: null }),
      ),
    );
    const year = new Date().getFullYear();
    renderWithProviders(<EventsPage />, { route: '/events' });
    expect(
      await screen.findByRole('heading', { level: 1, name: `Sundays ${year}` }),
    ).toBeInTheDocument();
  });

  it('falls back to the current year when the meta request fails', async () => {
    server.use(
      http.get('*/api/meta', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    const year = new Date().getFullYear();
    renderWithProviders(<EventsPage />, { route: '/events' });
    expect(
      await screen.findByRole('heading', { level: 1, name: `Sundays ${year}` }),
    ).toBeInTheDocument();
  });

  it('shows a load failure', async () => {
    server.use(
      http.get('*/api/events', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<EventsPage />, { route: '/events?year=2026' });
    expect(
      await screen.findByRole('heading', { level: 2, name: "Couldn't load Sundays" }),
    ).toBeInTheDocument();
    expect(screen.getByText('Internal server error')).toBeInTheDocument();
    expectUnbrokenOutline();
  });

  it('keeps an unbroken heading outline on a season with events', async () => {
    renderWithProviders(<EventsPage />, { route: '/events' });
    await screen.findByRole('list', { name: 'Sundays in 2026' });
    expectUnbrokenOutline();
  });

  it('opens a custom window on the year it ends in', async () => {
    renderWithProviders(<EventsPage />, { route: '/events?w=2025-01-01..2025-11-16' });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sundays 2025' }),
    ).toBeInTheDocument();
  });

  it('lets ?year= win over a custom window', async () => {
    renderWithProviders(<EventsPage />, { route: '/events?w=2025-01-01..2025-11-16&year=2026' });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sundays 2026' }),
    ).toBeInTheDocument();
  });

  it('marks Sundays hidden by the round-type filter "Other round type"', async () => {
    server.use(
      http.get('*/api/events', ({ request }) => {
        const params = new URL(request.url).searchParams;
        const all = eventSummaries.filter((e) => e.event_date.startsWith('2026'));
        const [kept, ...hidden] = all;
        if (!kept || hidden.length === 0) throw new Error('mock has 2026 Sundays');
        return HttpResponse.json(params.has('round_type') ? [kept] : all);
      }),
    );
    renderWithProviders(<EventsPage />, { route: '/events?year=2026&rt=sporting' });
    const calendar = await screen.findByRole('region', { name: 'Calendar 2026' });
    expect(await within(calendar).findAllByRole('img', { name: /other round type/ })).toHaveLength(
      eventSummaries.filter((e) => e.event_date.startsWith('2026')).length - 1,
    );
  });

  it('still shows the calendar when the filter hides every Sunday of the year', async () => {
    server.use(
      http.get('*/api/events', ({ request }) =>
        HttpResponse.json(
          new URL(request.url).searchParams.has('round_type')
            ? []
            : eventSummaries.filter((e) => e.event_date.startsWith('2026')),
        ),
      ),
    );
    renderWithProviders(<EventsPage />, { route: '/events?year=2026&rt=super_sporting' });
    const calendar = await screen.findByRole('region', { name: 'Calendar 2026' });
    expect(await within(calendar).findAllByRole('img', { name: /other round type/ })).toHaveLength(
      4,
    );
    expect(screen.queryByRole('list', { name: 'Sundays in 2026' })).not.toBeInTheDocument();
    expect(
      screen.getByText('No Super Sporting Sundays in 2026; 4 Sundays were another round type.'),
    ).toBeInTheDocument();
  });

  it('says "Sunday was" when the filter hides a single Sunday', async () => {
    server.use(
      http.get('*/api/events', ({ request }) =>
        HttpResponse.json(
          new URL(request.url).searchParams.has('round_type')
            ? []
            : eventSummaries.filter((e) => e.event_date.startsWith('2026')).slice(0, 1),
        ),
      ),
    );
    renderWithProviders(<EventsPage />, { route: '/events?year=2026&rt=sporting' });
    expect(
      await screen.findByText('No Sporting Sundays in 2026; 1 Sunday was another round type.'),
    ).toBeInTheDocument();
  });

  it('does not say "No Sundays" while it checks the other round types', async () => {
    server.use(
      http.get('*/api/events', async ({ request }) => {
        if (!new URL(request.url).searchParams.has('round_type')) {
          await new Promise((r) => setTimeout(r, 150));
          return HttpResponse.json(eventSummaries.filter((e) => e.event_date.startsWith('2026')));
        }
        return HttpResponse.json([]);
      }),
    );
    renderWithProviders(<EventsPage />, { route: '/events?year=2026&rt=super_sporting' });
    await screen.findByRole('heading', { level: 1, name: 'Sundays 2026' });
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText('No Sundays in 2026')).not.toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'Calendar 2026' })).toBeInTheDocument();
  });
});
