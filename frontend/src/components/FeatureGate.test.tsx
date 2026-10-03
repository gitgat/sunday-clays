import { act, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../test/msw/server';
import { FEATURES_QUERY_KEY } from '../lib/features';
import { renderWithProviders } from '../test/render';
import { FeatureGate } from './FeatureGate';

const off = () => server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));

describe('FeatureGate', () => {
  it('shows "Page not found" to a viewer while the switch is off', async () => {
    off();
    renderWithProviders(
      <FeatureGate feature="club_milestones">
        <h1>Milestones</h1>
      </FeatureGate>,
      { role: 'viewer' },
    );
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Milestones' })).not.toBeInTheDocument();
  });

  it('shows the page to an admin while the switch is off (preview)', async () => {
    off();
    renderWithProviders(
      <FeatureGate feature="club_milestones">
        <h1>Milestones</h1>
      </FeatureGate>,
      { role: 'admin' },
    );
    expect(await screen.findByRole('heading', { name: 'Milestones' })).toBeInTheDocument();
  });

  it('shows the page to a viewer while the switch is on', async () => {
    renderWithProviders(
      <FeatureGate feature="club_milestones">
        <h1>Milestones</h1>
      </FeatureGate>,
    );
    expect(await screen.findByRole('heading', { name: 'Milestones' })).toBeInTheDocument();
  });

  it('says the page could not load when the switches cannot be read', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.error()));
    renderWithProviders(
      <FeatureGate feature="club_milestones">
        <h1>Milestones</h1>
      </FeatureGate>,
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load this page');
  });

  it('keeps showing the page when a later refetch of the switches fails', async () => {
    const { queryClient } = renderWithProviders(
      <FeatureGate feature="club_milestones">
        <h1>Milestones</h1>
      </FeatureGate>,
    );
    expect(await screen.findByRole('heading', { name: 'Milestones' })).toBeInTheDocument();
    server.use(http.get('*/api/features', () => HttpResponse.error()));
    await act(() => queryClient.refetchQueries({ queryKey: FEATURES_QUERY_KEY }));
    expect(queryClient.getQueryState(FEATURES_QUERY_KEY)?.status).toBe('error');
    await new Promise((resolve) => setTimeout(resolve, 50)); // let the error reach the hook
    expect(screen.getByRole('heading', { name: 'Milestones' })).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
