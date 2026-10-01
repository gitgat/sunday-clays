import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { kudosFixture } from '../mocks';
import { KudosStrip, kudosLabel, naturalName } from './KudosStrip';

describe('KudosStrip', () => {
  it('is hidden when there are no kudos', () => {
    renderWithProviders(<KudosStrip kudos={[]} meId={null} />);
    expect(screen.queryByRole('region', { name: 'Kudos' })).toBeNull();
  });

  it('shows exactly 10 chips and no "more" chip for 10', () => {
    renderWithProviders(<KudosStrip kudos={kudosFixture(10)} meId={null} />);
    const strip = screen.getByRole('region', { name: 'Kudos' });
    expect(within(strip).getAllByRole('button', { name: / · / })).toHaveLength(10);
    expect(within(strip).queryByRole('button', { name: /more/ })).toBeNull();
  });

  it('caps 15 at 10 chips plus "and 5 more", which opens all 15', async () => {
    const { user } = renderWithProviders(<KudosStrip kudos={kudosFixture(15)} meId={null} />);
    const strip = screen.getByRole('region', { name: 'Kudos' });
    expect(within(strip).getAllByRole('button', { name: / · / })).toHaveLength(10);
    await user.click(within(strip).getByRole('button', { name: 'and 5 more' }));
    const sheet = screen.getByRole('dialog', { name: 'Kudos' });
    expect(within(sheet).getAllByRole('link', { name: /^Pat Shooter/ })).toHaveLength(15);
    expect(within(sheet).getAllByText(/New personal best for/)).toHaveLength(15);
    expect(within(sheet).getByRole('link', { name: 'Pat Shooter1' })).toHaveAttribute(
      'href',
      '/shooters/100',
    );
  });

  it('labels each chip with what it celebrates and opens that insight', async () => {
    const { user } = renderWithProviders(<KudosStrip kudos={kudosFixture(2)} meId={null} />);
    const strip = screen.getByRole('region', { name: 'Kudos' });
    await user.click(within(strip).getByRole('button', { name: 'Pat Shooter1 · personal best' }));
    const sheet = screen.getByRole('dialog', { name: 'Pat Shooter1' });
    expect(within(sheet).getByText(/New personal best for/)).toBeInTheDocument();
    expect(within(sheet).getByRole('link', { name: /^See the chart/ })).toBeInTheDocument();
  });

  it('shows the viewer their own kudos in the second person', async () => {
    const { user } = renderWithProviders(<KudosStrip kudos={kudosFixture(11)} meId={100} />);
    await user.click(screen.getByRole('button', { name: 'and 1 more' }));
    const sheet = screen.getByRole('dialog', { name: 'Kudos' });
    expect(within(sheet).getAllByText(/New personal best:/)).toHaveLength(1);
  });

  it('shows the viewer their own chip in the second person and closes the sheets', async () => {
    const { user } = renderWithProviders(<KudosStrip kudos={kudosFixture(2)} meId={100} />);
    await user.click(screen.getByRole('button', { name: 'Pat Shooter1 · personal best' }));
    const sheet = screen.getByRole('dialog', { name: 'Pat Shooter1' });
    expect(within(sheet).getByText(/New personal best:/)).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('centres the name link text in its 44 px target', async () => {
    const { user } = renderWithProviders(<KudosStrip kudos={kudosFixture(11)} meId={null} />);
    await user.click(screen.getByRole('button', { name: 'and 1 more' }));
    const link = screen.getByRole('link', { name: 'Pat Shooter1' });
    expect(link).toHaveClass('min-h-11', 'inline-flex', 'items-center', 'self-start');
  });

  it('closes the full list', async () => {
    const { user } = renderWithProviders(<KudosStrip kudos={kudosFixture(11)} meId={null} />);
    await user.click(screen.getByRole('button', { name: 'and 1 more' }));
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('writes names first-name first and labels kinds it does not know as kudos', () => {
    expect(naturalName('Hadley, Ike')).toBe('Ike Hadley');
    expect(naturalName('Cher')).toBe('Cher');
    expect(kudosLabel('pf.pb')).toBe('personal best');
    expect(kudosLabel('pf.someday')).toBe('kudos');
  });
});
