import type { UseQueryResult } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';

/** Loading / error / empty states for one dashboard chart; `children(data)` renders the ChartFrame. */
export function ChartSlot<T>({
  title,
  query,
  isEmpty,
  emptyText,
  children,
}: {
  title: string;
  query: UseQueryResult<T>;
  isEmpty: (data: T) => boolean;
  emptyText: string;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) {
    return (
      <Card title={title}>
        <Skeleton className="h-64" />
      </Card>
    );
  }
  if (query.isError) {
    return (
      <Card title={title}>
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
        <EmptyState title={emptyText} />
      </Card>
    );
  }
  return <>{children(query.data)}</>;
}
