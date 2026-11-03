import { readFileSync, mkdirSync, cpSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { browserPath } from './browser.mjs';

// Anchor every path here so this component also builds outside the monorepo.
const root = fileURLToPath(new URL('../', import.meta.url));
process.chdir(root);
const flags = process.argv.slice(2);
if (flags.some(flag => flag !== '--images')) throw new Error('Usage: npm run build [-- --images]');
const metadata = JSON.parse(readFileSync('metadata.json', 'utf8'));
const fields = ['title', 'subtitle', 'shortTitle', 'author', 'affiliation', 'event', 'date', 'projectUrl'];
for (const key of fields) {
  if (typeof metadata[key] !== 'string' || !metadata[key].trim() || /[\r\n]/.test(metadata[key])) {
    throw new Error(`metadata.json: ${key} must be a nonempty single-line string`);
  }
}
if (!['https:', 'http:'].includes(new URL(metadata.projectUrl).protocol)) {
  throw new Error('metadata.json: projectUrl must be an http(s) URL');
}
const escape = value => value.replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const slides = readFileSync('slides.md', 'utf8').replace(/\{\{(\w+)\}\}/g, (_, key) => {
  if (!fields.includes(key)) throw new Error(`Unknown metadata field: ${key}`);
  return escape(metadata[key]);
});
// JSON strings are valid YAML scalars; metadata cannot inject Marp directives.
const frontmatter = {
  marp: true, theme: 'bme', size: '16:9', paginate: true, math: false,
  title: metadata.title, author: metadata.author, description: metadata.subtitle,
  header: escape(metadata.shortTitle).replace(/([\\`*_{}\[\]()#+.!|~-])/g, '\\$1'),
  footer: '![ftsrg](assets/logos/ftsrg-grey.png) ![BME](assets/logos/bme-wordmark-grey.png)',
};
mkdirSync('dist', { recursive: true });
cpSync('assets', 'dist/assets', { recursive: true });
cpSync('figures', 'dist/figures', { recursive: true });
writeFileSync('dist/slides.md', `---\n${Object.entries(frontmatter).map(([k,v]) => `${k}: ${JSON.stringify(v)}`).join('\n')}\n---\n\n${slides}`);
const marp = resolve('node_modules/@marp-team/marp-cli/marp-cli.js');
const common = [marp, '--no-stdin', '--theme-set', 'theme/bme.css', '--html', '--allow-local-files', 'dist/slides.md'];
const env = { ...process.env, CHROME_PATH: browserPath() };
for (const args of [
  ['-o', 'dist/slides.html'],
  ['--pdf', '-o', 'dist/slides.pdf'],
  ['--pdf', '--pdf-notes', '-o', 'dist/slides-notes.pdf'],
  ...(flags.includes('--images') ? [['--images', 'png', '-o', 'dist/slide.png']] : []),
]) execFileSync(process.execPath, [...common, ...args], { stdio: 'inherit', env });
console.log('Built dist/slides.html, slides.pdf (audience), and slides-notes.pdf (presenter).');
