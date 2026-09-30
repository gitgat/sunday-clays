import { describe, expect, it } from 'vitest';
import { explainers } from './explainers';

describe('prediction explainers', () => {
  const copy = JSON.stringify(explainers);

  it('has the three parts', () => {
    const entry = explainers['next-sunday'];
    expect(entry.what.length).toBeGreaterThan(0);
    expect(entry.read.length).toBeGreaterThan(0);
    expect(entry.computed.length).toBeGreaterThan(0);
  });

  it('reads correctly on anyone’s profile, not only the viewer’s', () => {
    expect(copy).not.toMatch(/\b(you|your|yours)\b/i);
  });

  it('uses neutral pronouns and no odds wording', () => {
    expect(copy).not.toMatch(/\b(he|she|his|her|hers|him)\b/i);
    expect(copy).not.toMatch(/odds|chance to win|podium|\bclass\b/i);
  });
});
