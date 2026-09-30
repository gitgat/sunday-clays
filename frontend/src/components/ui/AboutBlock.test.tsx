import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { expectExplainer } from '../../test/charts';
import { renderWithProviders } from '../../test/render';
import { AboutBlock } from './AboutBlock';

const explainer = {
  what: 'Shows a thing.',
  read: ['Read it left to right.'],
  computed: ['Count the things.'],
  scope: 'all-time' as const,
};

describe('AboutBlock', () => {
  it('opens and closes the three-part explainer with its scope tag', async () => {
    const { container } = renderWithProviders(<AboutBlock explainer={explainer} />);
    expect(container).toHaveTextContent('All time');
    await expectExplainer(container, 'About this table', { read: true });
  });

  it('takes a custom label and leaves out a missing "How to read it"', async () => {
    const { container } = renderWithProviders(
      <AboutBlock explainer={{ what: 'Shows a thing.', computed: ['Count.'] }} label="About x" />,
    );
    await expectExplainer(container, 'About x', { read: false });
  });

  it('renders nothing without an explainer', () => {
    const { container } = render(<AboutBlock explainer={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
