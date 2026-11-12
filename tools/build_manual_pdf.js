#!/usr/bin/env node
// Render a Markdown manual to a styled, printable PDF.
// Usage: node tools/build_manual_pdf.js [input.md] [output.pdf]
// Default: docs/spirits-of-the-wild/manual.md -> docs/spirits-of-the-wild/manual.pdf
// Requires: pandoc (Markdown -> HTML) and the `playwright` node module (Chromium).
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '..');
const input = path.resolve(process.argv[2] || path.join(root, 'docs/spirits-of-the-wild/manual.md'));
const output = path.resolve(process.argv[3] || input.replace(/\.md$/, '.pdf'));

const CSS = `
  @page { size: A4; margin: 0; }
  main { padding: 16mm 16mm 16mm 16mm; -webkit-box-decoration-break: clone; box-decoration-break: clone; }
  :root { --navy: #14213d; --accent: #2a6f97; --bg: #fbf9f4; --rule: #d9d3c4; --ink: #222; }
  html, body { background: var(--bg); }
  body { font-family: "DejaVu Serif", Georgia, serif; color: var(--ink);
         font-size: 10.5pt; line-height: 1.5; margin: 0; }
  h1, h2, h3, h4 { font-family: "DejaVu Sans", Helvetica, Arial, sans-serif; color: var(--navy);
                   page-break-after: avoid; break-after: avoid; }
  h1 { font-size: 24pt; margin: 0 0 4pt; border-bottom: 3px solid var(--navy); padding-bottom: 6pt; }
  h2 { font-size: 15pt; margin: 18pt 0 6pt; border-bottom: 1px solid var(--rule); padding-bottom: 3pt; }
  h3 { font-size: 12pt; margin: 12pt 0 4pt; }
  h4 { font-size: 11pt; margin: 10pt 0 3pt; color: var(--accent); }
  hr { border: 0; border-top: 1px solid var(--rule); margin: 14pt 0; }
  table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9.8pt;
          page-break-inside: avoid; break-inside: avoid; background: #fff; }
  th { background: var(--navy); color: #fff; text-align: left; font-family: "DejaVu Sans", sans-serif; }
  th, td { border: 1px solid var(--rule); padding: 4pt 7pt; vertical-align: top; }
  tr:nth-child(even) td { background: #f3f0e8; }
  blockquote { margin: 8pt 0; padding: 6pt 10pt; background: #e8eef5; border-left: 4px solid var(--accent); }
  blockquote p { margin: 0; }
  ul, ol { padding-left: 18pt; }
  li { margin: 2pt 0; }
  p { margin: 5pt 0; orphans: 3; widows: 3; }
  strong { color: #111; }
`;

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'manual-'));
const htmlPath = path.join(tmp, 'manual.html');
const body = execFileSync('pandoc', ['-f', 'gfm', '-t', 'html5', input], { encoding: 'utf8' });
const title = (fs.readFileSync(input, 'utf8').match(/^#\s+(.+)$/m) || [, 'Manual'])[1];
fs.writeFileSync(htmlPath, `<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>${title}</title><style>${CSS}</style></head><body><main>${body}</main></body></html>`);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + htmlPath, { waitUntil: 'load' });
  await page.pdf({
    path: output, format: 'A4', printBackground: true, preferCSSPageSize: true,
  });
  await browser.close();
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log('Wrote ' + output);
})().catch((e) => { console.error(e); process.exit(1); });
