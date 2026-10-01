import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../test/render';
import { sheetFixture } from '../sheet/mocks';
import { homeWidget } from './homeWidget';
import { insightFixture } from './mocks';

describe('insights home widget', () => {
  it('leads the Sheet with the issue’s headline, deck and spotlight', () => {
    const issue = sheetFixture({
      headline: insightFixture({ key: 'hero' }),
      recap: insightFixture({ key: 'recap', kind: 'home.sunday-recap' }),
      spotlight: insightFixture({ key: 'spot' }),
    });
    renderWithProviders(<homeWidget.Component meId={null} issue={issue} />);
    expect(screen.getByRole('list', { name: 'Top story' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Show all' })).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Spotlight' })).toBeInTheDocument();
  });

  it('renders nothing outside an issue', () => {
    const { container } = renderWithProviders(<homeWidget.Component meId={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
