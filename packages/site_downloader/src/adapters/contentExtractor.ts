import fs from 'node:fs';
import path from 'node:path';
import TurndownService from 'turndown';
import { htmlToText } from 'html-to-text';
import { JSDOM } from 'jsdom';
import { Readability } from '@mozilla/readability';
import { withPage, BrowserOptions } from './browserAdapter.js';
import { logger } from '../core/logger.js';
import { deepScroll } from '../core/scroll.js';
import * as child_process from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import fsPromises from 'node:fs/promises';

export type Format = 'html' | 'md' | 'txt' | 'epub' | 'docx';

export interface ExtractOptions extends BrowserOptions {
  url: string;
  format: Format;
  output: string;
  articleMode: 'auto' | 'readability' | 'selector' | 'none';
  selector?: string;
  retries: number;
  maxScrolls: number; // NEW
  flags: {
    noAnnoyances: boolean;
    noScroll: boolean;
    noMedia: boolean;
    gfm: boolean;
  };
  turndown: {              // NEW
    headingStyle: string;
    codeBlockStyle: string;
  };
  wrapWidth: number;       // NEW (for txt)
}

async function stripMedia(page: any) {
  await page.evaluate(() => {
    document
      .querySelectorAll('img, video, audio, picture, source[srcset]')
      .forEach((el) => el.remove());
  });
}

function ensureDir(p: string) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
}

function runPandoc(input: string, outFile: string) {
  return new Promise<void>((res, rej) => {
    const p = child_process.spawn('pandoc', [input, '-o', outFile], { stdio: 'inherit' });
    p.on('exit', (code) => (code === 0 ? res() : rej(new Error('pandoc failed'))));
  });
}

export async function extract(opts: ExtractOptions) {
  ensureDir(opts.output);

  for (let attempt = 1; attempt <= opts.retries; attempt++) {
    try {
      await withPage(opts, async (page) => {
        logger.info(`➡️ Navigate ${opts.url}`);
        await page.goto(opts.url, { waitUntil: 'domcontentloaded', timeout: 60000 });

        if (!opts.flags.noAnnoyances) {
          const cssPath = path.resolve(
            dirname(fileURLToPath(import.meta.url)),
            '../core/annoyances.css',
          );
          await page.addStyleTag({ path: cssPath });
        }
        if (opts.flags.noMedia) await stripMedia(page);
        if (!opts.flags.noScroll) await deepScroll(page, opts.maxScrolls);

        const htmlFull = await page.content();
        let htmlMain = htmlFull;

        if (opts.selector) {
          const loc = page.locator(opts.selector).first();
          if ((await loc.count()) > 0) htmlMain = await loc.innerHTML();
        } else if (opts.articleMode !== 'none') {
          const dom = new JSDOM(htmlFull, { url: opts.url });
          const reader = new Readability(dom.window.document);
          const article = reader.parse();
          if (article?.content) {
            htmlMain = `<h1>${article.title}</h1>${article.content}`;
          }
        }

        let outputContent = '';
        switch (opts.format) {
          case 'html':
            outputContent = htmlMain;
            break;
            case 'md': {
              const headingStyle: 'setext' | 'atx' =
                opts.turndown.headingStyle === 'atx_closed' ? 'atx'
                                                            : (opts.turndown.headingStyle as 'setext' | 'atx');
            
              const td = new TurndownService({
                headingStyle,
                codeBlockStyle: opts.turndown.codeBlockStyle as 'indented' | 'fenced',
              });
            
              if (opts.flags.gfm) {
                // eslint-disable-next-line @typescript-eslint/ban-ts-comment
                // @ts-ignore  – plugin has no TypeScript declarations
                const { gfm } = await import('turndown-plugin-gfm');
                td.use(gfm);
              }
            
              outputContent = td.turndown(htmlMain);
              break;
            }            
          case 'txt':
            outputContent = htmlToText(htmlMain, { wordwrap: opts.wrapWidth });
            break;
          case 'epub':
          case 'docx': {
            const tmp = `${opts.output}.tmp.html`;
            await fsPromises.writeFile(tmp, htmlMain);
            await runPandoc(tmp, opts.output);
            await fsPromises.unlink(tmp);
            return;
          }
        }
        await fsPromises.writeFile(opts.output, outputContent);
      });
      return; // success
    } catch (err) {
      logger.warn(`Attempt ${attempt} failed: ${(err as Error).message}`);
      if (attempt === opts.retries) throw err;
    }
  }
}
