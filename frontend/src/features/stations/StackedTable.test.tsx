import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StackedTable } from './StackedTable';

describe('StackedTable', () => {
  it('renders a captioned table whose cells carry their column label', () => {
    render(
      <StackedTable
        caption="Demo"
        headers={['Name', 'Hits', 'Misses']}
        rows={[{ key: 'a', header: 'Row A', cells: ['3', '4'] }]}
      />,
    );
    expect(screen.getByRole('table', { name: 'Demo' })).toBeInTheDocument();
    expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'Name',
      'Hits',
      'Misses',
    ]);
    const row = screen.getByRole('row', { name: /^Row A\b/ });
    expect(screen.getByRole('rowheader', { name: 'Row A' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '3' })).toHaveAttribute('data-label', 'Hits');
    expect(row).toHaveTextContent('4');
  });

  it('copes with no headers at all', () => {
    render(<StackedTable caption="Empty" headers={[]} rows={[]} />);
    expect(screen.getByRole('table', { name: 'Empty' })).toBeInTheDocument();
  });
});
