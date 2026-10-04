import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { CONTACTS_KEY, rosterKey, useAdminRoster, useContacts } from './api';

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, wrapper };
}

describe('admin club-events audited reads', () => {
  it('useAdminRoster is never stale and never refetched on focus', async () => {
    const { client, wrapper } = setup();
    const { result } = renderHook(() => useAdminRoster(1), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.getQueryCache().find({ queryKey: rosterKey(1) })?.options).toMatchObject({
      staleTime: Infinity,
      refetchOnWindowFocus: false,
    });
  });

  it('useContacts is never stale and never refetched on focus', async () => {
    const { client, wrapper } = setup();
    const { result } = renderHook(() => useContacts(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.getQueryCache().find({ queryKey: CONTACTS_KEY })?.options).toMatchObject({
      staleTime: Infinity,
      refetchOnWindowFocus: false,
    });
  });
});
