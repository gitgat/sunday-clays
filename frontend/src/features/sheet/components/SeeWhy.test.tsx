import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
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

  it('opens a trophy’s Trophy Room entry and keeps the global filters', () => {
    renderWithProviders(<SeeWhy post={trophyPost} />, { route: '/?rt=sporting' });
    expect(
      screen.getByRole('link', { name: 'See why: First win in the Trophy Room' }),
    ).toHaveAttribute('href', '/achievements/first_win?rt=sporting');
  });

  it('opens that Sunday’s page for "On this day"', () => {
    renderWithProviders(<SeeWhy post={onThisDayPost} />);
    expect(screen.getByRole('link', { name: "See why: That Sunday's results" })).toHaveAttribute(
      'href',
      '/events/2025-09-28',
    );
  });
});
