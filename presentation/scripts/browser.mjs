import { accessSync, constants } from 'node:fs';
import { delimiter } from 'node:path';

export function browserPath() {
  const candidates = process.env.CHROME_PATH ? [process.env.CHROME_PATH] : [
    ...(process.env.PATH || '').split(delimiter).flatMap(p =>
      ['chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable'].map(n => `${p}/${n}`)),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ];
  for (const path of candidates) {
    try { accessSync(path, constants.X_OK); return path; } catch { /* Try the next location. */ }
  }
  throw new Error('Chrome/Chromium not found. Install it or set CHROME_PATH to its executable.');
}
