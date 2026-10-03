import { Component, type ErrorInfo, type ReactNode } from 'react';
import { isRouteErrorResponse, useRouteError } from 'react-router';

function Fallback({ title, message }: { title: string; message: string }) {
  return (
    <div
      role="alert"
      className="mx-auto flex max-w-md flex-col items-center gap-3 px-4 py-16 text-center"
    >
      <h1 className="text-lg font-medium text-text">{title}</h1>
      <p className="text-sm text-text-muted">{message}</p>
      <a
        href="/"
        className="inline-flex min-h-11 items-center rounded-button bg-primary px-4 text-sm text-text"
      >
        Go to home
      </a>
    </div>
  );
}

interface BoundaryState {
  error: Error | null;
}

/** Last-resort boundary around the whole app (render errors outside any route). */
export class AppErrorBoundary extends Component<{ children: ReactNode }, BoundaryState> {
  override state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(error, info.componentStack);
  }

  override render(): ReactNode {
    if (this.state.error) {
      return <Fallback title="Something went wrong" message="Reload the page to try again." />;
    }
    return this.props.children;
  }
}

/** "Page not found": unknown paths, and gated pages while their launch switch is off (D21). */
export function NotFoundView() {
  return <Fallback title="Page not found" message="That page does not exist." />;
}

/** errorElement for the root route: 404 for unknown paths, a generic message otherwise. */
export function RouteErrorPage() {
  const error = useRouteError();
  if (isRouteErrorResponse(error) && error.status === 404) {
    return <NotFoundView />;
  }
  return (
    <Fallback
      title="Something went wrong"
      message="This page hit an error. Reloading usually fixes it."
    />
  );
}
