import { Page } from 'playwright';
import { logger } from './logger';

/** Scrolls to bottom until height stabilises or limit reached */
export async function deepScroll(page: Page, max = 10) {
  logger.debug('📜 Starting deep scroll…');
  let prev = -1, curr = 0, count = 0;
  while (count < max) {
    prev = await page.evaluate(() => document.body.scrollHeight);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForTimeout(500);
    curr = await page.evaluate(() => document.body.scrollHeight);
    logger.debug(`Scroll ${count+1}/${max}: height=${curr}`);
    if (curr <= prev) break;
    count++;
  }
}
