import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { ApiError } from '../../../api/errors';
import { Button } from '../../../components/ui/Button';
import { safeNext } from '../../../lib/safeNext';
import { useLogin, useSession } from '../api';

function errorMessage(error: unknown): string | null {
  if (error === null) return null;
  if (error instanceof ApiError && error.status === 401) return 'Wrong password.';
  // Both 429s (Plan 04 T1): every argon2 verify slot busy, or the per-IP failure limit.
  if (error instanceof ApiError && error.code === 'login_busy') {
    return 'The server is busy. Try again in a moment.';
  }
  if (error instanceof ApiError && error.status === 429) {
    return 'Too many attempts. Try again in a few minutes.';
  }
  return 'Could not log in. Check your connection and try again.';
}

export function LoginPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { session } = useSession();
  const login = useLogin();
  const [password, setPassword] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const errorId = useId();
  const next = params.get('next');

  // Signed in (already, or just now): leave through safeNext only (C10). A data router's
  // navigate() returns a promise; a refused navigation must not become an unhandled rejection.
  useEffect(() => {
    if (!session) return;
    Promise.resolve(navigate(safeNext(next), { replace: true })).catch(() => undefined);
  }, [session, next, navigate]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    // The click left focus on the button: hand it back to the field the error describes.
    login.mutate(password, { onError: () => inputRef.current?.focus() });
  };
  const message = errorMessage(login.error);

  return (
    <main className="flex min-h-dvh items-center justify-center p-4">
      <form
        onSubmit={onSubmit}
        className="flex w-full max-w-sm flex-col gap-4 rounded-card bg-elevated p-6 shadow-xl"
      >
        <h1 className="text-2xl font-bold text-text">Sunday Clays</h1>
        <p className="text-sm text-text-muted">Enter the club password to continue.</p>
        <div className="flex flex-col gap-1">
          <label htmlFor={inputId} className="text-sm text-text">
            Password
          </label>
          <input
            ref={inputRef}
            id={inputId}
            type="password"
            autoComplete="current-password"
            // The page's only task: the password field takes focus when the page opens.
            autoFocus
            required
            aria-invalid={message !== null || undefined}
            aria-describedby={message !== null ? errorId : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="min-h-11 rounded-button border border-outline-variant bg-surface px-4 text-text"
          />
        </div>
        {message !== null && (
          <p
            id={errorId}
            role="alert"
            className="rounded-card bg-error-container px-3 py-2 text-sm text-text"
          >
            {message}
          </p>
        )}
        <Button type="submit" loading={login.isPending} disabled={password === ''}>
          Log in
        </Button>
      </form>
    </main>
  );
}
