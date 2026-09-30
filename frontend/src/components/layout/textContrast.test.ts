import { describe, expect, it } from 'vitest';
import { contrast, TOKEN_BY_CLASS_NAME } from '../../test/contrast';
import { colors } from '../../theme/tokens';

/** Source text of every layout component (not its tests). */
const layoutSources = import.meta.glob<string>(['./*.tsx', '!./*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

// The layout's counterpart of theme.test.ts's UI kit guard. Shell text is small (12-14px), so every
// `text-<token>` needs 4.5:1 on the side nav/tab bar (elevated) and on the page (surface). Icons
// are 3:1 graphics: an icon that needs a token the text cannot use takes it as `stroke-<token>`.
describe('layout text colors', () => {
  it('every token the shell uses as a text color keeps 4.5:1 on elevated and on surface', () => {
    const used = new Map<string, string[]>();
    for (const [file, source] of Object.entries(layoutSources)) {
      for (const match of source.matchAll(/(?<![\w-])text-([a-z]+(?:-[a-z]+)*)/g)) {
        const name = match[1] ?? '';
        if (TOKEN_BY_CLASS_NAME.has(name)) used.set(name, [...(used.get(name) ?? []), file]);
      }
    }
    expect(Object.keys(layoutSources).length).toBeGreaterThanOrEqual(6);
    expect([...used.keys()]).toEqual(expect.arrayContaining(['text', 'text-muted']));
    for (const [name, files] of used) {
      const hex = TOKEN_BY_CLASS_NAME.get(name) ?? '';
      const where = `text-${name} in ${[...new Set(files)].join(', ')}`;
      expect(contrast(hex, colors.elevated), `${where} on elevated`).toBeGreaterThanOrEqual(4.5);
      expect(contrast(hex, colors.surface), `${where} on surface`).toBeGreaterThanOrEqual(4.5);
    }
  });
});
