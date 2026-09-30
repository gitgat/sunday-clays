import { Component, lazy, Suspense, useState } from 'react';
import type { ComponentType, ReactNode } from 'react';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';

/** Contains a failed chart chunk (a tab left open across a deploy) to its own card, with a retry. */
class ChartBoundary extends Component<
  { title: string; onRetry: () => void; children: ReactNode },
  { failed: boolean }
> {
  override state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  override render() {
    if (!this.state.failed) return this.props.children;
    return (
      <Card title={this.props.title}>
        <EmptyState
          title={`Couldn't load ${this.props.title.toLowerCase()}`}
          description="The chart code did not load."
          action={
            <button
              type="button"
              className="min-h-11 rounded-card px-3 text-accent underline"
              onClick={() => {
                this.props.onRetry();
                this.setState({ failed: false });
              }}
            >
              Retry
            </button>
          }
        />
      </Card>
    );
  }
}

/**
 * One lazily loaded chart. `title` names its loading card (as ChartSlot's does); `load` resolves the
 * component, and Retry after a failure loads it afresh (React caches a rejected lazy for good).
 */
export function LazyChart({
  title,
  load,
}: {
  title: string;
  load: () => Promise<{ default: ComponentType }>;
}) {
  const [Chart, setChart] = useState(() => lazy(load));
  return (
    <ChartBoundary title={title} onRetry={() => setChart(() => lazy(load))}>
      <Suspense
        fallback={
          <Card title={title}>
            <Skeleton className="h-64" />
          </Card>
        }
      >
        <Chart />
      </Suspense>
    </ChartBoundary>
  );
}
