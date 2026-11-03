import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import puppeteer from 'puppeteer-core';
import { browserPath } from './browser.mjs';

process.chdir(fileURLToPath(new URL('../', import.meta.url)));
const browser = await puppeteer.launch({ executablePath: browserPath(), headless: true });
try {
  const page = await browser.newPage();
  const failures = [];
  await page.setRequestInterception(true);
  page.on('request', request => {
    // A portable deck must load its artwork and fonts without network access.
    if (/^https?:/.test(request.url())) {
      failures.push(`External resource: ${request.url()}`);
      request.abort();
    } else request.continue();
  });
  page.on('requestfailed', request => failures.push(`Failed resource: ${request.url()}`));
  await page.goto(pathToFileURL(resolve('dist/slides.html')).href, { waitUntil: 'networkidle0' });
  const result = await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map(img => img.decode().catch(() => {})));
    const slides = [...document.querySelectorAll('section')];
    const issues = [];
    for (const [index, section] of slides.entries()) {
      const box = section.getBoundingClientRect();
      if (section.scrollWidth > section.clientWidth + 1 || section.scrollHeight > section.clientHeight + 1) {
        issues.push(`Slide ${index + 1}: content overflows the slide`);
      }
      for (const el of section.querySelectorAll('h1, h2, p, pre, table, img, .card, .authors, .meta, .presenter-card, .contact')) {
        const r = el.getBoundingClientRect();
        if (r.left < box.left - 1 || r.right > box.right + 1 || r.top < box.top - 1 || r.bottom > box.bottom + 1) {
          issues.push(`Slide ${index + 1}: ${el.tagName} extends past an edge`);
        }
      }
    }
    for (const img of document.images) {
      if (!img.complete || img.naturalWidth === 0) issues.push(`Broken image: ${img.getAttribute('src')}`);
    }
    const fonts = [...document.fonts].map(font => ({ family: font.family, status: font.status }));
    return { count: slides.length, issues, fonts, title: document.title, hasCode: !!document.querySelector("section pre, section code") };
  });
  assert.ok(result.count > 0, 'No rendered slides');
  assert.deepEqual([...failures, ...result.issues], [], 'Slide rendering failed');
  for (const name of ['Montserrat', ...(result.hasCode ? ['JetBrains Mono'] : [])]) {
    assert.ok(result.fonts.some(f => f.family === name && f.status === 'loaded'), `Font not loaded: ${name}`);
  }
  const metadata = JSON.parse(readFileSync('metadata.json', 'utf8'));
  assert.ok(result.title.includes(metadata.title), 'HTML title does not match metadata');
  for (const file of ['dist/slides.pdf', 'dist/slides-notes.pdf']) {
    const info = execFileSync('pdfinfo', [file], { encoding: 'utf8' });
    assert.equal(Number(info.match(/^Pages:\s+(\d+)/m)?.[1]), result.count, `${file}: wrong page count`);
    const text = execFileSync('pdftotext', [file, '-'], { encoding: 'utf8' });
    assert.ok(text.replace(/\s+/g, ' ').toLowerCase().includes(metadata.author.toLowerCase()), `${file}: missing author`);
    assert.ok(!/\{\{\w+\}\}/.test(text), `${file}: unresolved metadata placeholder`);
    const fonts = execFileSync('pdffonts', [file], { encoding: 'utf8' });
    assert.match(fonts, /Montserrat/, `${file}: missing Montserrat`);
    if (result.hasCode) assert.match(fonts, /JetBrainsMono/, `${file}: missing code font`);
  }
  console.log(`Checked ${result.count} slides: offline assets, fonts, overflow, metadata, and both PDFs.`);
} finally {
  await browser.close();
}
