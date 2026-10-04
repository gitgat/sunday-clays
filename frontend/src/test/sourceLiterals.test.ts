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
});
