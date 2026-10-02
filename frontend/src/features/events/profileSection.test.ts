import { describe, expect, it } from 'vitest';
import { profileSections } from '../shooters/sections';
import { SpecialShootsCard } from './components/SpecialShootsCard';

describe('the special shoots profile section', () => {
  it('is registered after the weather card and renders its own card', () => {
    expect(profileSections.find((s) => s.id === 'special')).toMatchObject({
      title: 'Special shoots',
      order: 65,
      bare: true,
      Component: SpecialShootsCard,
    });
  });
});
