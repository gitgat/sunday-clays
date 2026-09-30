import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';
import { api, unwrap } from '../api/client';
import { server } from '../test/msw/server';
import { App } from './App';

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

describe('App session expiry', () => {
  it('routes a data 401 to the login page and forgets the cached session', async () => {
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Sunday Clays' })).toBeInTheDocument();
    server.use(
      http.get('/api/health', () =>
        HttpResponse.json({ error: { code: 'unauthenticated', message: 'x' } }, { status: 401 }),
      ),
    );
    await expect(unwrap(api.GET('/api/health'))).rejects.toMatchObject({ status: 401 });
    expect(await screen.findByLabelText('Password')).toBeInTheDocument();
    expect(window.location.pathname + window.location.search).toBe('/login?next=%2F');
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(window.location.pathname).toBe('/login');
  });
});
