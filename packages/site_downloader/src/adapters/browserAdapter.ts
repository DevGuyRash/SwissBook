import { chromium, firefox, webkit, LaunchOptions, Page } from 'playwright';
import UserAgent from 'user-agents';
import { logger } from '../core/logger.js';
import { makeClientHints, defaultHeaders } from '../core/headers.js';

export interface BrowserOptions {
  engine: 'chrome' | 'firefox' | 'webkit';
  proxy?: string;
  colorScheme: 'light' | 'dark';
  viewport: { width: number; height: number };
  scale: number;
  extraHeaders?: Record<string,string>;
}

export async function withPage<T>(opts: BrowserOptions, callback:(page:Page, ua:UserAgent)=>Promise<T>): Promise<T> {
  const launchOpts: LaunchOptions = { headless: true };
  if (opts.proxy) launchOpts.proxy = { server: opts.proxy };

  const browserType = opts.engine === 'firefox' ? firefox :
                      opts.engine === 'webkit'  ? webkit  : chromium;
  const browser = await browserType.launch(launchOpts);

  try {
    const ua = new UserAgent();
    logger.info(`🕵️ UA: ${ua.toString()}`);

    const ctx = await browser.newContext({
      userAgent: ua.toString(),
      colorScheme: opts.colorScheme,
      deviceScaleFactor: opts.scale,
      viewport: opts.viewport,
      extraHTTPHeaders: {
        ...defaultHeaders(),
        ...makeClientHints(ua),
        ...opts.extraHeaders
      }
    });
    const page = await ctx.newPage();
    const result = await callback(page, ua);
    await ctx.close();
    return result;
  } finally {
    await browser.close();
  }
}
