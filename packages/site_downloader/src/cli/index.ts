#!/usr/bin/env node
import { Command } from 'commander';
import path from 'node:path';
import { renderPdf } from '../adapters/pdfRenderer.js';
import { extract } from '../adapters/contentExtractor.js';
import { logger, setLogLevel } from '../core/logger.js';

const program = new Command();

program
  .name('yt_bulk_cc')
  .description('Bulk capture to PDF / Markdown / TXT / EPUB / DOCX')
  .version('0.2.0')
  .option('--verbose', 'Verbose logging')
  .option('--quiet',   'Quiet logging');

const commonFlags = (cmd: Command) =>
  cmd
    .option('-e, --engine <name>',  'chrome|firefox|webkit', 'chrome')
    .option('--proxy <url>',        'Proxy server')
    .option('--headers <json>',     'Extra HTTP headers (JSON string)')
    .option('--width <px>',         'Viewport width', '1280')
    .option('--scale <n>',          'Device scale factor', '2')
    .option('--dark',               'Dark mode');

const extractionFlags = (cmd: Command) =>
  cmd
    .option('--selector <css>', 'CSS selector to narrow content')
    .option('--article <mode>', 'auto|readability|selector|none', 'auto')
    .option('--max-scrolls <n>', 'Deep‑scroll iterations', '10')
    .option('--no-annoyances', 'Keep cookie/pop‑up overlays')
    .option('--no-scroll',   'Disable deep scroll')
    .option('--no-media',    'Remove <img>,<video> tags')
    .option('--no-gfm',      'Disable GitHub‑flavoured Markdown')
    .option('--heading-style <style>', 'atx|atx_closed|setext', 'atx')
    .option('--code-style <style>',    'fenced|indented', 'fenced')
    .option('--wrap-width <n>',        'Word‑wrap width for txt', '80');

/* ---------- grab ---------- */
commonFlags(extractionFlags(program.command('grab')))
  .argument('<url>', 'URL to capture')
  .option('-f, --format <fmt>', 'pdf|html|md|txt|epub|docx', 'pdf')
  .option('-o, --output <file>', 'Output path')
  .option('-r, --retries <n>', 'Retry count', '1')
  .hook('preAction', (cmd) => {
    if (cmd.opts().verbose) setLogLevel('verbose');
    if (cmd.opts().quiet)   setLogLevel('quiet');
  })
  .action(async (url, options) => {
    const absOut = path.resolve(
      options.output ??
        `out/${url.replace(/https?:\/\//, '').replace(/[/?=&]/g, '_')}.${options.format}`,
    );

    const baseBrowser = {
      engine: options.engine,
      proxy:  options.proxy,
      colorScheme: (options.dark ? 'dark' : 'light') as 'dark' | 'light',
      viewport: { width: Number(options.width), height: 720 },
      scale:    Number(options.scale),
      extraHeaders: options.headers ? JSON.parse(options.headers) : {},
    };

    if (options.format === 'pdf') {
      await renderPdf({ ...baseBrowser, url, output: absOut });
    } else {
      await extract({
        ...baseBrowser,
        url,
        format: options.format,
        output: absOut,
        articleMode: options.article,
        selector: options.selector,
        retries: Number(options.retries),
        maxScrolls: Number(options.maxScrolls),
        flags: {
          noAnnoyances: options.noAnnoyances ?? false,
          noScroll: options.noScroll ?? false,
          noMedia: options.noMedia ?? false,
          gfm: !(options.noGfm ?? false),
        },
        turndown: {
          headingStyle: options.headingStyle,
          codeBlockStyle: options.codeStyle,
        },
        wrapWidth: Number(options.wrapWidth),
      });
    }
  });

/* ---------- batch ---------- */
commonFlags(extractionFlags(program.command('batch')))
  .argument('<file>', 'File with list of URLs')
  .option('-f, --format <fmt>', 'pdf|html|md|txt|epub|docx', 'md')
  .option('-j, --jobs <n>', 'Parallel jobs', '4')
  .option('-r, --retries <n>', 'Retry each URL N times', '1')
  .hook('preAction', (cmd) => {
    if (cmd.opts().verbose) setLogLevel('verbose');
    if (cmd.opts().quiet)   setLogLevel('quiet');
  })
  .action(async (file, options) => {
    const lines = (await import('node:fs/promises')).readFile(file, 'utf8');
    const urls = (await lines).split(/\r?\n/).filter((l) => l.trim() && !l.startsWith('#'));
    const PQueue = (await import('p-queue')).default;
    const q = new PQueue({ concurrency: Number(options.jobs) });

    for (const u of urls) {
      q.add(async () => {
        let attempt = 0;
        while (attempt < Number(options.retries)) {
          try {
            await (program.commands.find((c) => c.name() === 'grab')!.action as any)(u, {
              ...options,
              retries: 1, // inner extractor handles its own retry
            });
            return;
          } catch (err) {
            attempt += 1;
            logger.warn(`Retry ${attempt}/${options.retries} failed for ${u}: ${(err as Error).message}`);
          }
        }
        logger.error(`❌ Giving up on ${u}`);
      });
    }
    await q.onIdle();
  });

program.parseAsync();
