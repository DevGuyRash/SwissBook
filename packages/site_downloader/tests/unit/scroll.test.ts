import { deepScroll } from '../../src/core/scroll';
import type { Page } from 'playwright';

const makePage = (heights: number[]): Page =>
  ({
    evaluate: jest.fn(async (fn: () => unknown) => {
      // Ignore the call that only scrolls (returns undefined)
      if (fn.toString().includes('scrollTo')) return undefined;
      return heights.shift()!;
    }),
    waitForLoadState: jest.fn(),
    waitForTimeout: jest.fn(),
  } as unknown as Page);

describe('deepScroll()', () => {
  it('stops when height plateaus', async () => {
    // grows twice then plateaus
    const page = makePage([2_000, 4_000, 6_000, 6_000]);
    await deepScroll(page, 10);
    expect(page.evaluate).toHaveBeenCalledTimes(6); // 2 loops × 3 calls
  });

  it('honours max‑scroll limit', async () => {
    const page = makePage([...Array(12)].map((_, i) => 1_000 + i * 500));
    await deepScroll(page, 5);
    expect(page.evaluate).toHaveBeenCalledTimes(15); // 5 loops × 3 calls
  });
});
