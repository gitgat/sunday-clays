import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../test/render';
import { homeWidget } from './homeWidget';
import { profileSection } from './profileSection';

describe('prediction glob exports', () => {
  it('puts the Next Sunday card in the home main column', async () => {
    expect(homeWidget.slot).toBe('main');
    expect(homeWidget.order).toBe(10);
    renderWithProviders(<homeWidget.Component meId={59} />);
    expect(await screen.findByRole('region', { name: 'Next Sunday' })).toBeInTheDocument();
    expect(await screen.findByText('Expected around 35 next Sunday, likely 31–39.')).toBeVisible();
  });

  it('adds the outlook to shooter profiles', async () => {
    expect(profileSection.title).toBe('Next Sunday');
    renderWithProviders(<profileSection.Component shooterId={59} />);
    expect(await screen.findByText('Expected around 35 next Sunday, likely 31–39.')).toBeVisible();
  });
});
