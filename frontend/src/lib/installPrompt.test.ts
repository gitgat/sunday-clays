import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  dismissInstall,
  DISMISSED_KEY,
  isInstallDismissed,
  isIosSafari,
  promptInstall,
  resetInstallPromptForTests,
} from './installPrompt';

afterEach(() => resetInstallPromptForTests());

function installEvent(outcome: 'accepted' | 'dismissed') {
  const event = new Event('beforeinstallprompt', { cancelable: true });
  return Object.assign(event, {
    prompt: vi.fn().mockResolvedValue(undefined),
    userChoice: Promise.resolve({ outcome }),
  });
}

describe('install prompt', () => {
  it('captures the event, prevents the mini-infobar, and prompts on demand', async () => {
    const event = installEvent('accepted');
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    await expect(promptInstall()).resolves.toBe('accepted');
    expect(event.prompt).toHaveBeenCalled();
    expect(isInstallDismissed()).toBe(true); // an install also dismisses the tip
  });

  it('is unavailable with no captured event', async () => {
    await expect(promptInstall()).resolves.toBe('unavailable');
  });

  it('forgets the install event and dismisses the tip once the app is installed', () => {
    window.dispatchEvent(installEvent('accepted'));
    window.dispatchEvent(new Event('appinstalled'));
    expect(isInstallDismissed()).toBe(true);
    return expect(promptInstall()).resolves.toBe('unavailable');
  });

  it('survives blocked storage', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(isInstallDismissed()).toBe(false);
    expect(() => dismissInstall()).not.toThrow();
    vi.restoreAllMocks();
  });

  it('remembers a dismissal', () => {
    dismissInstall();
    expect(localStorage.getItem(DISMISSED_KEY)).toBe('1');
    expect(isInstallDismissed()).toBe(true);
  });

  it.each([
    [
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
      true,
    ],
    [
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/129.0 Mobile/15E148 Safari/604.1',
      false,
    ],
    [
      'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/129.0 Mobile/15E148 Safari/605.1.15',
      false,
    ],
    [
      'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36',
      false,
    ],
  ])('isIosSafari(%s) is %s', (ua, expected) => {
    expect(isIosSafari(ua)).toBe(expected);
  });
});
