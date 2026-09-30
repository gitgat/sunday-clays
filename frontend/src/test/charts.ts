import { screen, within } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import type { EChartsOption } from 'echarts';
import { getInstanceByDom } from 'echarts/core';
import { expect, vi } from 'vitest';

/** C10: every data chart exposes Table and CSV controls. `region` = the chart's titled card. */
export function expectChartControls(region: HTMLElement): void {
  expect(within(region).getByRole('button', { name: 'Table' })).toBeInTheDocument();
  expect(within(region).getByRole('button', { name: 'CSV' })).toBeInTheDocument();
}

/**
 * Every chart (and stat) with an explainer has a disclosure that opens a panel with the three
 * plain-language parts. `region` = the titled card; `name` = the disclosure's accessible name.
 */
export async function expectExplainer(
  region: HTMLElement,
  name: string | RegExp = 'About this chart',
  /** true = "How to read it" must show, false = it must be absent (empty `read`), omitted = unchecked. */
  { read }: { read?: boolean } = {},
): Promise<void> {
  const user = userEvent.setup();
  const button = within(region).getByRole('button', { name });
  expect(button).toHaveAttribute('aria-expanded', 'false');
  await user.click(button);
  expect(button).toHaveAttribute('aria-expanded', 'true');
  const panelId = button.getAttribute('aria-controls');
  expect(panelId).toBeTruthy();
  expect(document.getElementById(panelId ?? '')).toBeInTheDocument();
  expect(within(region).getByRole('heading', { name: 'What this shows' })).toBeVisible();
  expect(within(region).getByRole('heading', { name: "How it's worked out" })).toBeVisible();
  const readHeading = within(region).queryByRole('heading', { name: 'How to read it' });
  if (read === true) expect(readHeading).toBeVisible();
  if (read === false) expect(readHeading).toBeNull();
  await user.click(button);
  expect(button).toHaveAttribute('aria-expanded', 'false');
  expect(within(region).queryByRole('heading', { name: 'What this shows' })).toBeNull();
}

/**
 * Spies on the CSV download (an `<a download>` click plus the blob URL). `names` collects each
 * downloaded file name; `text()` decodes the last blob without its 3-byte BOM. Restore the spies
 * with `vi.restoreAllMocks()` in `afterEach`, as the chart tests do.
 */
export function captureCsv(): { names: string[]; text: () => Promise<string> } {
  const names: string[] = [];
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    names.push(this.download);
  });
  const createUrl = vi.spyOn(URL, 'createObjectURL');
  return {
    names,
    text: async () => {
      const blob = createUrl.mock.calls.at(-1)?.[0] as Blob;
      return new TextDecoder().decode((await blob.arrayBuffer()).slice(3));
    },
  };
}

/** Clicks the chart card's Fullscreen button and returns its dialog (`title` = the card title). */
export async function openFullscreen(
  user: UserEvent,
  region: HTMLElement,
  title: string,
): Promise<HTMLElement> {
  await user.click(within(region).getByRole('button', { name: 'Fullscreen' }));
  return screen.getByRole('dialog', { name: title });
}

/** The live ECharts option of the chart image inside `container` (`name` picks one of several). */
export function chartOptionIn(container: HTMLElement, name?: string | RegExp): EChartsOption {
  const img = within(container).getByRole('img', name === undefined ? undefined : { name });
  const chart = getInstanceByDom(img);
  if (chart === undefined) throw new Error('chartOptionIn: no ECharts instance on the chart image');
  return chart.getOption() as EChartsOption;
}
