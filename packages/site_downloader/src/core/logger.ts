export enum LogLevel { ERROR = 0, WARN = 1, INFO = 2, DEBUG = 3 }

let currentLevel: LogLevel = LogLevel.INFO;

export function setLogLevel(flag: 'quiet' | 'info' | 'verbose' = 'info') {
  switch (flag) {
    case 'quiet': currentLevel = LogLevel.ERROR; break;
    case 'verbose': currentLevel = LogLevel.DEBUG; break;
    default: currentLevel = LogLevel.INFO;
  }
}

function write(level: LogLevel, first: unknown, ...rest: unknown[]) {
  if (level > currentLevel) return;
  const timestamp = new Date().toISOString();
  const tag = LogLevel[level];
  const fn = level === LogLevel.ERROR ? console.error :
             level === LogLevel.WARN  ? console.warn  : console.log;
  fn(`[${timestamp}] [${tag}]`, first, ...rest);
}

export const logger = {
  error: (m: unknown, ...a: unknown[]) => write(LogLevel.ERROR, m, ...a),
  warn:  (m: unknown, ...a: unknown[]) => write(LogLevel.WARN,  m, ...a),
  info:  (m: unknown, ...a: unknown[]) => write(LogLevel.INFO,  m, ...a),
  debug: (m: unknown, ...a: unknown[]) => write(LogLevel.DEBUG, m, ...a),
  setLogLevel
};

// auto‑detect CL flags once, before anything else runs
if (process.argv.includes('--quiet'))   setLogLevel('quiet');
if (process.argv.includes('--verbose')) setLogLevel('verbose');
