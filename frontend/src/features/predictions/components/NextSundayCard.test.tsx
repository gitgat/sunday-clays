import { screen, within } from '@testing-library/react';
import { http, HttpResponse, type JsonBodyType } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { expectExplainer } from '../../../test/charts';
import { NEXT_PREDICTIONS } from '../mocks';
import { NextSundayCard } from './NextSundayCard';

function serve(body: JsonBodyType, status = 200) {
  server.use(http.get('*/api/predictions/next', () => HttpResponse.json(body, { status })));
}

describe('NextSundayCard', () => {
  it('shows the forecast, the predicted field median and the difficulty', async () => {
    serve(NEXT_PREDICTIONS);
    renderWithProviders(<NextSundayCard meId={null} />);
    const card = await screen.findByRole('region', { name: 'Next Sunday' });
    expect(await within(card).findByText('Sun, Oct 4')).toBeInTheDocument();
    expect(
      within(card).getByText('Forecast 10:00–12:00: 54°F · gusts to 12 mph · 0.02 in rain · Rain'),
    ).toBeInTheDocument();
    expect(within(card).getByText('Predicted field median')).toBeInTheDocument();
    expect(within(card).getByText('36')).toBeInTheDocument();
    expect(within(card).getByText('About 27 shooters')).toBeInTheDocument();
    expect(within(card).getByText(/About 1.2 targets harder/)).toBeInTheDocument();
  });

  it('never ranks shooters or shows odds', async () => {
    serve(NEXT_PREDICTIONS);
    renderWithProviders(<NextSundayCard meId={null} />);
    const card = await screen.findByRole('region', { name: 'Next Sunday' });
    await within(card).findByText('Predicted field median');
    expect(within(card).queryByText(/odds|chance to win|podium/i)).not.toBeInTheDocument();
    expect(within(card).queryByText(/Abernathy|Finnegan|Hadley/)).not.toBeInTheDocument();
    expect(within(card).queryByRole('button', { name: 'CSV' })).not.toBeInTheDocument();
  });

  it('shows the viewer their own expected score after That’s me', async () => {
    serve(NEXT_PREDICTIONS);
    renderWithProviders(<NextSundayCard meId={121} />);
    expect(
      await screen.findByText('Expected around 41 next Sunday, likely 37–46.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Your expected score:')).toBeInTheDocument();
  });

  it('points to Shooters when nobody is picked, with a link that keeps the filters', async () => {
    serve(NEXT_PREDICTIONS);
    renderWithProviders(<NextSundayCard meId={null} />, { route: '/?rt=sporting' });
    const link = await screen.findByRole('link', { name: 'Go to Shooters' });
    expect(link).toHaveAttribute('href', '/shooters?rt=sporting');
    expect(screen.getByText(/Choose “That’s me”/)).toBeInTheDocument();
  });

  it('says so when the viewer has no expectation yet', async () => {
    serve(NEXT_PREDICTIONS);
    renderWithProviders(<NextSundayCard meId={7} />);
    expect(
      await screen.findByText(
        'No expected score for you yet. It builds from the Sundays you shoot, out of the last 13.',
      ),
    ).toBeInTheDocument();
  });

  it('explains what the numbers mean', async () => {
    serve(NEXT_PREDICTIONS);
    renderWithProviders(<NextSundayCard meId={null} />);
    const card = await screen.findByRole('region', { name: 'Next Sunday' });
    await within(card).findByText('Predicted field median');
    await expectExplainer(card, 'About these predictions', { read: true });
  });

  it('says when there is no forecast yet', async () => {
    serve({ ...NEXT_PREDICTIONS, forecast: null, difficulty_source: 'prior', difficulty: null });
    renderWithProviders(<NextSundayCard meId={null} />);
    expect(
      await screen.findByText('No forecast yet. It appears a few days before the shoot.'),
    ).toBeInTheDocument();
  });

  it('explains that predictions need an analytics run', async () => {
    serve({ ...NEXT_PREDICTIONS, model_ready: false, field_median: null, shooters: [] });
    renderWithProviders(<NextSundayCard meId={null} />);
    expect(
      await screen.findByText('Predictions appear after the first analytics run.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('Predicted field median')).not.toBeInTheDocument();
  });

  it('handles an empty field and a missing median', async () => {
    serve({ ...NEXT_PREDICTIONS, field_median: null, expected_turnout: 0, shooters: [] });
    renderWithProviders(<NextSundayCard meId={null} />);
    expect(await screen.findByText('Nobody has shot in the last 13 Sundays.')).toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('reports a failed request', async () => {
    serve({ error: { code: 'internal', message: 'Internal server error' } }, 500);
    renderWithProviders(<NextSundayCard meId={null} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load predictions.');
  });
});
