import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { Tabs } from './Tabs';

const TABS = [
  { value: 'season', label: 'Season' },
  { value: 'rolling_12', label: 'Rolling 12' },
  { value: 'all_time', label: 'All time' },
] as const;

function Harness() {
  const [value, setValue] = useState<(typeof TABS)[number]['value']>('season');
  return (
    <>
      <Tabs label="Period" tabs={TABS} value={value} onChange={setValue} />
      <p>selected:{value}</p>
    </>
  );
}

describe('Tabs', () => {
  it('marks exactly one tab selected and makes only it tabbable', () => {
    render(<Harness />);
    const tabs = screen.getAllByRole('tab');
    expect(tabs.map((t) => t.getAttribute('aria-selected'))).toEqual(['true', 'false', 'false']);
    expect(tabs.map((t) => t.tabIndex)).toEqual([0, -1, -1]);
    expect(screen.getByRole('tablist', { name: 'Period' })).toBeInTheDocument();
  });

  it('selects on click', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('tab', { name: 'All time' }));
    expect(screen.getByText('selected:all_time')).toBeInTheDocument();
  });

  it('moves selection and focus with arrow, Home and End keys, wrapping at the ends', async () => {
    render(<Harness />);
    screen.getByRole('tab', { name: 'Season' }).focus();
    await userEvent.keyboard('{ArrowLeft}');
    expect(screen.getByText('selected:all_time')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'All time' })).toHaveFocus();
    await userEvent.keyboard('{ArrowRight}');
    expect(screen.getByText('selected:season')).toBeInTheDocument();
    await userEvent.keyboard('{End}');
    expect(screen.getByText('selected:all_time')).toBeInTheDocument();
    await userEvent.keyboard('{Home}');
    expect(screen.getByText('selected:season')).toBeInTheDocument();
    await userEvent.keyboard('{Enter}');
    expect(screen.getByText('selected:season')).toBeInTheDocument();
  });
});
