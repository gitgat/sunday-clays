import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { HomePage } from '../home/pages/HomePage';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { homeWidget } from './homeWidget';
import { resetTourForTests, TOUR_KEY } from './state';

const tourOn = () =>
  server.use(
    http.get('*/api/features', () => HttpResponse.json({ switches: { tour_glossary: true } })),
  );

beforeEach(() => tourOn());
afterEach(() => resetTourForTests());

describe('tour home widget', () => {
  it('declares a hero widget before every other', () => {
    expect(homeWidget).toMatchObject({ id: 'tour', order: -10, slot: 'hero' });
  });

  it('opens on a first visit, and Done stores it and returns focus to the Home title', async () => {
    const { user } = renderWithProviders(<HomePage widgets={[homeWidget]} />);
    const dialog = await screen.findByRole(
      'dialog',
      { name: 'The latest Sunday' },
      { timeout: 3000 },
    );
    expect(dialog).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Skip tour' }));
    expect(localStorage.getItem(TOUR_KEY)).toBe('done');
    expect(screen.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toHaveFocus();
    expect(screen.getByRole('heading', { level: 1 })).toHaveAttribute('tabindex', '-1');
  });

  it('stays closed once done, and adds no node to the hero slot', async () => {
    localStorage.setItem(TOUR_KEY, 'done');
    const { container } = renderWithProviders(<HomePage widgets={[homeWidget]} />);
    const bare = renderWithProviders(<HomePage widgets={[]} />);
    await new Promise((resolve) => setTimeout(resolve, 1700));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    // WidgetSlot adds no wrapper, so a closed tour widget leaves the page column unchanged.
    const column = (root: HTMLElement) => root.querySelector('h1')?.parentElement?.children.length;
    expect(column(container)).toBe(column(bare.container));
  });

  it('?tour=1 reopens it and removes only the tour parameter', async () => {
    localStorage.setItem(TOUR_KEY, 'done');
    const { router } = renderWithProviders(<HomePage widgets={[homeWidget]} />, {
      route: '/?w=3m&tour=1',
    });
    expect(await screen.findByRole('dialog', {}, { timeout: 3000 })).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.search).toBe('?w=3m'));
  });

  it('never opens while the feature is off for a viewer', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));
    renderWithProviders(<HomePage widgets={[homeWidget]} />);
    await new Promise((resolve) => setTimeout(resolve, 1700));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('opens at once when the latest-Sunday card is already there', async () => {
    const marker = document.createElement('div');
    marker.dataset.tour = 'sunday';
    document.body.appendChild(marker);
    try {
      renderWithProviders(<HomePage widgets={[homeWidget]} />);
      expect(await screen.findByRole('dialog', {}, { timeout: 500 })).toBeInTheDocument();
    } finally {
      marker.remove();
    }
  });

  it('opens for an admin while the feature is off, with the Admin preview badge', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));
    renderWithProviders(<HomePage widgets={[homeWidget]} />, { role: 'admin' });
    const dialog = await screen.findByRole('dialog', {}, { timeout: 3000 });
    expect(within(dialog).getByText('Admin preview')).toBeInTheDocument();
  });

  it('opens after the wait even when the latest-Sunday card never appears', async () => {
    const Widget = homeWidget.Component;
    renderWithProviders(<Widget meId={null} />);
    expect(await screen.findByRole('dialog', {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it('returns focus to the Home title only once the page is no longer inert', async () => {
    const { user } = renderWithProviders(<HomePage widgets={[homeWidget]} />);
    await screen.findByRole('dialog', {}, { timeout: 3000 });
    const title = screen.getByRole('heading', { level: 1, name: 'Sunday Clays' });
    let inertWhenFocused: boolean | null = null;
    const original = title.focus.bind(title);
    title.focus = () => {
      inertWhenFocused = title.closest('[inert]') !== null;
      original();
    };
    await user.click(screen.getByRole('button', { name: 'Skip tour' }));
    expect(inertWhenFocused).toBe(false);
  });
});
