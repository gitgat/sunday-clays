import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import type { InsightChart } from '../../insights/api';
import { chartHref } from '../../insights/chartLink';
import { onThisDayPost, postFixture, trophyPost } from '../mocks';
import { SeeWhy } from './SeeWhy';

describe('SeeWhy', () => {
  it('opens an insight post’s chart with its own window and highlight, never a round type', () => {
    const post = postFixture();
    renderWithProviders(<SeeWhy post={post} />, { route: '/?rt=sporting' });
    const link = screen.getByRole('link', {
      name: "See why: Ike Hadley's scores, with the personal-best line",
    });
    expect(link).toHaveTextContent('See why →');
    const chart = post.see_why.chart;
    if (chart == null) throw new Error('the fixture post links a chart');
    expect(link).toHaveAttribute('href', chartHref(chart, null));
    expect(link.getAttribute('href')).toContain('trend.hl=2026-09-27');
    expect(link.getAttribute('href')).toContain('#chart-trend');
    expect(link.getAttribute('href')).not.toContain('rt=');
  });

  it('carries the viewer’s explicit window when the chart has no dates of its own', () => {
    const base = postFixture();
    const chart = base.see_why.chart;
    if (chart == null) throw new Error('the fixture post links a chart');
    // An Explorer chart with no dates of its own follows the viewer's window.
    const open: InsightChart = {
      ...chart,
      type: 'explorer',
      route: null,
      anchor: null,
      params: {},
      spec: {
        metric: 'adjusted',
        agg: 'avg',
        group_by: ['precip_band'],
        sort: 'key_asc',
        limit: 500,
        filters: {
          date_from: null,
          date_to: null,
          shooter_ids: [3],
          round_types: [],
          statuses: [],
          gauges: [],
          min_rounds: 0,
          best_round_only: true,
          min_score: null,
          ytd: null,
        },
      },
    };
    const post = postFixture({ see_why: { ...base.see_why, chart: open } });
    renderWithProviders(<SeeWhy post={post} />, { route: '/?rt=sporting&w=6m' });
    const href = screen.getByRole('link', { name: /^See why: / }).getAttribute('href');
    expect(href).toBe(chartHref(open, '6m'));
    expect(href).not.toBe(chartHref(open, null));
    expect(href).toContain('w=6m');
    expect(href).not.toContain('rt=');
  });

  it('reads in the second person on the viewer’s own post, where a label exists', () => {
    renderWithProviders(<SeeWhy post={postFixture()} you />);
    expect(
      screen.getByRole('link', { name: 'See why: Your scores, with the personal-best line' }),
    ).toBeInTheDocument();
  });

  it('keeps the plain label on the viewer’s own post when there is no second-person one', () => {
    renderWithProviders(<SeeWhy post={trophyPost} you />);
    expect(
      screen.getByRole('link', { name: 'See why: First win in the Trophy Room' }),
    ).toBeInTheDocument();
  });

  it('opens a trophy’s Trophy Room entry and keeps the global filters', () => {
    renderWithProviders(<SeeWhy post={trophyPost} />, { route: '/?rt=sporting' });
    expect(
      screen.getByRole('link', { name: 'See why: First win in the Trophy Room' }),
    ).toHaveAttribute('href', '/achievements/first_win?rt=sporting');
  });

  it('opens that Sunday’s page for "On this day"', () => {
    renderWithProviders(<SeeWhy post={onThisDayPost} />, { route: '/?rt=sporting' });
    expect(screen.getByRole('link', { name: "See why: That Sunday's results" })).toHaveAttribute(
      'href',
      '/events/2025-09-28?rt=sporting',
    );
  });
});
