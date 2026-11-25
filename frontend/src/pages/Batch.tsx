import {Clapperboard, CircleCheck, CircleX, Download, FileSpreadsheet, Film, FlaskConical, LoaderCircle, Link2, Play, RotateCcw, ScrollText, Upload} from 'lucide-react';
import {useCallback, useEffect, useId, useRef, useState, type DragEvent} from 'react';
import {api, withToken, type Job} from '../lib/api';
import {plural, titleCase} from '../lib/format';
import {href, usePoll} from '../lib/hooks';
import {useStudio} from '../lib/studio';
import {styleInfo} from '../lib/styles';
import {Badge, Button, Check as CheckBox, Field, Input, LinkButton, Notice, Panel, Segmented, Select, cx} from '../components/ui';

type Row = {row: number; ok: boolean; errors: string[]; data: Record<string, string | boolean | string[] | number>};
type Preview = {raw: Record<string, string>[]; results: Row[]; columns: string[]; sample?: boolean};
type Mode = 'scripts' | 'render';
type RowState = {state: 'waiting' | 'writing' | 'script' | 'rendering' | 'done' | 'failed' | 'paused'; slug?: string; detail?: string};
type Run = {job: string; mode: Mode; rows: number[]; status: string; states: Record<string, RowState>; offset: number};
const INTERVALS = [['30m', '30 min'], ['45m', '45 min'], ['1h', '1 hour'], ['2h', '2 hours'], ['4h', '4 hours'], ['custom', 'Custom…']] as const;
const RUN_KEY = 'vf-horde-run';
const LINE = /\[batch \d+\/\d+\] ROW (\S+) (WRITING|SCRIPT|RENDERING|DONE|FAILED|PAUSED) ?(.*)$/;

/** Read the job log's progress lines into a per-row state (one line per change, the last one wins). */
function applyLog(states: Record<string, RowState>, text: string): Record<string, RowState> {
  const next = {...states};
  for (const line of text.split(/\r?\n/)) {
    const m = LINE.exec(line.trim());
    if (!m) continue;
    const [, row, kind, rest] = m;
    const prev = next[row] ?? {state: 'waiting'};
    if (kind === 'WRITING') next[row] = {...prev, state: 'writing'};
    else if (kind === 'SCRIPT') next[row] = {state: 'script', slug: rest.trim()};
    else if (kind === 'RENDERING') next[row] = {state: 'rendering', slug: rest.trim() || prev.slug};
    else if (kind === 'DONE') next[row] = {state: 'done', slug: rest.trim() || prev.slug};
    else if (kind === 'FAILED') next[row] = {...prev, state: 'failed', detail: rest.trim()};
    else next[row] = {...prev, state: 'paused', detail: rest.trim()};
  }
  return next;
}

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

const STATE_UI: Record<RowState['state'], {label: string; tone: 'volt' | 'candle' | 'blood' | 'ghost' | 'neutral'}> = {
  waiting: {label: 'Waiting', tone: 'neutral'},
  writing: {label: 'Writing…', tone: 'ghost'},
  script: {label: 'Script ready', tone: 'candle'},
  rendering: {label: 'Rendering…', tone: 'ghost'},
  done: {label: 'Alive', tone: 'volt'},
  failed: {label: 'Failed', tone: 'blood'},
  paused: {label: 'Paused', tone: 'candle'},
};

function Progress({r, st}: {r: Row; st?: RowState}) {
  if (!st) return r.ok ? <Badge tone="volt">Ready</Badge> : <Badge tone="blood">Fix</Badge>;
  const ui = STATE_UI[st.state];
  const busy = st.state === 'writing' || st.state === 'rendering';
  return (
    <span className="flex flex-col items-start gap-1">
      <Badge tone={ui.tone} icon={busy ? LoaderCircle : undefined} className={busy ? '[&_svg]:animate-spin' : ''}>{ui.label}</Badge>
      {st.slug && st.state === 'script' ? <a className="text-xs font-semibold text-pumpkin underline underline-offset-4" href={href('render', {project: st.slug})}>Open on the Table</a> : null}
      {st.slug && st.state === 'done' ? <a className="text-xs font-semibold text-pumpkin underline underline-offset-4" href={href('library', {item: st.slug})}>Open in the Vault</a> : null}
      {st.detail && (st.state === 'failed' || st.state === 'paused') ? <span className="max-w-[28ch] text-xs text-blood">{st.detail}</span> : null}
    </span>
  );
}

function PreviewTable({p, states}: {p: Preview; states: Record<string, RowState> | null}) {
  const cols = ['title', 'input_mode', 'style', 'aspect_ratio', 'language', 'length', 'auto_publish', 'platforms', 'schedule_at'];
  return (
    <>
      <div className="hidden overflow-x-auto rounded-md border border-lab-700 md:block" tabIndex={0} aria-label="Batch preview table">
        <table className="w-full min-w-[900px] text-left text-sm">
          <caption className="sr-only">Rows from the sheet and their progress</caption>
          <thead className="sticky top-0 bg-lab-800 text-xs font-semibold text-moss">
            <tr>
              <th scope="col" className="px-3 py-2 text-right tabular">Row</th>
              <th scope="col" className="px-3 py-2">{states ? 'Progress' : 'Status'}</th>
              {cols.map((c) => <th key={c} scope="col" className="px-3 py-2">{titleCase(c)}</th>)}
            </tr>
          </thead>
          <tbody>
            {p.results.map((r) => (
              <tr key={r.row} className={cx('border-t border-lab-700 align-top', !r.ok && 'bg-blood-deep/40')}>
                <td className="px-3 py-2 text-right text-fog tabular">{r.row}</td>
                <td className="px-3 py-2">
                  <Progress r={r} st={states?.[String(r.row)]} />
                  {!r.ok ? <ul className="mt-1 max-w-[28ch] text-xs text-blood">{r.errors.map((e) => <li key={e}>{e}</li>)}</ul> : null}
                </td>
                {cols.map((c) => (
                  <td key={c} className="max-w-[26ch] px-3 py-2 text-bone [overflow-wrap:anywhere]">
                    {c === 'title' ? <span className="line-clamp-2 font-semibold">{cell(r.data[c]) || <span className="font-normal text-fog">AI suggests</span>}</span>
                      : c === 'style' ? styleInfo(cell(r.data[c])).name
                      : c === 'length' ? (Number(r.data[c]) ? `${r.data[c]}s` : <span className="text-fog">default</span>)
                      : c === 'language' ? (cell(r.data[c]) ? titleCase(cell(r.data[c])) : <span className="whitespace-nowrap text-fog">default</span>)
                      : cell(r.data[c]) || <span className="text-fog">–</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="flex flex-col gap-2 md:hidden" aria-label="Batch rows">
        {p.results.map((r) => (
          <li key={r.row} className={cx('rounded-md border p-3', r.ok ? 'border-lab-700 bg-lab-850' : 'border-blood/50 bg-blood-deep/40')}>
            <div className="flex items-start gap-2">
              {r.ok ? <CircleCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-volt" /> : <CircleX aria-hidden className="mt-0.5 size-5 shrink-0 text-blood" />}
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-bone [overflow-wrap:anywhere]">{cell(r.data.title) || `Row ${r.row}`}</p>
                <p className="text-xs text-moss">Row {r.row} · {cell(r.data.input_mode)} · {styleInfo(cell(r.data.style)).name} · {cell(r.data.aspect_ratio)}</p>
                {!r.ok ? <ul className="mt-1 text-sm text-blood">{r.errors.map((e) => <li key={e}>{e}</li>)}</ul> : null}
                {states ? <div className="mt-2"><Progress r={r} st={states[String(r.row)]} /></div> : null}
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
  const [preview, setPreview] = useState<Preview | null>(() => {
    try {
      return (JSON.parse(localStorage.getItem(RUN_KEY) ?? 'null') as {preview?: Preview} | null)?.preview ?? null;
    } catch {
      return null;
    }
  });
  const [run, setRun] = useState<Run | null>(() => {
    try {
      return (JSON.parse(localStorage.getItem(RUN_KEY) ?? 'null') as {run?: Run} | null)?.run ?? null;
    } catch {
      return null;
    }
  });
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<Mode>(() => (localStorage.getItem('vf-horde-mode') as Mode) || 'scripts');
  const [skipBad, setSkipBad] = useState(true);
  const [gap, setGap] = useState('1h');
  const [custom, setCustom] = useState('');
  const [start, setStart] = useState('');
  const ids = {url: useId(), int: useId(), custom: useId(), start: useId()};

  // the run survives leaving the page: progress is re-read from the job log when you come back
  useEffect(() => {
    if (run || preview) localStorage.setItem(RUN_KEY, JSON.stringify({run, preview}));
    else localStorage.removeItem(RUN_KEY);
  }, [run, preview]);
  useEffect(() => localStorage.setItem('vf-horde-mode', mode), [mode]);
  useEffect(() => {
    if (demo && !preview) void act(async () => setPreview(await api<Preview>('/api/demo/batch')));
  }, [demo, preview, act]);

  const live = Boolean(run && !['done', 'failed', 'cancelled'].includes(run.status));
  const poll = useCallback(async () => {
    if (!run) return;
    try {
      const r = await api<{text: string; offset: number; status: string}>(`/api/jobs/${run.job}/log?offset=${run.offset}`);
      setRun((cur) => (cur && cur.job === run.job ? {...cur, offset: r.offset, status: r.status, states: applyLog(cur.states, r.text)} : cur));
    } catch {
      setRun((cur) => (cur ? {...cur, status: 'failed'} : cur)); // the server restarted: the job is gone
    }
  }, [run]);
  usePoll(poll, 1500, live);
  useEffect(() => {
    if (run && run.offset === 0) void poll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run?.job]);

  const fresh = (p: Preview) => {
    setPreview(p);
    setRun(null);
  };
  const upload = (f: File) =>
    act(async () => {
      setBusy(true);
      try {
        const fd = new FormData();
        fd.append('file', f);
        fresh(await api<Preview>('/api/batch/preview-file', {method: 'POST', body: fd}));
      } finally {
        setBusy(false);
      }
    });
  const loadSheet = () =>
    act(async () => {
      if (!url.trim()) throw new Error('Paste a Google Sheets link first.');
      setBusy(true);
      try {
        fresh(await api<Preview>('/api/batch/preview-url', {method: 'POST', body: {url: url.trim()}}));
      } finally {
        setBusy(false);
      }
    });

  const results = preview?.results ?? [];
  const bad = results.filter((r) => !r.ok).length;
  const good = results.length - bad;
  const publishing = results.filter((r) => r.ok && r.data.auto_publish).length;
  const willRun = skipBad ? good : bad ? 0 : good;
  const reason = !preview ? 'Load a sheet to start.' : !good ? 'No row is ready yet: fix the rows in red.' : bad && !skipBad ? `Fix ${plural(bad, 'row')} in red, or skip them.` : gap === 'custom' && mode === 'render' && publishing && !custom.trim() ? 'Type a custom interval, e.g. 90m.' : live ? 'A batch is already running.' : '';

  const start_ = (only?: number[]) =>
    act(async () => {
      if (!preview) return;
      const body = {raw: preview.raw, mode, skip_bad: skipBad, only_rows: only, interval: gap === 'custom' ? custom.trim() : gap, start: start ? `${start}:00` : ''};
      const job = await api<Job>('/api/batch/run', {method: 'POST', body});
      const rows = (only ?? results.filter((r) => r.ok).map((r) => r.row));
      setRun({job: job.id, mode, rows, status: 'queued', offset: 0, states: Object.fromEntries(rows.map((n) => [String(n), {state: 'waiting'} as RowState]))});
      watch(job, mode === 'render' ? `The Horde: ${plural(rows.length, 'video')} to write and render` : `The Horde: ${plural(rows.length, 'script')} to write`, (s) =>
        toast(s === 'done' ? (mode === 'render' ? 'The Horde has risen. Every video is in the Vault.' : 'Every script is on the Operating Table.') : 'The batch finished with some failures. The rows say why.', s === 'done' ? 'ok' : 'err'));
    });

  // slug -> sheet row, for the render-written job (its log lines are keyed by slug)
  const [rowAlias, setRowAlias] = useState<Record<string, string>>({});
  const raw = run?.states ?? null;
  const states = raw ? Object.fromEntries(Object.entries(raw).map(([k, v]) => [rowAlias[k] ?? k, v])) : null;
  const vals = states ? Object.values(states) : [];
  const count = (s: RowState['state']) => vals.filter((v) => v.state === s).length;
  const scriptsReady = states ? Object.entries(states).filter(([, v]) => v.state === 'script' && v.slug) : [];
  const failedRows = states ? Object.entries(states).filter(([, v]) => v.state === 'failed' || v.state === 'paused').map(([k]) => Number(k)).filter(Number.isFinite) : [];
  const finished = run && !live;
  const renderWritten = () =>
    act(async () => {
      const slugs = scriptsReady.map(([, v]) => v.slug!);
      const job = await api<Job>('/api/batch/render-written', {method: 'POST', body: {slugs}});
      const moved = new Set(scriptsReady.map(([k]) => k));
      setRun((cur) => {
        if (!cur) return cur;
        const kept = Object.fromEntries(Object.entries(cur.states).filter(([k]) => !moved.has(k)));
        return {...cur, job: job.id, mode: 'render', status: 'queued', offset: 0, states: {...kept, ...Object.fromEntries(scriptsReady.map(([, v]) => [v.slug!, {...v}]))}};
      });
      // render-written reports rows by slug; map them back to sheet rows as they arrive
      setRowAlias(Object.fromEntries(scriptsReady.map(([k, v]) => [v.slug!, k])));
      watch(job, `The Horde: rendering ${plural(slugs.length, 'script')}`, (s) => toast(s === 'done' ? 'The Horde has risen. Every video is in the Vault.' : 'Some renders failed. The rows say why.', s === 'done' ? 'ok' : 'err'));
    });
  const shown = states;
  // a failed row that already has its script only needs rendering again; one without a script is rewritten
  const retry = () =>
    act(async () => {
      const entries = Object.entries(states ?? {}).filter(([, v]) => v.state === 'failed' || v.state === 'paused');
      const toRender = entries.filter(([, v]) => v.slug);
      const toWrite = entries.filter(([, v]) => !v.slug).map(([k]) => Number(k)).filter(Number.isFinite);
      if (toWrite.length) return start_(toWrite);
      const slugs = toRender.map(([, v]) => v.slug!);
      const job = await api<Job>('/api/batch/render-written', {method: 'POST', body: {slugs}});
      setRowAlias((a) => ({...a, ...Object.fromEntries(toRender.map(([k, v]) => [v.slug!, k]))}));
      setRun((cur) => (cur ? {...cur, job: job.id, mode: 'render', status: 'queued', offset: 0} : cur));
      watch(job, `The Horde: re-rendering ${plural(slugs.length, 'video')}`, (s) => toast(s === 'done' ? 'Every retried video is in the Vault.' : 'Some renders failed again. The rows say why.', s === 'done' ? 'ok' : 'err'));
    });
  const pct = run && run.rows.length ? Math.round(((count('done') + count('failed') + (run.mode === 'scripts' ? count('script') : 0)) / run.rows.length) * 100) : 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Panel id="batch-in" title="Feed the lab a spreadsheet" description="Every row becomes a script. Choose whether the Horde stops there or renders each one, one video at a time.">
          <DropZone onFile={upload} busy={busy} />
          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-end">
            <Field label="Or a public Google Sheets link" htmlFor={ids.url} hint="Share it as “Anyone with the link can view”." className="flex-1">
              <Input id={ids.url} type="url" inputMode="url" spellCheck={false} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://docs.google.com/spreadsheets/d/…" />
            </Field>
            <Button icon={Link2} loading={busy} onClick={loadSheet} className="sm:mb-[1.6rem]">Load Sheet</Button>
          </div>
        </Panel>
        <Panel id="batch-sample" title="Start from the sample" description="Twelve columns, example rows and a README tab. Friendly spellings work: “Case Study”, “vertical”, “yt, insta”.">
          <LinkButton href={withToken('/api/batch/sample')} download="video-factory-batch-sample.xlsx" icon={Download}>Download Sample Excel</LinkButton>
          <dl className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-sm">
            {[['input_mode', 'idea or script'], ['title', 'becomes the folder'], ['content', 'the idea or full script'], ['style', 'e.g. whiteboard'], ['aspect_ratio', '9:16, 16:9, 1:1'], ['music_mood', 'chill, documentary…'], ['voice', 'empty = style narrator'], ['auto_publish', 'yes or no'], ['platforms', 'youtube,instagram'], ['schedule_at', 'optional time'], ['language', 'english, hinglish, hindi'], ['length', 'e.g. 45s or 3m']].map(([k, v]) => (
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
        title={run ? 'The Horde rises' : 'Preview'}
        description={preview ? `${plural(results.length, 'row')} · ${good} ready${bad ? ` · ${bad} need fixing` : ''}${publishing ? ` · ${publishing} will auto-publish` : ''}` : 'Rows appear here, checked before anything is written.'}
        action={preview?.sample ? <Badge tone="ghost" icon={FlaskConical}>Sample sheet</Badge> : null}
      >
        {run ? (
          <div className="mb-4" aria-live="polite">
            <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
              <span className="font-semibold text-bone">{live ? (run.mode === 'render' ? 'Writing every script, then rendering one at a time…' : 'Writing every script…') : 'Finished'}</span>
              <span className="text-moss tabular">{count('script')} scripts ready · {count('done')} alive · {count('failed') + count('paused')} failed</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-lab-800" role="progressbar" aria-label="Batch progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
              <div className="h-full rounded-full bg-volt transition-[width] duration-500" style={{width: `${pct}%`}} />
            </div>
          </div>
        ) : null}
        {preview ? <PreviewTable p={preview} states={shown} /> : <p className="text-sm text-moss">No sheet loaded yet.</p>}

        {!live ? (
          <div className="mt-5 flex flex-col gap-4">
            <div className="max-w-2xl">
              <Segmented<Mode>
                label="What should the Horde do?"
                value={mode}
                onChange={setMode}
                options={[
                  {value: 'scripts', label: 'Write scripts', hint: 'Every row lands on the Operating Table', icon: ScrollText},
                  {value: 'render', label: 'Write and render', hint: 'Auto-render each one, one at a time', icon: Clapperboard},
                ]}
              />
            </div>
            {bad ? <CheckBox label={`Skip the ${plural(bad, 'row')} that need fixing`} hint="The ready rows run now; fix the red ones in the sheet and load it again." checked={skipBad} onChange={setSkipBad} /> : null}
            {mode === 'render' && publishing ? (
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Gap between uploads" htmlFor={ids.int} hint="For rows with auto_publish = yes.">
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
            ) : mode === 'scripts' && publishing ? (
              <p className="text-sm text-fog">Auto-publish rows are scheduled once they are rendered; use “Write and render” to schedule them in one go.</p>
            ) : null}
            {demo && preview?.sample ? <Notice tone="ghost" title="Sample sheet">Starting it needs a language model for the idea rows. The preview above is the real validator’s output.</Notice> : null}
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="primary" icon={mode === 'render' ? Play : ScrollText} disabled={Boolean(reason)} onClick={() => start_()}>
                {mode === 'render' ? `Write and render ${plural(willRun, 'video')}` : `Write ${plural(willRun, 'script')}`}
              </Button>
              <span className="text-sm text-moss">{reason || (mode === 'render' ? 'About 20 s per script, then about 3 minutes per video.' : 'About 20 seconds per script. Render later, or all at once below.')}</span>
            </div>
          </div>
        ) : null}

        {finished && (scriptsReady.length || failedRows.length) ? (
          <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-lab-700 pt-4">
            {scriptsReady.length ? <Button icon={Clapperboard} onClick={renderWritten}>Render all {plural(scriptsReady.length, 'script')} now</Button> : null}
            {scriptsReady.length ? <LinkButton href={href('render')} variant="ghost" icon={Film}>Open the Operating Table</LinkButton> : null}
            {failedRows.length ? <Button variant="ghost" icon={RotateCcw} onClick={retry}>Retry {plural(failedRows.length, 'failed row')}</Button> : null}
          </div>
        ) : null}
      </Panel>
    </div>
  );
}
