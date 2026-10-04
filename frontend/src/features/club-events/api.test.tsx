import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { useSignupCheck } from './api';

describe('club-events queries', () => {
  it('useSignupCheck is never stale and never refetched on focus (D11)', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useSignupCheck(1, 3), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const query = client
      .getQueryCache()
      .find({ queryKey: ['/api/club-events', 1, 'signup-check', 3] });
    expect(query?.options).toMatchObject({ staleTime: Infinity, refetchOnWindowFocus: false });
  });

  it('useSignupCheck does not run while disabled (sheet closed)', async () => {
    let calls = 0;
    server.use(
      http.get('*/api/club-events/:id/signup-check', () => {
        calls += 1;
        return HttpResponse.json({ has_email: false, already_signed_up: false });
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useSignupCheck(1, 3, false), { wrapper });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(result.current.fetchStatus).toBe('idle');
    expect(calls).toBe(0);
  });
});
