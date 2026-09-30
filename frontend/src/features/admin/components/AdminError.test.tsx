import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { AdminError, adminErrorMessage } from './AdminError';

describe('AdminError', () => {
  it('shows the error message as an alert', () => {
    renderWithProviders(<AdminError error={new Error('Import 12 is not pending')} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Import 12 is not pending');
    expect(adminErrorMessage(new Error('boom'))).toBe('boom');
  });
});
