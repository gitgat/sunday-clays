import { afterEach, describe, expect, it, vi } from 'vitest';
import { downloadBlob } from './download';

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('downloadBlob', () => {
  it('releases the object URL shortly after the download starts', () => {
    vi.useFakeTimers();
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    const revoke = vi.spyOn(URL, 'revokeObjectURL');
    downloadBlob(new Blob(['x']), 'x.txt');
    expect(revoke).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1_000);
    expect(revoke).toHaveBeenCalledWith('blob:mock-object-url');
  });
});
