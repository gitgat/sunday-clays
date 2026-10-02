import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { CLAYSMASHER_BUTTON_ENABLED, CLAYSMASHER_LINK_MODE } from '../links';
import { ImportIntoClaySmasher } from './ImportIntoClaySmasher';

const WEB = 'https://claysmasher.com/link/sunday-clays?shooter=3';

describe('ImportIntoClaySmasher', () => {
  // The flag-flip PR (spec §11 step 4) updates this test, and only this test.
  it('ships off, in universal mode', () => {
    expect(CLAYSMASHER_BUTTON_ENABLED).toBe(false);
    expect(CLAYSMASHER_LINK_MODE).toBe('universal');

    renderWithProviders(<ImportIntoClaySmasher shooterId={3} />);

    expect(screen.queryByRole('link', { name: /ClaySmasher/ })).toBeNull();
  });

  it('is a plain same-tab link to the claysmasher.com page', () => {
    renderWithProviders(<ImportIntoClaySmasher shooterId={3} enabled mode="universal" />);

    const link = screen.getByRole('link', { name: 'Import into ClaySmasher' });
    expect(link).toHaveAttribute('href', WEB);
    expect(link).not.toHaveAttribute('target');
    expect(link).not.toHaveAttribute('rel');
    expect(screen.getAllByRole('link')).toHaveLength(1);
  });

  it('scheme mode adds a web link for phones without the app', () => {
    renderWithProviders(<ImportIntoClaySmasher shooterId={3} enabled mode="scheme" />);

    expect(screen.getByRole('link', { name: 'Import into ClaySmasher' })).toHaveAttribute(
      'href',
      'claysmasher://sunday-clays/link?shooter=3',
    );
    const fallback = screen.getByRole('link', { name: 'Don’t have ClaySmasher?' });
    expect(fallback).toHaveAttribute('href', WEB);
    expect(fallback).not.toHaveAttribute('target');
  });
});
