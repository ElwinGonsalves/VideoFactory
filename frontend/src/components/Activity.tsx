import {CalendarClock, ChevronDown, CircleCheck, CircleStop, CircleX, Clapperboard, Film, Ghost, LoaderCircle, RotateCcw, Square, Upload, Zap} from 'lucide-react';
import {useEffect, useRef, useState} from 'react';
import {api, type Job, type Slot, type StudioJob} from '../lib/api';
import {countdown, elapsed, humanTime, platformName, titleCase} from '../lib/format';
import {href, navigate, useNow, usePoll} from '../lib/hooks';
import {useStudio} from '../lib/studio';
import {Overlay} from './Overlay';
import {StitchStepper} from './StitchStepper';
import {styleInfo} from '../lib/styles';
import {Badge, Button, SpecimenTag, cx} from './ui';

const KIND_LABEL: Record<string, string> = {render: 'Rendering', llm: 'Writing', analyze: 'Reading reference', approve: 'Approving', batch: 'Batch', smoke: 'Smoke test', publish: 'Uploading', login: 'Login', doctor: 'Health check'};

function liveElapsed(j: StudioJob, nowMs: number) {
  const start = j.started ?? j.created;
  const end = j.ended ?? nowMs / 1000;
  return Math.max(0, end - start);
}

// ------------------------------------------------------------------ the header pill
export function StudioPill() {
  const {studio, offline, setDrawerOpen, drawerOpen} = useStudio();
  const now = useNow(1000);
  const btn = useRef<HTMLButtonElement>(null);
  let dot = 'bg-volt';
  let main = 'Ready';
  let detail = '';
  let short = 'Ready';
  if (offline) {
    dot = 'bg-blood';
    main = 'Server offline';
    short = 'Offline';
    detail = 'start ui/server.py';
  } else if (!studio) {
    dot = 'bg-fog';
    main = 'Connecting…';
    short = '…';
  } else if (studio.now) {
    const j = studio.now;
    dot = 'bg-pumpkin animate-flicker';
    const node = j.node ? titleCase(studio.nodes.find((n) => n.id === j.node)?.label ?? j.node) : KIND_LABEL[j.kind] ?? 'Working';
    main = j.title;
    detail = `${node}${j.percent != null ? ` ${j.percent}%` : ''} · ${elapsed(liveElapsed(j, now))}`;
    short = j.percent != null ? `${node} ${j.percent}%` : node;
  } else {
    const next = studio.upcoming.find((s) => s.kind === 'upload' && !s.held) ?? studio.upcoming[0];
    main = 'Ready';
    if (studio.scheduled) {
      const left = next ? (Date.parse(next.at) - now) / 1000 : 0;
      detail = `${studio.scheduled} Scheduled${next ? ` · Next ${next.kind} ${left < 0 ? `overdue ${countdown(left)}` : `in ${countdown(left)}`}` : ''}`;
      short = `${studio.scheduled} scheduled`;
      if (next && left < 0) dot = 'bg-candle';
    } else {
      detail = 'Nothing scheduled';
    }
    if (studio.queued.length) detail = `${studio.queued.length} queued · ${detail}`;
  }
  return (
    <button
      ref={btn}
      type="button"
      onClick={() => setDrawerOpen(true)}
      aria-haspopup="dialog"
      aria-expanded={drawerOpen}
      aria-label={`Studio activity: ${main}${detail ? `, ${detail}` : ''}. Open activity`}
      className="group flex h-10 min-w-0 max-w-full items-center gap-2.5 rounded-full border border-lab-600 bg-lab-900 pr-4 pl-3 text-sm transition-[border-color,box-shadow] duration-200 hover:border-volt/60 hover:shadow-glow"
    >
      <span aria-hidden className={cx('size-2.5 shrink-0 rounded-full', dot)} />
      <span className="hidden min-w-0 items-baseline gap-2 md:flex">
        <span className="max-w-[22ch] truncate font-semibold text-bone">{main}</span>
        {detail ? <span className="truncate text-moss tabular">· {detail}</span> : null}
      </span>
      <span className="truncate font-semibold text-bone tabular md:hidden">{short}</span>
      <Zap aria-hidden className="size-4 shrink-0 text-fog transition-colors group-hover:text-volt" />
    </button>
  );
}

// ------------------------------------------------------------------ logs
function LogTail({jobId, live}: {jobId: string; live: boolean}) {
  const [text, setText] = useState('');
  const offset = useRef(0);
  const pre = useRef<HTMLPreElement>(null);
  useEffect(() => {
    offset.current = 0;
    setText('');
  }, [jobId]);
  usePoll(async () => {
    const r = await api<{text: string; offset: number}>(`/api/jobs/${jobId}/log?offset=${offset.current}`);
    if (r.text) {
      offset.current = r.offset;
      setText((t) => (t + r.text).slice(-60_000));
      requestAnimationFrame(() => pre.current && (pre.current.scrollTop = pre.current.scrollHeight));
    }
  }, live ? 1500 : 60_000);
  return (
    <pre ref={pre} tabIndex={0} aria-label="Job log" className="mt-2 max-h-64 overflow-auto rounded-md border border-lab-700 bg-lab-950 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-moss [overflow-wrap:anywhere]">
      {text || 'Waiting for output…'}
    </pre>
  );
}

// ------------------------------------------------------------------ sections
function NowGenerating() {
  const {studio, act, toast, refresh, setDrawerOpen} = useStudio();
  const now = useNow(1000);
  const [confirm, setConfirm] = useState(false);
  const j = studio?.now;
  useEffect(() => setConfirm(false), [j?.id]);
  if (!j) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-dashed border-lab-600 p-4">
        <Ghost aria-hidden className="size-8 shrink-0 text-fog" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-bone">The lab is quiet.</p>
          <p className="text-sm text-moss">No creature on the table. Start one and watch it come alive here.</p>
        </div>
        <Button size="sm" variant="secondary" onClick={() => { setDrawerOpen(false); navigate('create'); }}>Start a video</Button>
      </div>
    );
  }
  const cancel = () =>
    act(async () => {
      await api(`/api/jobs/${j.id}/cancel`, {method: 'POST'});
      toast('Cancelled. The creature sleeps.', 'info');
      setConfirm(false);
      await refresh();
    });
  const others = (studio?.running.length ?? 1) - 1 + (studio?.queued.length ?? 0);
  return (
    <div className="rounded-lg border border-lab-600 bg-lab-850 p-4">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[0.8125rem] text-fog">{KIND_LABEL[j.kind] ?? 'Working'}</p>
          <p className="font-semibold text-bone [overflow-wrap:anywhere]">{j.title}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            {j.style ? <SpecimenTag>{styleInfo(j.style).name}</SpecimenTag> : null}
            {j.aspect_ratio ? <Badge icon={null}>{j.aspect_ratio}</Badge> : null}
            <span className="text-xs text-moss tabular">{elapsed(liveElapsed(j, now))} elapsed</span>
          </div>
        </div>
        {j.percent != null ? <span className="font-display text-3xl leading-none text-pumpkin tabular" aria-label={`${j.percent} percent`}>{j.percent}%</span> : null}
      </div>
      {j.pipeline ? (
        <div className="mt-4">
          <StitchStepper activeIndex={j.node_index} />
        </div>
      ) : null}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {confirm ? (
          <>
            <Button size="sm" variant="danger" icon={CircleStop} onClick={cancel}>Yes, stop it</Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirm(false)}>Keep going</Button>
          </>
        ) : (
          <Button size="sm" variant="ghost" icon={CircleStop} onClick={() => setConfirm(true)}>Cancel</Button>
        )}
        {others > 0 ? <span className="text-xs text-moss">{others} more waiting their turn</span> : null}
      </div>
      <details className="group mt-3">
        <summary className="flex min-h-10 list-none items-center gap-1.5 text-sm font-semibold text-moss hover:text-bone [&::-webkit-details-marker]:hidden">
          <ChevronDown aria-hidden className="size-4 transition-transform group-open:rotate-180" />
          Show log
        </summary>
        <LogTail jobId={j.id} live />
      </details>
    </div>
  );
}

function SlotRow({s, now}: {s: Slot; now: number}) {
  const left = (Date.parse(s.at) - now) / 1000;
  const overdue = left < 0;
  const Icon = s.kind === 'generate' ? Clapperboard : Upload;
  return (
    <li className="flex items-center gap-3 py-2.5">
      <span className={cx('grid size-9 shrink-0 place-items-center rounded-full border', s.held ? 'border-candle/50 text-candle' : 'border-ghost/40 text-ghost')}>
        <Icon aria-hidden className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-bone" title={s.title}>{s.title}</p>
        <p className="text-xs text-moss">
          {s.kind === 'generate' ? 'Renders' : 'Uploads'} {humanTime(s.at)} · {s.platforms.map(platformName).join(', ')}
        </p>
      </div>
      {s.held ? <Badge tone="candle">Needs review</Badge> : <Badge tone={overdue ? 'candle' : 'ghost'} icon={null}><span className="tabular">{overdue ? `${countdown(left)} late` : `in ${countdown(left)}`}</span></Badge>}
    </li>
  );
}

function UpNext() {
  const {studio, setDrawerOpen} = useStudio();
  const now = useNow(15_000);
  const slots = studio?.upcoming ?? [];
  return (
    <div>
      {studio && slots.length && !studio.daemon ? (
        <p className="mb-2 rounded-md border border-candle/40 bg-candle-deep p-2.5 text-[0.8125rem] text-candle">
          The scheduler daemon is off in this session, so these slots will not run on their own. Turn it on in Schedule.
        </p>
      ) : null}
      {slots.length ? (
        <ul className="divide-y divide-lab-700">{slots.map((s) => <SlotRow key={`${s.job_id}-${s.kind}`} s={s} now={now} />)}</ul>
      ) : (
        <p className="py-2 text-sm text-moss">Nothing scheduled. The night is young.</p>
      )}
      <a href={href('schedule')} onClick={() => setDrawerOpen(false)} className="mt-2 inline-flex min-h-10 items-center gap-1.5 text-sm font-semibold text-pumpkin underline-offset-4 hover:underline">
        <CalendarClock aria-hidden className="size-4" />
        Manage Schedule
      </a>
    </div>
  );
}

function Recent() {
  const {studio, act, watch, setDrawerOpen, refresh} = useStudio();
  const [openLog, setOpenLog] = useState<string | null>(null);
  const items = studio?.recent ?? [];
  if (!items.length) return <p className="py-2 text-sm text-moss">No finished jobs in this session yet.</p>;
  const retry = (j: StudioJob) =>
    act(async () => {
      const job = await api<Job>(`/api/projects/${encodeURIComponent(j.slug)}/render`, {method: 'POST', body: {}});
      watch(job, `Retrying ${j.title}`);
      await refresh();
    });
  return (
    <ul className="divide-y divide-lab-700">
      {items.map((j) => {
        const ok = j.status === 'done';
        const Icon = ok ? CircleCheck : j.status === 'cancelled' ? Square : CircleX;
        return (
          <li key={j.id} className="py-2.5">
            <div className="flex items-start gap-3">
              <Icon aria-hidden className={cx('mt-0.5 size-5 shrink-0', ok ? 'text-volt' : j.status === 'cancelled' ? 'text-fog' : 'text-blood')} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-bone [overflow-wrap:anywhere]">{j.title}</p>
                <p className="text-xs text-moss">
                  {KIND_LABEL[j.kind] ?? j.kind} · {ok ? 'done' : j.status} {j.ended ? `· ${humanTime(new Date(j.ended * 1000))}` : ''}
                </p>
                <div className="mt-1.5 flex flex-wrap gap-2">
                  {ok && j.has_video ? (
                    <Button size="sm" variant="secondary" icon={Film} onClick={() => { setDrawerOpen(false); navigate('library', {item: j.slug}); }}>Open in Library</Button>
                  ) : null}
                  {!ok && j.kind === 'render' && j.slug ? <Button size="sm" variant="secondary" icon={RotateCcw} onClick={() => retry(j)}>Retry</Button> : null}
                  <Button size="sm" variant="ghost" aria-expanded={openLog === j.id} onClick={() => setOpenLog(openLog === j.id ? null : j.id)}>{openLog === j.id ? 'Hide log' : 'View log'}</Button>
                </div>
                {openLog === j.id ? <LogTail jobId={j.id} live={false} /> : null}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function ActivityDrawer() {
  const {drawerOpen, setDrawerOpen, studio} = useStudio();
  return (
    <Overlay
      open={drawerOpen}
      onClose={() => setDrawerOpen(false)}
      variant="right"
      title="Studio Activity"
      description={studio?.now ? 'Something is stirring on the table.' : 'Everything the lab is doing, has done, and will do.'}
    >
      <div className="flex flex-col gap-6">
        <section aria-labelledby="act-now">
          <h3 id="act-now" className="mb-2 flex items-center gap-2 font-display text-xl leading-none text-bone">
            {studio?.now ? <LoaderCircle aria-hidden className="size-4 animate-spin text-pumpkin" /> : null}
            Now Generating
          </h3>
          <NowGenerating />
        </section>
        <section aria-labelledby="act-next">
          <h3 id="act-next" className="mb-1 font-display text-xl leading-none text-bone">Up Next (Scheduled)</h3>
          <UpNext />
        </section>
        <section aria-labelledby="act-recent">
          <h3 id="act-recent" className="mb-1 font-display text-xl leading-none text-bone">Recent Activity</h3>
          <Recent />
        </section>
      </div>
    </Overlay>
  );
}
