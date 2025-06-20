/**
 * Verifies that CLI flag parsing feeds the right, **typed** options
 * to the adapters – no browser launch required.  We rely on the global
 * Jest namespace provided by `@types/jest`, so no explicit import from
 * `@jest/globals` is necessary (avoids the TS 2307 error).
 */

// ---- 1. Mock the two adapter modules BEFORE the CLI is imported ----
jest.mock('../../src/adapters/pdfRenderer.js', () => ({ renderPdf: jest.fn() }));
jest.mock('../../src/adapters/contentExtractor.js', () => ({ extract: jest.fn() }));

// typed handles to the mocked fns
const { renderPdf } = jest.requireMock('../../src/adapters/pdfRenderer.js') as {
  renderPdf: jest.Mock;
};
const { extract } = jest.requireMock('../../src/adapters/contentExtractor.js') as {
  extract: jest.Mock;
};

// helper that isolates the CLI import each time
const runCLI = async (...args: string[]) => {
  await jest.isolateModulesAsync(async () => {
    process.argv = ['node', 'yt_bulk_cc', ...args];
    await import('../../src/cli/index.js'); // path relative to tests folder
  });
};

describe('yt_bulk_cc CLI', () => {
  beforeEach(() => jest.clearAllMocks());

  it('calls renderPdf() with default flags', async () => {
    await runCLI('grab', 'https://example.com');
    expect(renderPdf).toHaveBeenCalledTimes(1);
    expect(renderPdf).toHaveBeenCalledWith(
      expect.objectContaining({
        url: 'https://example.com',
        engine: 'chrome',
        colorScheme: 'light',
      }),
    );
  });

  it('routes to extract() when --format md is given', async () => {
    await runCLI(
      'grab',
      'https://example.com',
      '--format',
      'md',
      '--selector',
      'main',
      '--dark',
    );
    expect(extract).toHaveBeenCalledTimes(1);
    expect(extract).toHaveBeenCalledWith(
      expect.objectContaining({
        format: 'md',
        selector: 'main',
        colorScheme: 'dark',
      }),
    );
  });
});
