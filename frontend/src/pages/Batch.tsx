import {CircleCheck, CircleX, Download, FileSpreadsheet, FlaskConical, Link2, Play, Upload} from 'lucide-react';
import {useEffect, useId, useRef, useState, type DragEvent} from 'react';
import {api, withToken, type Job} from '../lib/api';
import {plural, titleCase} from '../lib/format';
import {useStudio} from '../lib/studio';
import {styleInfo} from '../lib/styles';
import {Badge, Button, Field, Input, LinkButton, Notice, Panel, Select, cx} from '../components/ui';

type Row = {row: number; ok: boolean; errors: string[]; data: Record<string, string | boolean | string[]>};
type Preview = {raw: Record<string, string>[]; results: Row[]; columns: string[]; sample?: boolean};
const INTERVALS = [['30m', '30 min'], ['45m', '45 min'], ['1h', '1 hour'], ['2h', '2 hours'], ['4h', '4 hours'], ['custom', 'Custom…']] as const;

function DropZone({onFile, busy}: {onFile: (f: File) => void; busy: boolean}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const id = useId();
  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  };
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={drop}
      className={cx('relative flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-[border-color,background-color] duration-200 select-none', over ? 'border-volt bg-volt-deep/30' : 'border-lab-500 bg-lab-950 hover:border-lab-400')}
    >
      <span className={cx('grid size-14 place-items-center rounded-full border-2 border-dashed', over ? 'border-volt text-volt' : 'border-lab-400 text-moss')}>
        <FileSpreadsheet aria-hidden className="size-6" />
      </span>
      <p className="font-display text-2xl tracking-wide text-bone">{over ? 'Drop it on the slab' : 'Drop an Excel or CSV sheet'}</p>
      <p className="text-sm text-moss">One row per video. Up to 100 rows, 5 MB.</p>
      <input ref={input} id={id} type="file" accept=".xlsx,.csv" className="sr-only" onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ''; }} />
      <label htmlFor={id} className="inline-flex h-10 items-center gap-2 rounded-md border border-lab-500 bg-lab-800 px-4 text-sm font-semibold text-bone transition-colors hover:border-lab-400 hover:bg-lab-700 has-[:focus-visible]:outline-2 pointer-coarse:h-11">
        <Upload aria-hidden className="size-4" />
        {busy ? 'Reading…' : 'Choose File'}
      </label>
    </div>
  );
}

function cell(v: unknown) {
  if (Array.isArray(v)) return v.join(', ');
  if (typeof v === 'boolean') return v ? 'yes' : 'no';
  return String(v ?? '');
}

function PreviewTable({p}: {p: Preview}) {
  const cols = ['title', 'input_mode', 'style', 'aspect_ratio', 'music_mood', 'auto_publish', 'platforms', 'schedule_at'];
  return (
    <>
      <div className="hidden overflow-x-auto rounded-md border border-lab-700 md:block" tabIndex={0} aria-label="Batch preview table">
        <table className="w-full min-w-[820px] text-left text-sm">
          <caption className="sr-only">Validated rows from the sheet</caption>
          <thead className="sticky top-0 bg-lab-800 text-xs font-semibold text-moss">
            <tr>
              <th scope="col" className="px-3 py-2 text-right tabular">Row</th>
              <th scope="col" className="px-3 py-2">Status</th>
              {cols.map((c) => <th key={c} scope="col" className="px-3 py-2">{titleCase(c)}</th>)}
            </tr>
          </thead>
          <tbody>
            {p.results.map((r) => (
              <tr key={r.row} className={cx('border-t border-lab-700 align-top', !r.ok && 'bg-blood-deep/40')}>
                <td className="px-3 py-2 text-right text-fog tabular">{r.row}</td>
                <td className="px-3 py-2">
                  {r.ok ? <Badge tone="volt">Ready</Badge> : <Badge tone="blood">Fix</Badge>}
                  {!r.ok ? <ul className="mt-1 max-w-[28ch] text-xs text-blood">{r.errors.map((e) => <li key={e}>{e}</li>)}</ul> : null}
                </td>
                {cols.map((c) => (
                  <td key={c} className="max-w-[26ch] px-3 py-2 text-bone [overflow-wrap:anywhere]">
                    {c === 'title' ? <span className="line-clamp-2 font-semibold">{cell(r.data[c]) || <span className="font-normal text-fog">AI suggests</span>}</span> : c === 'style' ? styleInfo(cell(r.data[c])).name : cell(r.data[c]) || <span className="text-fog">–</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="flex flex-col gap-2 md:hidden" aria-label="Batch preview rows">
        {p.results.map((r) => (
          <li key={r.row} className={cx('rounded-md border p-3', r.ok ? 'border-lab-700 bg-lab-850' : 'border-blood/50 bg-blood-deep/40')}>
            <div className="flex items-start gap-2">
              {r.ok ? <CircleCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-volt" /> : <CircleX aria-hidden className="mt-0.5 size-5 shrink-0 text-blood" />}
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-bone [overflow-wrap:anywhere]">{cell(r.data.title) || `Row ${r.row}`}</p>
                <p className="text-xs text-moss">Row {r.row} · {cell(r.data.input_mode)} · {styleInfo(cell(r.data.style)).name} · {cell(r.data.aspect_ratio)}</p>
                {!r.ok ? <ul className="mt-1 text-sm text-blood">{r.errors.map((e) => <li key={e}>{e}</li>)}</ul> : null}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}

export default function Batch() {
  const {act, watch, toast, demo} = useStudio();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [gap, setGap] = useState('1h');
  const [custom, setCustom] = useState('');
  const [start, setStart] = useState('');
  const ids = {url: useId(), int: useId(), custom: useId(), start: useId()};

  useEffect(() => {
    if (demo && !preview) void act(async () => setPreview(await api<Preview>('/api/demo/batch')));
  }, [demo, preview, act]);

  const upload = (f: File) =>
    act(async () => {
      setBusy(true);
      try {
        const fd = new FormData();
        fd.append('file', f);
        setPreview(await api<Preview>('/api/batch/preview-file', {method: 'POST', body: fd}));
      } finally {
        setBusy(false);
      }
    });
  const loadSheet = () =>
    act(async () => {
      if (!url.trim()) throw new Error('Paste a Google Sheets link first.');
      setBusy(true);
      try {
        setPreview(await api<Preview>('/api/batch/preview-url', {method: 'POST', body: {url: url.trim()}}));
      } finally {
        setBusy(false);
      }
    });
  const bad = preview?.results.filter((r) => !r.ok).length ?? 0;
  const total = preview?.results.length ?? 0;
  const publishing = preview?.results.filter((r) => r.data.auto_publish).length ?? 0;
  const reason = !preview ? 'Load a sheet to start.' : bad ? `Fix ${plural(bad, 'row')} marked in red first.` : gap === 'custom' && !custom.trim() ? 'Type a custom interval, e.g. 90m.' : '';
  const run = () =>
    act(async () => {
      if (!preview) return;
      const job = await api<Job>('/api/batch/run', {method: 'POST', body: {raw: preview.raw, interval: gap === 'custom' ? custom.trim() : gap, start: start ? `${start}:00` : ''}});
      watch(job, `Batch of ${plural(total, 'video')}, one at a time`, (s) => toast(s === 'done' ? 'Batch finished. Every creature is in the Library.' : 'The batch stopped. Studio Activity has the log.', s === 'done' ? 'ok' : 'err'));
    });

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Panel id="batch-in" title="Feed the lab a spreadsheet" description="Videos render strictly one at a time (a 6 GB GPU cannot do two). Rows marked auto_publish join the Schedule.">
          <DropZone onFile={upload} busy={busy} />
          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-end">
            <Field label="Or a public Google Sheets link" htmlFor={ids.url} hint="Share it as “Anyone with the link can view”." className="flex-1">
              <Input id={ids.url} type="url" inputMode="url" spellCheck={false} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://docs.google.com/spreadsheets/d/…" />
            </Field>
            <Button icon={Link2} loading={busy} onClick={loadSheet} className="sm:mb-[1.6rem]">Load Sheet</Button>
          </div>
        </Panel>
        <Panel id="batch-sample" title="Start from the sample" description="Ten columns, two example rows and a README tab.">
          <LinkButton href={withToken('/api/batch/sample')} download="video-factory-batch-sample.xlsx" icon={Download}>Download Sample Excel</LinkButton>
          <dl className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-sm">
            {[['input_mode', 'idea or script'], ['title', 'becomes the folder'], ['content', 'the idea or full script'], ['style', 'e.g. whiteboard'], ['aspect_ratio', '9:16, 16:9, 1:1'], ['music_mood', 'chill, documentary…'], ['voice', 'empty = default'], ['auto_publish', 'yes or no'], ['platforms', 'youtube,instagram'], ['schedule_at', 'optional time']].map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="font-mono text-xs leading-5 text-moss">{k}</dt>
                <dd className="text-fog">{v}</dd>
              </div>
            ))}
          </dl>
        </Panel>
      </div>

      <Panel
        id="batch-preview"
        title="Preview"
        description={preview ? `${plural(total, 'row')} · ${bad ? `${bad} need fixing` : 'all ready'} · ${publishing} will auto-publish` : 'Rows appear here, checked before anything renders.'}
        action={preview?.sample ? <Badge tone="ghost" icon={FlaskConical}>Sample sheet</Badge> : null}
      >
        {preview ? <PreviewTable p={preview} /> : <p className="text-sm text-moss">No sheet loaded yet.</p>}
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <Field label="Relative upload interval" htmlFor={ids.int} hint="Gap between auto-published uploads.">
            <Select id={ids.int} value={gap} onChange={(e) => setGap(e.target.value)}>
              {INTERVALS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </Select>
          </Field>
          {gap === 'custom' ? (
            <Field label="Custom interval" htmlFor={ids.custom} hint="Like 90m or 1.5h.">
              <Input id={ids.custom} value={custom} spellCheck={false} onChange={(e) => setCustom(e.target.value)} placeholder="90m" />
            </Field>
          ) : null}
          <Field label="First upload" htmlFor={ids.start} optional hint="Empty = as soon as the first render is done.">
            <Input id={ids.start} type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
          </Field>
        </div>
        {demo && preview?.sample ? <div className="mt-4"><Notice tone="ghost" title="Sample sheet">Starting it needs a Gemini key for the idea rows. The preview above is the real validator’s output.</Notice></div> : null}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button variant="primary" icon={Play} disabled={Boolean(reason)} onClick={run}>Start Batch</Button>
          {reason ? <span className="text-sm text-moss">{reason}</span> : <span className="text-sm text-moss">About 3 minutes per video, one after another.</span>}
        </div>
      </Panel>
    </div>
  );
}
