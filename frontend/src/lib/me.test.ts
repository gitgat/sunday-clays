import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearMe, getMe, isMeSkipped, setMe, skipMe } from './me';

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('me', () => {
  it('remembers, reads and clears the chosen shooter id', () => {
    expect(getMe()).toBeNull();
    setMe(42);
    expect(getMe()).toBe(42);
    clearMe();
    expect(getMe()).toBeNull();
  });

  it('ignores a corrupted stored value', () => {
    localStorage.setItem('sc.me', 'abc');
    expect(getMe()).toBeNull();
    localStorage.setItem('sc.me', '-3');
    expect(getMe()).toBeNull();
  });

  it('never throws when storage is unavailable', () => {
    const boom = () => {
      throw new DOMException('denied', 'SecurityError');
    };
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(boom);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(boom);
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(boom);
    expect(getMe()).toBeNull();
    expect(() => setMe(1)).not.toThrow();
    expect(() => clearMe()).not.toThrow();
    expect(isMeSkipped()).toBe(false);
    expect(() => skipMe()).not.toThrow();
  });

  it('remembers a skip until someone is picked; "Not me" does not skip', () => {
    expect(isMeSkipped()).toBe(false);
    skipMe();
    expect(isMeSkipped()).toBe(true);
    setMe(42);
    expect(isMeSkipped()).toBe(false);
    clearMe();
    expect(isMeSkipped()).toBe(false);
    expect(getMe()).toBeNull();
  });
});
