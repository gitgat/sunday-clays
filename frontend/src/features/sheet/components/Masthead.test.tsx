import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { sheetFixture } from '../mocks';
import { Masthead } from './Masthead';

describe('Masthead sharing', () => {
  it('offers "Share this Sheet" beside, not inside, the issues navigation', () => {
    renderWithProviders(<Masthead issue={sheetFixture()} />);
    const share = screen.getByRole('button', { name: 'Share this Sheet' });
    expect(
      within(screen.getByRole('navigation', { name: 'Issues' })).queryByRole('button'),
    ).toBeNull();
    expect(share).toBeInTheDocument();
  });
});
