import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { insightFixture } from '../mocks';
import { leadSubtitle, SheetLead } from './SheetLead';

const DAY = '2026-09-27';

const hero = insightFixture({
  key: 'hero',
  kind: 'lb.most-improved',
  headline: [
    { t: 'text', v: 'Most improved this year: ' },
    { t: 'shooter', v: 'Amy Ace', id: 1 },
    { t: 'text', v: '.' },
  ],
  subject_id: '1',
});
const recap = insightFixture({
  key: 'recap',
  kind: 'home.sunday-recap',
  family: 'recap',
  subject_type: 'sunday',
  subject_id: '2026-09-27',
  headline: [{ t: 'text', v: '23 shooters came out; the top score was 49.' }],
  headline_you: null,
});
const spotlight = insightFixture(); // Ike Hadley (3), with a "you" twin

describe('SheetLead', () => {
  it('shows the headline with the recap as its deck, then the spotlight', () => {
    renderWithProviders(
      <SheetLead headline={hero} recap={recap} spotlight={spotlight} meId={null} date={DAY} />,
    );
    const lead = screen.getByRole('region', { name: 'Top story' });
    expect(within(lead).getByRole('list', { name: 'Top story' })).toHaveTextContent(
      'Most improved this year: Amy Ace.',
    );
    expect(
      within(lead).getByText('23 shooters came out; the top score was 49.'),
    ).toBeInTheDocument();
    const spot = screen.getByRole('region', { name: 'Spotlight' });
    expect(within(spot).getByText('Shooter to know')).toBeInTheDocument();
    expect(within(spot).getByRole('link', { name: 'Ike Hadley' })).toHaveAttribute(
      'href',
      '/shooters/3',
    );
    expect(lead.compareDocumentPosition(spot) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('clamps the deck to three lines until "Show all", and links the results', async () => {
    const { user } = renderWithProviders(
      <SheetLead headline={hero} recap={recap} spotlight={null} meId={null} date={DAY} />,
    );
    const deck = screen.getByText('23 shooters came out; the top score was 49.').closest('p');
    expect(deck).toHaveClass('line-clamp-3');
    await user.click(screen.getByRole('button', { name: 'Show all' }));
    expect(deck).not.toHaveClass('line-clamp-3');
    await user.click(screen.getByRole('button', { name: 'Show less' }));
    expect(deck).toHaveClass('line-clamp-3');
    expect(screen.getByRole('link', { name: 'See the results' })).toHaveAttribute(
      'href',
      expect.stringContaining('/shooters/3?'),
    );
  });

  it('reads the viewer’s own spotlight in the second person', () => {
    renderWithProviders(
      <SheetLead headline={null} recap={null} spotlight={spotlight} meId={3} date={DAY} />,
    );
    expect(screen.getByRole('list', { name: 'Spotlight' })).toHaveTextContent(
      'New personal best: 46.',
    );
    expect(screen.queryByRole('region', { name: 'Top story' })).toBeNull();
  });

  it('shows the deck alone when the Sunday has no headline pick', () => {
    renderWithProviders(
      <SheetLead headline={null} recap={recap} spotlight={null} meId={null} date={DAY} />,
    );
    expect(screen.getByRole('region', { name: 'Top story' })).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Top story' })).toBeNull();
    expect(screen.getByText('23 shooters came out; the top score was 49.')).toBeInTheDocument();
  });

  it('names the Sunday a headline is about when it is not the issue’s', () => {
    renderWithProviders(
      <SheetLead
        headline={{ ...hero, anchor_date: '2026-09-20' }}
        recap={null}
        spotlight={null}
        meId={null}
        date={DAY}
      />,
    );
    expect(screen.getByText('Sep 20, 2026 · not affected by the time filter')).toBeInTheDocument();
    expect(leadSubtitle(hero, DAY)).toBe('Not affected by the time filter');
    expect(leadSubtitle({ ...hero, anchor_date: null }, DAY)).toBe(
      'Not affected by the time filter',
    );
  });

  it('renders nothing when the Sunday has no lead at all', () => {
    const { container } = renderWithProviders(
      <SheetLead headline={null} recap={null} spotlight={null} meId={null} date={DAY} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
