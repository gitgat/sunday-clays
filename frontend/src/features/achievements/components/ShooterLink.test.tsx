import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { ShooterLink } from './ShooterLink';

describe('ShooterLink', () => {
  it('links to the profile and keeps the round-type filter', () => {
    render(
      <MemoryRouter initialEntries={['/achievements?rt=sporting']}>
        <ShooterLink shooterId={12} name="Hadley, Ike" />
      </MemoryRouter>,
    );
    expect(screen.getByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/12?rt=sporting',
    );
  });
});
