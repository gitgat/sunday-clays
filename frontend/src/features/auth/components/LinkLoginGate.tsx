import { useEffect, useState, type ReactNode } from 'react';
import { Skeleton } from '../../../components/ui/Skeleton';

/** Holds the app back (normal loading state) until a password link has been tried. */
export function LinkLoginGate({
  ready,
  children,
}: {
  ready: Promise<void> | null;
  children: ReactNode;
}) {
  const [done, setDone] = useState(ready === null);
  useEffect(() => {
    if (ready === null) return;
    let live = true;
    void ready.then(() => {
      if (live) setDone(true);
    });
    return () => {
      live = false;
    };
  }, [ready]);
  if (!done) {
    return <Skeleton label="Checking your session" lines={4} className="mx-auto max-w-md p-8" />;
  }
  return children;
}
