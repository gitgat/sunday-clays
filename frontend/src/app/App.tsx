// From 'react-router', like every hook the pages use: under Node (vitest), 'react-router/dom'
// require()s a second React Router copy whose contexts page hooks cannot see.
import { RouterProvider } from 'react-router';
import { setNavigate } from '../api/client';
import { onSessionExpired } from '../features/auth/api';
import { LinkLoginGate } from '../features/auth/components/LinkLoginGate';
import { resolveLinkLogin } from '../features/auth/linkLogin';
import { AppProviders } from './providers';
import { createQueryClient } from './queryClient';
import { createAppRouter } from './router';

const router = createAppRouter();
const queryClient = createQueryClient();
// A password link (?p= already stripped by main.tsx) is tried before any protected page renders.
const linkLoginReady = resolveLinkLogin(queryClient);

// A data request's 401 clears the cached session, then navigates in-app (no reload, no loop).
setNavigate(
  onSessionExpired(queryClient, (to) => {
    void router.navigate(to);
  }),
);

export function App() {
  return (
    <AppProviders queryClient={queryClient}>
      <LinkLoginGate ready={linkLoginReady}>
        <RouterProvider router={router} />
      </LinkLoginGate>
    </AppProviders>
  );
}
