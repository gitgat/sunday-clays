import { describe, expect, it } from 'vitest';
import { profileSections } from '../shooters/sections';
import { ExportScores } from './components/ExportScores';

describe('ClaySmasher export profile section', () => {
  it('sits at the top of the shooter page and renders its own element', () => {
    expect(profileSections.find((s) => s.id === 'claysmasher-export')).toMatchObject({
      title: 'Export my scores',
      placement: 'top',
      bare: true,
      order: 5,
      Component: ExportScores,
    });
  });

  it('is the only ClaySmasher section (the old import link is gone)', () => {
    expect(profileSections.filter((s) => s.id.startsWith('claysmasher'))).toHaveLength(1);
  });
});
