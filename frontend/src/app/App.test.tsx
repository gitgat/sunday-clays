import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App } from './App';

describe('App', () => {
  it('renders the routed home page', async () => {
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Sunday Clays' })).toBeInTheDocument();
  });
});
