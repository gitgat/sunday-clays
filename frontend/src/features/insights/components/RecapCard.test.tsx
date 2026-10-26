import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { SUNDAY_THROWN_OUT, THROWN_OUT_RECAP_LINE } from '../../events/thrownOut';
import { insightFixture } from '../mocks';
import { RecapCard } from './RecapCard';

describe('RecapCard thrown-out Sunday', () => {
  it('discloses a thrown-out Sunday from its how line', () => {
    const base = insightFixture();
    const how = [...base.how, [{ t: 'text' as const, v: THROWN_OUT_RECAP_LINE }]];
    renderWithProviders(<RecapCard insight={insightFixture({ how })} />);
    expect(screen.getByTitle(SUNDAY_THROWN_OUT)).toBeInTheDocument();
    expect(screen.getByText(THROWN_OUT_RECAP_LINE)).toBeInTheDocument();
  });

  it('a normal recap has no mark', () => {
    renderWithProviders(<RecapCard insight={insightFixture()} />);
    expect(screen.queryByTitle(SUNDAY_THROWN_OUT)).toBeNull();
  });
});
