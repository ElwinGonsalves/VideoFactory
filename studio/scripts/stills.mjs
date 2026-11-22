// Render many stills with ONE bundle and ONE browser (remotion `still` re-bundles per call).
// Usage: node scripts/stills.mjs <jobs.json>
// jobs.json: [{"composition": "ConceptExplainer", "props": "path/props.json" | {...}, "frame": 0, "output": "x.png"}]
import {bundle} from '@remotion/bundler';
import {openBrowser, renderStill, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const serveUrl = await bundle({entryPoint: path.join(here, '..', 'src', 'index.ts'), publicDir: path.join(here, '..', 'public')});
const browser = await openBrowser('chrome');
const propsCache = new Map();
const loadProps = (p) => {
  if (typeof p !== 'string') return p;
  if (!propsCache.has(p)) propsCache.set(p, JSON.parse(fs.readFileSync(p, 'utf8')));
  return propsCache.get(p);
};
try {
  for (const job of jobs) {
    const inputProps = {...loadProps(job.props), ...(job.override ?? {})};
    const composition = await selectComposition({serveUrl, id: job.composition, inputProps, puppeteerInstance: browser});
    const frame = Math.min(Math.max(0, job.frame ?? 0), composition.durationInFrames - 1);
    fs.mkdirSync(path.dirname(job.output), {recursive: true});
    const jpeg = job.output.endsWith('.jpg');
    await renderStill({
      composition,
      serveUrl,
      inputProps,
      frame,
      output: job.output,
      puppeteerInstance: browser,
      imageFormat: jpeg ? 'jpeg' : 'png',
      ...(jpeg ? {jpegQuality: 90} : {}),
    });
    console.log(`still ${job.composition}@${frame} -> ${job.output}`);
  }
} finally {
  await browser.close({silent: true});
}
