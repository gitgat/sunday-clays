import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { BumpsProvider } from '../../bumps/BumpsProvider';
import { insightFixture } from '../mocks';
import { Segments } from '../segments';
import { InsightCard } from './InsightCard';

function renderCard(props: Parameters<typeof InsightCard>[0]) {
  return renderWithProviders(
    <ul>
      <InsightCard {...props} />
    </ul>,
  );
}

describe('Segments', () => {
  it('renders names as profile links and numbers as text, never as HTML', () => {
    renderWithProviders(
      <p>
        <Segments
          segments={[
            { t: 'text', v: '<b>hi</b> ' },
            { t: 'shooter', v: 'Ike Hadley', id: 3 },
            { t: 'num', v: '46' },
          ]}
        />
      </p>,
    );
    expect(screen.getByRole('link', { name: 'Ike Hadley' })).toHaveAttribute('href', '/shooters/3');
    expect(screen.getByText('<b>hi</b>', { exact: false })).toBeInTheDocument();
    expect(document.querySelector('b')).toBeNull();
  });
});

describe('Segments variants', () => {
  it('renders trophies, plain shooters without an id and unknown parts as text', () => {
    renderWithProviders(
      <p>
        <Segments
          segments={[
            { t: 'trophy', v: 'Century' },
            { t: 'shooter', v: 'No Id' },
            { t: 'shooter', v: 'Null Id', id: null },
          ]}
        />
      </p>,
    );
    expect(screen.getByText('Century')).toBeInTheDocument();
    expect(screen.getByText('No Id')).toBeInTheDocument();
    expect(screen.queryByRole('link')).toBeNull();
  });
});

describe('InsightCard', () => {
  it('reads in the third person with a chart link and the rules behind it', async () => {
    const { user } = renderCard({ insight: insightFixture() });
    expect(screen.getByText(/New personal best for/)).toBeInTheDocument();
    const link = screen.getByRole('link', {
      name: "See the chart: Ike Hadley's scores, with the personal-best line",
    });
    expect(link.getAttribute('href')).toContain('#chart-trend');
    const toggle = screen.getByRole('button', { name: 'How we worked it out' });
    await user.click(toggle);
    const panel = document.getElementById(toggle.getAttribute('aria-controls') ?? '');
    expect(panel).not.toBeNull();
    expect(
      within(panel ?? document.body).getByText('The best round beats every earlier round.'),
    ).toBeInTheDocument();
  });

  it('uses the "you" wording for that shooter viewing their own insight', async () => {
    const { user } = renderCard({ insight: insightFixture(), you: true });
    expect(screen.getByText(/New personal best:/)).toBeInTheDocument();
    expect(screen.queryByText(/for$/)).toBeNull();
    expect(
      screen.getByRole('link', { name: 'See the chart: Your scores, with the personal-best line' }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'How we worked it out' }));
    expect(
      screen.getByText('Your best round beats every earlier round of yours.'),
    ).toBeInTheDocument();
  });

  it('tags a new insight and falls back to third person when there is no "you" form', () => {
    renderCard({ insight: insightFixture({ is_new: true, headline_you: null }), you: true });
    expect(screen.getByText('New')).toBeInTheDocument();
    expect(screen.getByText(/New personal best for/)).toBeInTheDocument();
  });

  it('keeps a global round-type filter off the chart link but on the name link', () => {
    renderWithProviders(
      <ul>
        <InsightCard insight={insightFixture()} />
      </ul>,
      { route: '/shooters/3?rt=super_sporting' },
    );
    const chart = screen.getByRole('link', { name: /^See the chart/ });
    expect(chart.getAttribute('href')).not.toContain('rt=');
    expect(chart.getAttribute('href')).toContain('trend.from=');
    expect(screen.getByRole('link', { name: 'Ike Hadley' })).toHaveAttribute(
      'href',
      '/shooters/3?rt=super_sporting',
    );
  });

  it('opens the insight dates as a Custom window, or keeps the viewer window when it has none', () => {
    const base = insightFixture();
    const explorer = (dates: boolean) =>
      insightFixture({
        chart: {
          ...base.chart,
          type: 'explorer',
          route: null,
          anchor: null,
          params: {},
          spec: {
            metric: 'score',
            agg: 'avg',
            group_by: ['year'],
            sort: 'key_asc',
            limit: 500,
            filters: {
              date_from: dates ? '2026-05-03' : null,
              date_to: dates ? '2026-09-27' : null,
              shooter_ids: [],
              round_types: [],
              statuses: [],
              gauges: [],
              min_rounds: 0,
              best_round_only: false,
            },
          },
        },
      });
    const { unmount } = renderWithProviders(
      <ul>
        <InsightCard insight={explorer(true)} />
      </ul>,
      { route: '/?w=3m' },
    );
    const own = screen.getByRole('link', { name: /^See the chart/ }).getAttribute('href');
    expect(new URLSearchParams(own?.split('?')[1]).get('w')).toBe('2026-05-03..2026-09-27');
    expect(own).not.toMatch(/[?&](from|to)=/);
    unmount();
    renderWithProviders(
      <ul>
        <InsightCard insight={explorer(false)} />
      </ul>,
      { route: '/?w=3m' },
    );
    const kept = screen.getByRole('link', { name: /^See the chart/ }).getAttribute('href');
    expect(new URLSearchParams(kept?.split('?')[1]).get('w')).toBe('3m');
  });

  it('lists extra charts, using the "you" label when it is for the viewer', () => {
    const base = insightFixture();
    const also = [
      { ...base.chart, anchor: 'other', label: 'Their other chart', label_you: 'Your other chart' },
      { ...base.chart, anchor: 'third', label: 'Third chart', label_you: null },
    ];
    renderCard({ insight: { ...base, chart: { ...base.chart, also } }, you: true });
    expect(
      screen.getByRole('link', { name: 'See the chart: Your other chart' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See the chart: Third chart' })).toBeInTheDocument();
  });

  it('keeps two identical extra charts as separate links without key warnings', () => {
    const base = insightFixture();
    const same = { ...base.chart, anchor: 'dup', label: 'Same chart', label_you: null };
    const errors = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    renderCard({ insight: { ...base, chart: { ...base.chart, also: [same, same] } } });
    expect(screen.getAllByRole('link', { name: 'See the chart: Same chart' })).toHaveLength(2);
    expect(errors).not.toHaveBeenCalled();
    errors.mockRestore();
  });

  it('falls back to the third-person bullets and chart label', async () => {
    const base = insightFixture();
    const { user } = renderCard({
      insight: { ...base, how_you: null, chart: { ...base.chart, label_you: null } },
      you: true,
    });
    expect(
      screen.getByRole('link', { name: `See the chart: ${base.chart.label}` }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'How we worked it out' }));
    expect(screen.getByText('The best round beats every earlier round.')).toBeInTheDocument();
  });
});

describe('InsightCard bumps', () => {
  it('carries its key and a fist bump inside a BumpsProvider', async () => {
    const { container } = renderWithProviders(
      <BumpsProvider keys={['k-pb-3']}>
        <ul>
          <InsightCard insight={insightFixture()} />
        </ul>
      </BumpsProvider>,
    );
    expect(container.querySelector('li')).toHaveAttribute('data-insight-key', 'k-pb-3');
    expect(await screen.findByRole('button', { name: 'Fist bump, 0 bumps' })).toBeInTheDocument();
  });

  it('has no fist bump on its own', () => {
    renderWithProviders(
      <ul>
        <InsightCard insight={insightFixture()} />
      </ul>,
    );
    expect(screen.queryByRole('button', { name: /^Fist bump/ })).toBeNull();
  });
});
