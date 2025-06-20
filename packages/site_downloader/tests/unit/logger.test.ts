import { logger, setLogLevel } from '../../src/core/logger';

describe('logger', () => {
  let spy: jest.SpyInstance;

  beforeAll(() => {
    spy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterAll(() => spy.mockRestore());

  it('should respect log level', () => {
    setLogLevel('quiet');
    logger.error('err');   // no longer printed
    logger.warn('warn');
  });
});
