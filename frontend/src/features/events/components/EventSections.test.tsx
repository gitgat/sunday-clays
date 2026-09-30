import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import type { EventSection } from '../sections';
import { EventSections } from './EventSections';

const sections: EventSection[] = [
  { id: 'b', title: 'Second block', order: 2, Component: ({ date }) => <p>second for {date}</p> },
  { id: 'a', title: 'First block', order: 1, Component: ({ date }) => <p>first for {date}</p> },
];

describe('EventSections', () => {
  it('renders each section title and passes the event date to its component', () => {
    renderWithProviders(<EventSections date="2026-09-13" sections={sections} />);
    expect(screen.getByText('First block')).toBeInTheDocument();
    expect(screen.getByText('first for 2026-09-13')).toBeInTheDocument();
    expect(screen.getByText('second for 2026-09-13')).toBeInTheDocument();
  });

  it('renders a bare section as is, without a card around it', () => {
    renderWithProviders(
      <EventSections
        date="2026-09-13"
        sections={[
          {
            id: 'bare',
            title: 'Bare',
            order: 1,
            bare: true,
            Component: ({ date }) => <p>bare {date}</p>,
          },
        ]}
      />,
    );
    expect(screen.getByText('bare 2026-09-13')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Bare' })).toBeNull();
  });
});
