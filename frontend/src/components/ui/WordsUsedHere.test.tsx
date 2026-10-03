import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { ExplainerPanel } from './Explainer';

const explainer = {
  what: 'Shows things.',
  computed: ['Field-adjusted score is used.'],
  terms: ['field-adjusted', 'percentile'] as const,
};

describe('Words used here', () => {
  it('links each term to its glossary anchor while the glossary is visible', async () => {
    server.use(
      http.get('*/api/features', () => HttpResponse.json({ switches: { tour_glossary: true } })),
    );
    renderWithProviders(<ExplainerPanel id="x" explainer={explainer} />);
    const link = await screen.findByRole('link', { name: 'Field-adjusted score' });
    expect(link).toHaveAttribute('href', '/glossary#field-adjusted');
    expect(link).toHaveClass('min-h-11');
    expect(screen.getByRole('link', { name: 'Percentile' })).toHaveAttribute(
      'href',
      '/glossary#percentile',
    );
    expect(screen.getByText('Words used here:')).toBeInTheDocument();
  });

  it('is hidden while the glossary is off for a viewer', async () => {
    renderWithProviders(<ExplainerPanel id="x" explainer={explainer} />); // default: off
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByText('Words used here:')).not.toBeInTheDocument();
  });

  it('renders nothing for an explainer without terms (no query either)', () => {
    renderWithProviders(<ExplainerPanel id="x" explainer={{ what: 'a', computed: ['b'] }} />);
    expect(screen.queryByText('Words used here:')).not.toBeInTheDocument();
  });
});
