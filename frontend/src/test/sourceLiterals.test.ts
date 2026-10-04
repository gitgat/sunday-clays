import { describe, expect, it } from 'vitest';
import { sourceLiterals } from './sourceLiterals';

describe('sourceLiterals (Plan 20 §5.8 lints)', () => {
  it('returns string, template and JSX text, never className values or import paths', () => {
    const source = [
      "import { x } from './class-names';",
      "const a = 'Top of the class';",
      'const b = `Hi ${x}, welcome`;',
      'const c = <p className="classy text-sm">Plain text</p>;',
    ].join('\n');
    expect(sourceLiterals('x.tsx', source)).toEqual([
      'Top of the class',
      'Hi ',
      ', welcome',
      'Plain text',
    ]);
  });

  it('drops empty template parts and reads nested templates', () => {
    const source =
      'const a = `${x}`; const b = `one ${`two ${y} three`} four`; const c = `${x}${y}`;';
    expect(sourceLiterals('x.ts', source)).toEqual(['one ', ' four', 'two ', ' three']);
  });

  it('skips className in every form but keeps other attributes', () => {
    const source = [
      "const a = <p className={cn('a', 'b')} aria-label=\"Top of the board\">Hi</p>;",
      "const b = { className: 'x', title: 'Shown' };",
    ].join('\n');
    expect(sourceLiterals('x.tsx', source)).toEqual(['Top of the board', 'Hi', 'Shown']);
  });

  it('skips dynamic import and vi.mock module paths', () => {
    const source = [
      "const m = import('./x');",
      "vi.mock('./y', () => ({ z: 'kept' }));",
      "const n = other('./w');",
    ].join('\n');
    expect(sourceLiterals('x.ts', source)).toEqual(['kept', './w']);
  });
});
