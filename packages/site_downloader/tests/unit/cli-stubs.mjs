import * as pdf from '../../dist/adapters/pdfRenderer.js';
import * as ce  from '../../dist/adapters/contentExtractor.js';

function hijack(ns, fn) {
  const orig = ns[fn];
  ns[fn] = (...args) => {
    if (process.env.TEST_CAPTURE) {
      console.log(JSON.stringify({ fn, args }));
    }
    return Promise.resolve(orig ? orig(...args) : undefined);
  };
}

hijack(pdf, 'renderPdf');
hijack(ce,  'extract');
