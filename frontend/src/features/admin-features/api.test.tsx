import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { AppProviders } from '../../app/providers';
import { SESSION_QUERY_KEY } from '../auth/api';
import { createTestQueryClient } from '../../test/render';
import { useSetFeatureSwitch } from './api';

function wrapper() {
  const queryClient = createTestQueryClient();
  queryClient.setQueryData(SESSION_QUERY_KEY, { role: 'admin' });
  return ({ children }: { children: ReactNode }) => (
    <AppProviders queryClient={queryClient}>{children}</AppProviders>
  );
}

describe('useSetFeatureSwitch', () => {
  it('returns the updated switch with its change date', async () => {
    const { result } = renderHook(() => useSetFeatureSwitch(), { wrapper: wrapper() });
    result.current.mutate({ key: 'pwa', enabled: true });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toMatchObject({
      key: 'pwa',
      enabled: true,
      updated_on: '2026-10-02',
    });
  });

  it('fails for a switch that does not exist', async () => {
    const { result } = renderHook(() => useSetFeatureSwitch(), { wrapper: wrapper() });
    result.current.mutate({ key: 'nope', enabled: true });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
