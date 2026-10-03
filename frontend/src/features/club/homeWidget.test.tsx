import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { homeWidget } from './homeWidget';
import { clubMilestones } from './mocks';

const { Component } = homeWidget;

describe('club milestone home card', () => {
  it('is a main widget at order 20', () => {
    expect(homeWidget).toMatchObject({ id: 'club-milestone', order: 20, slot: 'main' });
  });

  it('shows the latest milestone, its Sunday, the next one and a link to the Club page', async () => {
    renderWithProviders(<Component meId={null} />);
    expect(await screen.findByRole('heading', { name: 'Club milestone' })).toBeInTheDocument();
    expect(screen.getByText('350,000 clays thrown')).toBeInTheDocument();
    expect(screen.getByText('Passed on Sunday, Sep 13, 2026')).toBeInTheDocument();
    expect(screen.getByText('Next up: 400,000 clays thrown, 41,250 to go')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'All club milestones' })).toHaveAttribute(
      'href',
      '/club#milestones',
    );
    expect(screen.getByRole('button', { name: 'About club milestones' })).toBeInTheDocument();
  });

  it('renders nothing and asks nothing while off for a viewer', async () => {
    let asked = 0;
    server.use(
      http.get('*/api/features', () => HttpResponse.json({ switches: {} })),
      http.get('*/api/club/milestones', () => {
        asked += 1;
        return HttpResponse.json(clubMilestones);
      }),
    );
    const { container } = renderWithProviders(<Component meId={null} />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
    expect(asked).toBe(0);
  });

  it('is hidden when there is no milestone yet', async () => {
    server.use(
      http.get('*/api/club/milestones', () =>
        HttpResponse.json({ ...clubMilestones, milestones: [], latest: null }),
      ),
    );
    const { container } = renderWithProviders(<Component meId={null} />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });
});
