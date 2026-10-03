import { useSyncExternalStore } from 'react';

/** Chromium's install event (not in lib.dom). */
export interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export const DISMISSED_KEY = 'sc.install.dismissed';

let deferred: BeforeInstallPromptEvent | null = null;
const listeners = new Set<() => void>();
const notify = () => {
  for (const listener of listeners) listener();
};

// Attached at import (AppShell imports this module), so an early event is never missed.
window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault();
  deferred = event as BeforeInstallPromptEvent;
  notify();
});
window.addEventListener('appinstalled', () => {
  deferred = null;
  dismissInstall();
});

export function isInstallDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED_KEY) === '1';
  } catch {
    return false;
  }
}

export function dismissInstall(): void {
  try {
    localStorage.setItem(DISMISSED_KEY, '1');
  } catch {
    // storage blocked: the tip may show again on the next load
  }
  notify();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useInstallPrompt(): BeforeInstallPromptEvent | null {
  return useSyncExternalStore(subscribe, () => deferred);
}

export function useInstallDismissed(): boolean {
  return useSyncExternalStore(subscribe, isInstallDismissed);
}

export async function promptInstall(): Promise<'accepted' | 'dismissed' | 'unavailable'> {
  const event = deferred;
  if (event === null) return 'unavailable';
  await event.prompt();
  const { outcome } = await event.userChoice;
  deferred = null;
  dismissInstall(); // Install (either answer) never shows the tip again
  return outcome;
}

/** iPhone, iPad or iPod Safari (not Chrome or Firefox on iOS, which cannot add to home). */
export function isIosSafari(ua: string = navigator.userAgent): boolean {
  return /iP(hone|ad|od)/.test(ua) && /Safari/.test(ua) && !/CriOS|FxiOS/.test(ua);
}

export function resetInstallPromptForTests(): void {
  deferred = null;
}
