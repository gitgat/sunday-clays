import { expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThrownOutMark } from './ThrownOutMark';

it('shows a plain muted asterisk with the phrase as title and screen-reader text', () => {
  render(
    <p>
      43
      <ThrownOutMark phrase="Station 11 was thrown out" />
    </p>,
  );
  const mark = screen.getByTitle('Station 11 was thrown out');
  expect(mark).toHaveClass('ml-0.5', 'text-text-muted');
  expect(mark.querySelector('[aria-hidden="true"]')).toHaveTextContent(/^\*$/);
  expect(mark.querySelector('.sr-only')).toHaveTextContent('Station 11 was thrown out');
  expect(screen.getByText(/^43/).textContent).toBe('43* Station 11 was thrown out');
});
