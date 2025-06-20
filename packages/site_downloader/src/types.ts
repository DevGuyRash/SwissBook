export interface CliCommon {
  proxy?: string;
  headers?: string;
  engine: 'chrome'|'firefox'|'webkit';
  width: number;
  scale: number;
  dark: boolean;
}
