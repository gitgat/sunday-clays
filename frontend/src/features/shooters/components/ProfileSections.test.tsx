import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { ProfileSections } from './ProfileSections';

describe('ProfileSections', () => {
  it('wraps each section in a card titled by its title and passes the shooter id to its component', () => {
    renderWithProviders(
      <ProfileSections
        shooterId={3}
        sections={[
          {
            id: 'trophies',
            title: 'Trophy case',
            order: 10,
            Component: ({ shooterId }) => <p>trophies of {shooterId}</p>,
          },
        ]}
      />,
    );
    // D5: a Card titled `title` is a region named by its h2, with the section's component inside it.
    const region = screen.getByRole('region', { name: 'Trophy case' });
    expect(
      within(region).getByRole('heading', { level: 2, name: 'Trophy case' }),
    ).toBeInTheDocument();
    expect(within(region).getByText('trophies of 3')).toBeInTheDocument();
  });

  it('renders a bare section as is, without a card around it', () => {
    renderWithProviders(
      <ProfileSections
        shooterId={3}
        sections={[
          {
            id: 'bare',
            title: 'Bare',
            order: 1,
            bare: true,
            Component: ({ shooterId }) => <p>bare {shooterId}</p>,
          },
        ]}
      />,
    );
    expect(screen.getByText('bare 3')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Bare' })).toBeNull();
  });
});
