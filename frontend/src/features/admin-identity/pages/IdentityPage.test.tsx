import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { duplicatePairs, rules } from '../mocks';
import { IdentityPage } from './IdentityPage';

describe('IdentityPage', () => {
  it('shows the duplicates queue, the shooter forms, the rules and the rule form', async () => {
    server.use(
      http.get('*/api/admin/possible-duplicates', () => HttpResponse.json(duplicatePairs)),
      http.get('*/api/admin/rules', () => HttpResponse.json(rules)),
    );
    renderWithProviders(<IdentityPage />, { route: '/admin/identity' });
    expect(screen.getByRole('heading', { level: 1, name: 'Identity & rules' })).toBeInTheDocument();
    expect(await screen.findByRole('list', { name: 'Possible duplicates' })).toBeInTheDocument();
    expect(await screen.findByRole('table', { name: 'Rules' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Rename' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Set status' })).toBeInTheDocument();
    expect(screen.getByLabelText('Rule type')).toBeInTheDocument();
  });

  it('a viewer session sees the admins-only message', async () => {
    const forbidden = () =>
      HttpResponse.json({ error: { code: 'forbidden', message: 'Forbidden' } }, { status: 403 });
    server.use(
      http.get('*/api/admin/possible-duplicates', forbidden),
      http.get('*/api/admin/rules', forbidden),
    );
    renderWithProviders(<IdentityPage />, { route: '/admin/identity' });
    // Two independent queries fail; wait until both messages are shown.
    await waitFor(() =>
      expect(screen.getAllByText('Admins only — sign in with the admin password.')).toHaveLength(2),
    );
  });
});
