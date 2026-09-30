import type { ReactNode } from 'react';

export interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}

export function EmptyState({ title, description, action, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
      {icon !== undefined && <div className="text-text-muted">{icon}</div>}
      <h3 className="text-base font-medium text-text">{title}</h3>
      {description !== undefined && (
        <p className="max-w-prose text-sm text-text-muted">{description}</p>
      )}
      {action !== undefined && <div className="mt-2">{action}</div>}
    </div>
  );
}
