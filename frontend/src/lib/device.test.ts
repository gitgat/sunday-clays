import { afterEach, describe, expect, it, vi } from 'vitest';
import { getDeviceId, newUuid } from './device';

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe('newUuid', () => {
  it('uses crypto.randomUUID where the browser has it', () => {
    vi.spyOn(crypto, 'randomUUID').mockReturnValue('11111111-2222-4333-8444-555555555555');
    expect(newUuid()).toBe('11111111-2222-4333-8444-555555555555');
  });

  it('builds a version-4 UUID from getRandomValues on an insecure (plain http) page', () => {
    vi.stubGlobal('crypto', {
      getRandomValues: (bytes: Uint8Array) => bytes.fill(0xff),
    });
    expect(newUuid()).toBe('ffffffff-ffff-4fff-bfff-ffffffffffff');
    expect(newUuid()).toMatch(UUID_V4);
  });
});

describe('getDeviceId', () => {
  it('creates a UUID once and keeps it', () => {
    const id = getDeviceId();
    expect(id).toMatch(UUID_V4);
    expect(getDeviceId()).toBe(id);
    expect(localStorage.getItem('sc.device')).toBe(id);
  });

  it('replaces a stored value that is not a UUID instead of sending it', () => {
    localStorage.setItem('sc.device', 'hello');
    const id = getDeviceId();
    expect(id).toMatch(UUID_V4);
    expect(localStorage.getItem('sc.device')).toBe(id);
  });

  it('is null when storage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    expect(getDeviceId()).toBeNull();
  });

  it('is null when storage does not keep what is written', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => undefined);
    expect(getDeviceId()).toBeNull();
  });
});
