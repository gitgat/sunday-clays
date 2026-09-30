import { useState } from 'react';
import { Button } from '../../../components/ui/Button';

/** How many rows a list shows before "Show all N". */
export const SHOWN_ROWS = 10;

/**
 * The first SHOWN_ROWS of `items`, and whether a "Show all N" button should reveal the rest.
 */
export function useShowAll<T>(items: readonly T[]) {
  const [all, setAll] = useState(false);
  const hidden = items.length > SHOWN_ROWS && !all;
  return {
    visible: hidden ? items.slice(0, SHOWN_ROWS) : items,
    hidden,
    showAll: () => {
      setAll(true);
    },
  };
}

export function ShowAllButton({
  count,
  noun,
  latest = false,
  onClick,
}: {
  count: number;
  noun: string;
  /** The list is the server's newest `count`, not everything: say "the latest" instead of "all". */
  latest?: boolean;
  onClick: () => void;
}) {
  return (
    <Button variant="tonal" className="self-start" onClick={onClick}>
      {latest ? 'Show the latest' : 'Show all'} {count} {noun}
    </Button>
  );
}
