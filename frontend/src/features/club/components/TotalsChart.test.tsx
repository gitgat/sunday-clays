import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { LAZY_CHART } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import TotalsChart from './TotalsChart';

describe('TotalsChart', () => {
  it('switches the plotted total with the chips, clays thrown first', async () => {
    renderWithProviders(<TotalsChart />, { route: '/club' });
    const clays = await screen.findByRole('button', { name: 'Clays thrown' }, LAZY_CHART);
    expect(clays).toHaveAttribute('aria-pressed', 'true');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Rounds' }));
    expect(screen.getByRole('button', { name: 'Rounds' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Clays thrown' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('draws nothing until the milestones arrive', async () => {
    server.use(http.get('*/api/club/milestones', () => new Promise(() => {})));
    const { container } = renderWithProviders(<TotalsChart />, { route: '/club' });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });
});
