import { screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { renderWithProviders } from '../../../test/render';
import { AnalyticsPage } from './AnalyticsPage';

afterEach(() => {
  vi.useRealTimers();
});

describe('AnalyticsPage', () => {
  it(
    'shows the window once and the four charts',
    async () => {
      vi.useFakeTimers({ toFake: ['Date'] });
      vi.setSystemTime(new Date(2026, 9, 1, 12, 0));
      renderWithProviders(<AnalyticsPage />, { route: '/admin/analytics' });
      expect(screen.getByRole('heading', { level: 1, name: 'Analytics' })).toBeInTheDocument();
      expect(screen.getByText(/^Last 8 weeks · Aug 7 – Oct 1\./)).toBeInTheDocument();
      for (const name of [
        'Visitors',
        'Busiest days',
        'Page views by page',
        'Fist bumps per day',
        'Most-bumped insights',
        '“Which one are you?” answers',
      ]) {
        expect(await screen.findByRole('region', { name }, LAZY_CHART)).toBeInTheDocument();
      }
    },
    LAZY_TEST_TIMEOUT,
  );
});
