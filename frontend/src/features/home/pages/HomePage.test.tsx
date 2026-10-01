import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { clearMe, getMe, isMeSkipped, setMe, skipMe } from '../../../lib/me';
import { expectChartControls } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { shooterList } from '../../shooters/mocks';
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
    localStorage.removeItem('sc.me.skip');
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
      http.get('*/api/shooters', ({ request }) => {
        const q = (new URL(request.url).searchParams.get('q') ?? '').toLowerCase();
        return HttpResponse.json(
          shooterList.filter((s) => s.display_name.toLowerCase().includes(q)),
        );
      }),
    );
  });

  it('every data chart exposes Table and CSV controls', async () => {
    renderWithProviders(<HomePage widgets={[]} />);
    expectChartControls(await chartLoaded());
    // The turnout chart is the page's only data chart.
    expect(screen.getAllByRole('button', { name: 'CSV' })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: 'Table' })).toHaveLength(1);
  });

  it('shows the latest event, the club pulse, main widgets and asks which one you are', async () => {
    renderWithProviders(<HomePage widgets={widgets} />);
    expect(screen.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toBeInTheDocument();
    expect(
      await screen.findByText('Winners: Finnegan, Stanton & Stockton, Ethan — 49'),
    ).toBeInTheDocument();
    expect(screen.getByText('next sunday for null')).toBeInTheDocument();
    const panel = screen.getByRole('complementary', { name: 'Personal' });
    expect(within(panel).getByRole('heading', { name: 'Which one are you?' })).toBeInTheDocument();
    expect(within(panel).queryByText(/tap “That’s me”/)).toBeNull();
    await chartLoaded();
  });

  it('a pick fills the panel, passes the id on and moves focus to the panel', async () => {
    const user = userEvent.setup();
    renderWithProviders(<HomePage widgets={widgets} />);
    const panel = screen.getByRole('complementary', { name: 'Personal' });
    await user.type(within(panel).getByLabelText('Your name'), 'Hadley');
    await user.click(await within(panel).findByRole('button', { name: 'Hadley, Ike' }));
    expect(await within(panel).findByText('37 · 16th')).toBeInTheDocument();
    expect(within(panel).getByRole('heading', { name: 'Your panel' })).toHaveFocus();
    expect(screen.getByText('next sunday for 3')).toBeInTheDocument();
    expect(getMe()).toBe(3);
    await chartLoaded();
  });

  it('"Not me" forgets the choice and asks again, with focus on the question', async () => {
    setMe(3);
    const user = userEvent.setup();
    renderWithProviders(<HomePage widgets={widgets} />);
    const panel = screen.getByRole('complementary', { name: 'Personal' });
    await user.click(await within(panel).findByRole('button', { name: 'Not me' }));
    expect(within(panel).getByRole('heading', { name: 'Which one are you?' })).toHaveFocus();
    expect(getMe()).toBeNull();
    expect(screen.getByText('next sunday for null')).toBeInTheDocument();
    await chartLoaded();
  });

  it('a skip puts back the usual prompt and is remembered on this browser', async () => {
    const user = userEvent.setup();
    const { unmount } = renderWithProviders(<HomePage widgets={widgets} />);
    const panel = screen.getByRole('complementary', { name: 'Personal' });
    await user.click(within(panel).getByRole('button', { name: 'Not a shooter / skip' }));
    expect(within(panel).getByRole('heading', { name: 'Your panel' })).toHaveFocus();
    expect(within(panel).getByText(/tap “That’s me”/)).toBeInTheDocument();
    expect(isMeSkipped()).toBe(true);
    await chartLoaded();
    unmount();
    renderWithProviders(<HomePage widgets={widgets} />);
    const again = screen.getByRole('complementary', { name: 'Personal' });
    expect(within(again).queryByRole('heading', { name: 'Which one are you?' })).toBeNull();
    expect(within(again).getByText(/tap “That’s me”/)).toBeInTheDocument();
    await chartLoaded();
  });

  it('a skipped browser still shows a chosen shooter', async () => {
    skipMe();
    setMe(3);
    renderWithProviders(<HomePage widgets={widgets} />);
    expect(await screen.findByText('37 · 16th')).toBeInTheDocument();
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

  it('stale me id asks which one you are after choosing again', async () => {
    setMe(999);
    const user = userEvent.setup();
    renderWithProviders(<HomePage widgets={widgets} />);
    await user.click(await screen.findByRole('button', { name: 'Choose again' }));
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Which one are you?' })).toBeInTheDocument(),
    );
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
