import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { expectExplainer } from '../../test/charts';
import { server } from '../../test/msw/server';
import { shooterAchievementsFixture } from './mocks';
import { NextTrophy } from './NextTrophy';

function renderWidget(meId: number | null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <NextTrophy meId={meId} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('NextTrophy', () => {
  it('asks the viewer to pick themselves first', () => {
    renderWidget(null);
    expect(screen.getByText(/see your next trophy/)).toBeInTheDocument();
  });

  it('lists the three tiers closest to done', async () => {
    renderWidget(12);
    const region = await screen.findByRole('region', { name: 'Your next trophy' });
    const items = within(region).getAllByRole('listitem');
    expect(
      items.map(
        (item) => within(item).getByText(/Round Score|Events Attended|Clays Broken/).textContent,
      ),
    ).toEqual(['Round Score', 'Events Attended', 'Clays Broken']);
    expect(within(region).getByText('1,742 / 2,500 clays broken')).toBeInTheDocument();
  });

  it('explains how the next trophies are picked', async () => {
    renderWidget(12);
    const region = await screen.findByRole('region', { name: 'Your next trophy' });
    await expectExplainer(region, 'About your next trophy');
  });

  it('breaks equal progress by trophy code', async () => {
    const [first] = shooterAchievementsFixture.progress;
    if (!first) throw new Error('fixture has progress');
    server.use(
      http.get('*/api/shooters/:id/achievements', () =>
        HttpResponse.json({
          ...shooterAchievementsFixture,
          progress: [
            { ...first, code: 'b_family', name: 'Bee', fraction: 0.5 },
            { ...first, code: 'a_family', name: 'Aye', fraction: 0.5 },
          ],
        }),
      ),
    );
    renderWidget(12);
    const region = await screen.findByRole('region', { name: 'Your next trophy' });
    expect(
      within(region)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual([expect.stringContaining('Aye'), expect.stringContaining('Bee')]);
  });

  it('celebrates when every tier is earned', async () => {
    server.use(
      http.get('*/api/shooters/:id/achievements', () =>
        HttpResponse.json({
          ...shooterAchievementsFixture,
          progress: shooterAchievementsFixture.progress.filter((p) => p.next_threshold === null),
        }),
      ),
    );
    renderWidget(12);
    expect(await screen.findByText(/Every tier earned/)).toBeInTheDocument();
  });

  it('shows an error when the API fails', async () => {
    server.use(
      http.get('*/api/shooters/:id/achievements', () => new HttpResponse(null, { status: 500 })),
    );
    renderWidget(12);
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });
});
