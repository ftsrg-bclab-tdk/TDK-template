// Inspect only exported files; resolve the browser driver from the run-local tools.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const [component, exported, executablePath] = process.argv.slice(2);
const require = createRequire(resolve(component, 'package.json'));
const puppeteer = require('puppeteer-core');
const browser = await puppeteer.launch({executablePath, headless: true});
try {
  const page = await browser.newPage();
  const failures = [];
  const base = pathToFileURL(resolve(exported) + '/').href;
  await page.setRequestInterception(true);
  page.on('request', request => {
    const url = request.url();
    if (!url.startsWith(base) && !url.startsWith('data:') && !url.startsWith('about:')) {
      failures.push(`Resource outside exported deck: ${url}`);
      request.abort();
    } else request.continue();
  });
  page.on('requestfailed', request => failures.push(`Failed exported resource: ${request.url()}`));
  await page.goto(new URL('slides.html', base).href, {waitUntil: 'networkidle0'});
  const result = await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map(image => image.decode().catch(() => {})));
    return {slides: document.querySelectorAll('section').length,
      broken: [...document.images].filter(image => !image.complete || !image.naturalWidth).map(image => image.src),
      loadedFonts: [...document.fonts].filter(font => font.status === 'loaded').length};
  });
  assert.ok(result.slides > 0, 'Exported deck has no slides');
  assert.ok(result.loadedFonts > 0, 'Exported fonts did not load');
  assert.deepEqual([...failures, ...result.broken], [], 'Exported deck is incomplete');
  console.log(`Verified ${result.slides} exported slides independently of staging.`);
} finally {
  await browser.close();
}
