import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import type { Notable } from '../api';
import { NotablesCard } from './NotablesCard';

const pb: Notable = {
  kind: 'pb',
  shooter_id: 12,
  display_name: 'Nordquist, Sherman',
  detail: 'New personal best 42 (was 40)',
  value: 42,
};
const first: Notable = {
  kind: 'first_timer',
  shooter_id: 30,
  display_name: 'Lee, Casey',
  detail: 'First round: 31',
  value: 31,
};
// A kind a newer server might send (cast: outside today's union); it is still shown verbatim.
const other = {
  kind: 'milestone',
  shooter_id: 7,
  display_name: 'Abernathy, Preston',
  detail: '250 Sundays',
  value: 250,
} as unknown as Notable;

describe('NotablesCard', () => {
  it('leaves personal bests and first rounds to the insights', () => {
    renderWithProviders(<NotablesCard notables={[pb, first, other]} />);
    expect(screen.getByText('milestone')).toBeInTheDocument();
    expect(screen.queryByText(/New personal best/)).not.toBeInTheDocument();
    expect(screen.queryByText(/First round: 31/)).not.toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
  });

  it('renders nothing when only insight-told rows remain', () => {
    const { container } = renderWithProviders(<NotablesCard notables={[pb, first]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
