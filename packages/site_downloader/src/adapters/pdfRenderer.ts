import fs from 'node:fs';
import path from 'node:path';
import { withPage, BrowserOptions } from './browserAdapter.js';
import { logger } from '../core/logger.js';
import { deepScroll } from '../core/scroll.js';
import fsPromises from 'node:fs/promises';

export interface PdfOptions extends BrowserOptions {
  url: string;
  output: string;     // base path; .screen.pdf + .print.pdf will be produced
}

function ensureDir(p: string) { fs.mkdirSync(path.dirname(p), { recursive: true }); }

export async function renderPdf(opts: PdfOptions) {
  const { url, output } = opts;
  ensureDir(output);

  const screenPdf = output.replace(/\.pdf$/, '.screen.pdf');
  const printPdf  = output.replace(/\.pdf$/, '.print.pdf');
  const pngFallback = output.replace(/\.pdf$/, '.png');

  await withPage(opts, async (page) => {
    logger.info(`➡️ Navigate ${url}`);
    const resp = await page.goto(url, { waitUntil:'networkidle', timeout:90000 });
    if (!resp || !resp.ok()) throw new Error(`HTTP ${resp?.status()} on ${url}`);

    await deepScroll(page);
    await page.waitForTimeout(500);

    if (opts.engine === 'chrome') {
        // screen
        await page.emulateMedia({ media:'screen' });
        logger.info(`🖨  Save screen PDF ${screenPdf}`);
        await page.pdf({ path: screenPdf, format:'A4', printBackground:true, scale: opts.scale });
        // print
        await page.emulateMedia({ media:'print' });
        logger.info(`🖨  Save print PDF ${printPdf}`);
        await page.pdf({ path: printPdf, format:'A4', printBackground:true });
    } else {
        const pathOut = pngFallback;
        logger.info(`🖼  Save screenshot ${pathOut}`);
        await page.screenshot({ path: pathOut, fullPage:true });
    }
  });

  // move to screen/print folders
  if (fs.existsSync(screenPdf)) {
      const dir = path.join(path.dirname(screenPdf), 'screen');
      ensureDir(dir + '/x');
      await fsPromises.rename(screenPdf, path.join(dir, path.basename(screenPdf)));
  }
  if (fs.existsSync(printPdf)) {
      const dir = path.join(path.dirname(printPdf), 'print');
      ensureDir(dir + '/x');
      await fsPromises.rename(printPdf, path.join(dir, path.basename(printPdf)));
  }
}
