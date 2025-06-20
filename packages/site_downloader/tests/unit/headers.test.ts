import { makeClientHints } from '../../src/core/headers';
// delete:  import UA from 'user-agents';
type UA = { toString(): string };     // new

const ua = (str: string): UA => ({ toString: () => str });

describe('makeClientHints()', () => {
  it('detects Google Chrome on desktop', () => {
    const headers = makeClientHints(
      ua(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      )
    );
    expect(headers['Sec-CH-UA']).toMatch(/Google Chrome/);
    expect(headers['Sec-CH-UA-Mobile']).toBe('?0');
    expect(headers['Sec-CH-UA-Platform']).toBe('"Windows"');
  });

  it('detects Microsoft Edge and omits Google Chrome brand', () => {
    const headers = makeClientHints(
      ua(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
          '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0'
      )
    );
    expect(headers['Sec-CH-UA']).toMatch(/Microsoft Edge/);
    expect(headers['Sec-CH-UA']).not.toMatch(/Google Chrome/);
  });

  it('flags mobile UAs correctly', () => {
    const headers = makeClientHints(
      ua(
        'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 ' +
          '(KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36'
      )
    );
    expect(headers['Sec-CH-UA-Mobile']).toBe('?1');
    expect(headers['Sec-CH-UA-Platform']).toBe('"Android"');
  });
});
