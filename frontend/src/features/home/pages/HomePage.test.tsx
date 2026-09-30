import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { clearMe, setMe } from '../../../lib/me';
import { expectChartControls } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { homeMeta, latestEvent, meDetail, meRounds, seasonEvents } from '../mocks';
import type { HomeWidget } from '../widgets';
import { HomePage } from './HomePage';

/** A landmark's accessible name, from `aria-labelledby` (Card) or `aria-label`. */
function landmarkName(element: HTMLElement): string {
  const labelledBy = element.getAttribute('aria-labelledby');
  if (labelledBy !== null) return document.getElementById(labelledBy)?.textContent ?? '';
  return element.getAttribute('aria-label') ?? '';
}

// ClubPulse loads its chart lazily. Warm that module (and ECharts) once, so findBy*'s 1 s
// budget never covers a cold import, and every test that loads the season waits for the chart:
// a lazy chart resolving after a test ends would log React's act() warning.
beforeAll(async () => {
  await import('../components/TurnoutChart');
});
const chartLoaded = () => screen.findByRole('region', { name: 'Turnout per Sunday' });

const widgets: HomeWidget[] = [
  {
    id: 'next-sunday',
    order: 10,
    slot: 'main',
    Component: ({ meId }) => <p>next sunday for {String(meId)}</p>,
  },
  {
    id: 'next-trophy',
    order: 10,
    slot: 'me',
    Component: ({ meId }) => <p>next trophy for {meId}</p>,
  },
];

describe('HomePage', () => {
  beforeEach(() => {
    clearMe();
    server.use(
      http.get('*/api/meta', () => HttpResponse.json(homeMeta)),
      http.get('*/api/events/:date', () => HttpResponse.json(latestEvent)),
      http.get('*/api/events', () => HttpResponse.json(seasonEvents)),
      http.get('*/api/shooters/:id', ({ params }) =>
        params.id === '3'
          ? HttpResponse.json(meDetail)
          : HttpResponse.json(
              { error: { code: 'shooter_not_found', message: 'No such shooter' } },
              { status: 404 },
            ),
      ),
      http.get('*/api/shooters/:id/rounds', () => HttpResponse.json(meRounds)),
    );
  });

  it('every data chart exposes Table and CSV controls', async () => {
    renderWithProviders(<HomePage widgets={[]} />);
    expectChartControls(await chartLoaded());
    // The turnout chart is the page's only data chart.
    expect(screen.getAllByRole('button', { name: 'CSV' })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: 'Table' })).toHaveLength(1);
  });

  it('shows the latest event, the club pulse, main widgets and the me prompt', async () => {
    renderWithProviders(<HomePage widgets={widgets} />);
    expect(screen.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toBeInTheDocument();
    expect(
      await screen.findByText('Winners: Finnegan, Stanton & Stockton, Ethan — 49'),
    ).toBeInTheDocument();
    expect(screen.getByText('next sunday for null')).toBeInTheDocument();
    const panel = screen.getByRole('complementary', { name: 'Personal' });
    expect(within(panel).getByText(/tap “That’s me”/)).toBeInTheDocument();
    await chartLoaded();
  });

  it('personalizes the me panel and passes the me id to widgets', async () => {
    setMe(3);
    renderWithProviders(<HomePage widgets={widgets} />);
    const panel = screen.getByRole('complementary', { name: 'Personal' });
    expect(await within(panel).findByText('37 · 16th')).toBeInTheDocument();
    expect(within(panel).getByText('next trophy for 3')).toBeInTheDocument();
    expect(screen.getByText('next sunday for 3')).toBeInTheDocument();
    await chartLoaded();
  });

  it('gives every landmark a unique name', async () => {
    setMe(3);
    renderWithProviders(<HomePage widgets={widgets} />);
    await chartLoaded();
    await screen.findByText('37 · 16th');
    const names = [...screen.getAllByRole('region'), ...screen.getAllByRole('complementary')].map(
      landmarkName,
    );
    expect(names).not.toContain('');
    expect(names.filter((name, i) => names.indexOf(name) !== i)).toEqual([]);
    // The panel card stays inside the complementary landmark.
    expect(
      within(screen.getByRole('complementary', { name: 'Personal' })).getByRole('region', {
        name: 'Your panel',
      }),
    ).toBeInTheDocument();
  });

  it('stale me id falls back to the prompt after choosing again', async () => {
    setMe(999);
    const user = userEvent.setup();
    renderWithProviders(<HomePage widgets={widgets} />);
    await user.click(await screen.findByRole('button', { name: 'Choose again' }));
    await waitFor(() => expect(screen.getByText(/tap “That’s me”/)).toBeInTheDocument());
    expect(screen.getByText('next sunday for null')).toBeInTheDocument();
    await chartLoaded();
  });

  it('renders hero widgets under the title, above the latest event', async () => {
    const hero: HomeWidget = {
      id: 'hero',
      order: 1,
      slot: 'hero',
      Component: () => <p>hero widget</p>,
    };
    renderWithProviders(<HomePage widgets={[hero, ...widgets]} />);
    const heroText = screen.getByText('hero widget');
    const latest = await screen.findByText('Winners: Finnegan, Stanton & Stockton, Ethan — 49');
    expect(
      heroText.compareDocumentPosition(latest) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    await chartLoaded();
  });
});
