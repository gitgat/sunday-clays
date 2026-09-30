import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse, type JsonBodyType } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { expectExplainer } from '../../../test/charts';
import { gilchristDetail } from '../../shooters/mocks';
import { NEXT_PREDICTIONS } from '../mocks';
import { ProfileOutlook } from './ProfileOutlook';

function serve(body: JsonBodyType, status = 200) {
  server.use(http.get('*/api/predictions/next', () => HttpResponse.json(body, { status })));
}

describe('ProfileOutlook', () => {
  it("shows the shooter's own expected score and likely range", async () => {
    serve(NEXT_PREDICTIONS);
    renderWithProviders(<ProfileOutlook shooterId={121} />);
    const outlook = await screen.findByRole('region', { name: 'Next Sunday outlook' });
    expect(
      await within(outlook).findByText('Expected around 41 next Sunday, likely 37–46.'),
    ).toBeInTheDocument();
    expect(within(outlook).queryByText(/odds|chance|podium/i)).not.toBeInTheDocument();
  });

  it('explains the expected score', async () => {
    serve(NEXT_PREDICTIONS);
    renderWithProviders(<ProfileOutlook shooterId={121} />);
    const outlook = await screen.findByRole('region', { name: 'Next Sunday outlook' });
    await within(outlook).findByText(/Expected around/);
    await expectExplainer(outlook, 'About this expected score', { read: true });
  });

  it('says when there is no expectation yet, without judging', async () => {
    serve(NEXT_PREDICTIONS);
    renderWithProviders(<ProfileOutlook shooterId={7} />);
    expect(
      await screen.findByText(
        'No expected score for Sun, Oct 4 yet. It builds from the Sundays shot, out of the last 13.',
      ),
    ).toBeInTheDocument();
  });

  it('explains that predictions need an analytics run', async () => {
    serve({ ...NEXT_PREDICTIONS, model_ready: false, shooters: [] });
    renderWithProviders(<ProfileOutlook shooterId={121} />);
    expect(
      await screen.findByText('Predictions appear after the first analytics run.'),
    ).toBeInTheDocument();
  });

  it('says nothing about next Sunday for a shooter who has died', async () => {
    serve({
      ...NEXT_PREDICTIONS,
      shooters: NEXT_PREDICTIONS.shooters.map((s) => ({ ...s, shooter_id: 41 })),
    });
    server.use(http.get('*/api/shooters/:id', () => HttpResponse.json(gilchristDetail)));
    renderWithProviders(<ProfileOutlook shooterId={41} />);
    await waitFor(() => {
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });
    expect(screen.queryByRole('region', { name: 'Next Sunday outlook' })).not.toBeInTheDocument();
    expect(screen.queryByText(/next Sunday|No expected score/)).not.toBeInTheDocument();
  });

  it('reports a failed request', async () => {
    serve({ error: { code: 'internal', message: 'Internal server error' } }, 500);
    renderWithProviders(<ProfileOutlook shooterId={121} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load predictions.');
  });
});
