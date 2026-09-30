import type { UseQueryResult } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';

/** Loading / error / empty states for one chart; renders `children(data)` (a ChartFrame) once data is usable. */
export function QueryChart<T>({
  title,
  query,
  isEmpty,
  emptyText,
  controls,
  waiting = false,
  children,
}: {
  title: string;
  query: UseQueryResult<T>;
  isEmpty: (data: T) => boolean;
  emptyText: string;
  /** Kept above the loading, error and empty states so the viewer can still change them. */
  controls?: ReactNode;
  /** Keeps the loading state after the data is in: the time window is not resolved yet. */
  waiting?: boolean;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending || waiting) {
    return (
      <Card title={title}>
        {controls !== undefined && <div className="mb-3">{controls}</div>}
        <Skeleton className="h-64" />
      </Card>
    );
  }
  if (query.isError) {
    return (
      <Card title={title}>
        {controls !== undefined && <div className="mb-3">{controls}</div>}
        <EmptyState
          title={`Couldn't load ${title.toLowerCase()}`}
          description={query.error.message}
        />
      </Card>
    );
  }
  if (isEmpty(query.data)) {
    return (
      <Card title={title}>
        {controls !== undefined && <div className="mb-3">{controls}</div>}
        <EmptyState title={emptyText} />
      </Card>
    );
  }
  return <>{children(query.data)}</>;
}
