import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { LAZY_CHART } from '../test/lazyChart';
import { App } from './App';

describe('App', () => {
  it('renders the Sunday Sheet at /', async () => {
    render(<App />);

    expect(
      await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' }, LAZY_CHART),
    ).toBeInTheDocument();
  });
});
