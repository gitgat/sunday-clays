import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { insightFixture } from '../mocks';
import { InsightList, isMine } from './InsightList';

describe('InsightList', () => {
  it('renders nothing for no items', () => {
    const { container } = renderWithProviders(<InsightList items={[]} label="Insights" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lists the cards, reading the viewer's own single-shooter card in the second person", () => {
    renderWithProviders(
      <InsightList
        label="Insights"
        meId={3}
        columns={2}
        wideFirst
        items={[insightFixture({ key: 'a' }), insightFixture({ key: 'b', subject_id: '4' })]}
      />,
    );
    expect(screen.getByRole('list', { name: 'Insights' })).toBeInTheDocument();
    expect(screen.getAllByText(/New personal best:/)).toHaveLength(1);
    expect(screen.getAllByText(/New personal best for/)).toHaveLength(1);
  });

  it("reads every card in the second person on the viewer's own page", () => {
    renderWithProviders(
      <InsightList label="Insights" you items={[insightFixture({ key: 'a', subject_id: '9' })]} />,
    );
    expect(screen.getByText(/New personal best:/)).toBeInTheDocument();
  });

  it('knows whose insight is whose', () => {
    expect(isMine(insightFixture(), 3)).toBe(true);
    expect(isMine(insightFixture(), 4)).toBe(false);
    expect(isMine(insightFixture(), null)).toBe(false);
    expect(isMine(insightFixture({ subject_type: 'club', subject_id: '3' }), 3)).toBe(false);
  });
});
