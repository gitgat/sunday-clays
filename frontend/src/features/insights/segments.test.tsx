import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../test/render';
import { Segments } from './segments';

describe('Segments', () => {
  it('grows a name link hit box without changing the line box', () => {
    renderWithProviders(
      <p>
        <Segments segments={[{ t: 'shooter', v: 'Bo Li', id: 3 }]} />
      </p>,
    );
    const link = screen.getByRole('link', { name: 'Bo Li' });
    expect(link).toHaveClass('py-3.5', '-my-3.5', 'px-2', '-mx-2');
    expect(link).not.toHaveClass('inline-flex');
    expect(link).not.toHaveClass('min-h-11');
  });
});
