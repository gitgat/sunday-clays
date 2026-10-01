import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '../../../test/render';
import { AboutPage } from './AboutPage';

function external(name: RegExp | string): HTMLElement {
  return screen.getByRole('link', { name });
}

describe('AboutPage', () => {
  it('has the page title and the four sections in order', () => {
    renderWithProviders(<AboutPage />, { route: '/about' });
    expect(screen.getByRole('heading', { level: 1, name: 'About' })).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
      'What is Sunday Clays?',
      'Who built this?',
      'For the technically curious',
      'Your privacy',
    ]);
  });

  it('opens each external link in a new tab with the exact address', () => {
    renderWithProviders(<AboutPage />, { route: '/about' });
    const expected: [RegExp, string][] = [
      [/Read more on tcgc\.org/, 'https://tcgc.org/sunday-clays/'],
      [/gitgat\.com/, 'https://gitgat.com'],
      [/github\.com\/gitgat\/sunday-clays/, 'https://github.com/gitgat/sunday-clays'],
    ];
    for (const [name, href] of expected) {
      const link = external(name);
      expect(link).toHaveAttribute('href', href);
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
      expect(link).toHaveTextContent('(opens in a new tab)');
    }
  });

  it('links to the builder’s profile', () => {
    renderWithProviders(<AboutPage />, { route: '/about' });
    expect(screen.getByRole('link', { name: 'See my scores' })).toHaveAttribute(
      'href',
      '/shooters/187',
    );
  });

  it('names the builder and ClaySmasher', () => {
    renderWithProviders(<AboutPage />, { route: '/about' });
    expect(screen.getByText(/Bryan Moran, one of the Sunday regulars/)).toBeInTheDocument();
    expect(screen.getByText(/ClaySmasher/)).toBeInTheDocument();
  });

  it('lists five privacy points', () => {
    renderWithProviders(<AboutPage />, { route: '/about' });
    const section = screen.getByRole('heading', { name: 'Your privacy' }).closest('section');
    if (section === null) throw new Error('expected a privacy section');
    expect(within(section).getAllByRole('listitem')).toHaveLength(5);
  });

  it('never uses he, she, his or her', () => {
    const { container } = renderWithProviders(<AboutPage />, { route: '/about' });
    expect(container.textContent).not.toMatch(/\b(he|she|his|her)\b/i);
  });
});
