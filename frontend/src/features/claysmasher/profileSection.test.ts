import { describe, expect, it } from 'vitest';
import { profileSections } from '../shooters/sections';
import { ImportIntoClaySmasher } from './components/ImportIntoClaySmasher';

describe('ClaySmasher profile section', () => {
  it('sits at the top of the shooter page and renders its own (or no) element', () => {
    expect(profileSections.find((s) => s.id === 'claysmasher')).toMatchObject({
      placement: 'top',
      bare: true,
      order: 5,
      Component: ImportIntoClaySmasher,
    });
  });
});
