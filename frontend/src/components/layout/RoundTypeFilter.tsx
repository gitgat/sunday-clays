import { Filter } from 'lucide-react';
import { useEffect, useId, useRef, useState } from 'react';
import {
  ROUND_TYPE_LABELS,
  ROUND_TYPES,
  useRoundTypes,
  type RoundTypeValue,
} from '../../lib/roundTypes';
import { Chip } from '../ui/Chip';
import { cx } from '../ui/cx';

/**
 * The global round-type filter (C10): a checkbox popover bound to `?rt=` plus a 'Filtered' chip.
 * `align` picks the edge the panel hangs from; the mobile TopBar puts the filter at the right
 * edge of a 390px screen, so it opens its panel leftwards ('right').
 */
export function RoundTypeFilter({ align = 'left' }: { align?: 'left' | 'right' }) {
  const [selected, setSelected] = useRoundTypes();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (event.target instanceof Node && !rootRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  const toggle = (value: RoundTypeValue) => {
    const next = ROUND_TYPES.filter((t) =>
      t === value ? !selected.includes(t) : selected.includes(t),
    );
    // All three selected filters nothing out, so store it as "no filter".
    setSelected(next.length === ROUND_TYPES.length ? [] : next);
  };

  return (
    <div
      ref={rootRef}
      onBlur={(event) => {
        // Focus moving to an element outside (Tab, Shift+Tab) closes the panel. Focus that only
        // drops to the page (a click on the panel's padding) has no target and is left to the
        // pointerdown handler.
        const next = event.relatedTarget;
        if (next instanceof Node && !event.currentTarget.contains(next)) setOpen(false);
      }}
      className="relative flex flex-wrap items-center gap-2"
    >
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') setOpen(false);
        }}
        className="inline-flex min-h-11 items-center gap-2 rounded-button border border-outline-variant px-3 text-sm text-text-muted hover:text-text"
      >
        <Filter aria-hidden="true" className="size-4" />
        Round type
      </button>
      {open && (
        <div
          id={panelId}
          role="group"
          aria-label="Round types"
          onKeyDown={(event) => {
            if (event.key !== 'Escape') return;
            setOpen(false);
            // The focused checkbox unmounts with the panel; hand focus back to the trigger.
            triggerRef.current?.focus();
          }}
          className={cx(
            'absolute top-full z-40 mt-1 flex w-56 flex-col rounded-card border border-outline-variant bg-elevated p-2 shadow-xl',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {ROUND_TYPES.map((value) => (
            <label key={value} className="flex min-h-11 items-center gap-3 px-2 text-sm text-text">
              <input
                type="checkbox"
                checked={selected.includes(value)}
                onChange={() => toggle(value)}
                className="size-4 accent-accent"
              />
              {ROUND_TYPE_LABELS[value]}
            </label>
          ))}
        </div>
      )}
      {selected.length > 0 && (
        <Chip
          selected
          onRemove={() => {
            setSelected([]);
            // The clear button unmounts with the chip; hand focus back to the trigger.
            triggerRef.current?.focus();
          }}
          removeLabel="Clear round type filter"
        >
          Filtered: {selected.map((t) => ROUND_TYPE_LABELS[t]).join(' + ')}
        </Chip>
      )}
    </div>
  );
}
