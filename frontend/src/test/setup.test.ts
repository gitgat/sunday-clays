import { describe, expect, it, vi } from 'vitest';

describe('jsdom shims from test/setup.ts', () => {
  it('provides the browser APIs charts, layout and sharing rely on', () => {
    expect(window.matchMedia('(min-width: 1024px)').matches).toBe(false);
    expect(() => new ResizeObserver(() => undefined).observe(document.body)).not.toThrow();
    expect(() => new IntersectionObserver(() => undefined).observe(document.body)).not.toThrow();
    expect(URL.createObjectURL(new Blob(['x']))).toBe('blob:mock-object-url');
    expect(navigator.canShare()).toBe(false);
    expect(document.createElement('canvas').getContext('2d')).not.toBeNull();
    expect(() => window.scrollTo(0, 0)).not.toThrow();
  });

  it('fails any request no MSW handler matches', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    await expect(fetch('http://localhost/api/unmocked')).rejects.toThrow();
    expect(error).toHaveBeenCalledWith(
      expect.stringContaining('without a matching request handler'),
    );
  });

  it('resolves relative /api URLs against the page origin, so only MSW rejects them', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    expect(new Request('/api/unmocked').url).toBe(`${window.location.origin}/api/unmocked`);
    await expect(fetch('/api/unmocked')).rejects.toThrow();
    expect(error).toHaveBeenCalledWith(
      expect.stringContaining('without a matching request handler'),
    );
  });
});
