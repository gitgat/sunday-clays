import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { ADMIN_PREVIEW_HINT, AdminPreviewBadge } from './AdminPreviewBadge';

const off = () => server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));

describe('AdminPreviewBadge', () => {
  it('renders for an admin while the switch is off', async () => {
    off();
    renderWithProviders(<AdminPreviewBadge feature="summary_card" />, { role: 'admin' });
    const badge = await screen.findByText('Admin preview');
    const hint = screen.getByText(ADMIN_PREVIEW_HINT);
    expect(hint).toHaveClass('sr-only');
    expect(badge).toContainElement(hint);
  });

  it('renders nothing once the switch is on', async () => {
    const { container } = renderWithProviders(<AdminPreviewBadge feature="summary_card" />, {
      role: 'admin',
    });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for a viewer', async () => {
    off();
    const { container } = renderWithProviders(<AdminPreviewBadge feature="summary_card" />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });
});
