import {CalendarClock, CalendarPlus, Check as CheckIcon, ChevronDown, CircleCheck, CircleQuestionMark, CircleX, ExternalLink, Moon, Pause, Play, RotateCcw, ShieldCheck, Trash, Zap} from 'lucide-react';
import {useEffect, useId, useMemo, useState} from 'react';
import {Badge, Button, Check, EmptyState, Field, Input, Notice, Panel, Select, Skeleton, Switch, cx} from '../components/ui';
import {api, type Job, type ProjectRow} from '../lib/api';
import {countdown, humanTime, platformName} from '../lib/format';
import {useApi, useNow, useRoute} from '../lib/hooks';
import {useStudio} from '../lib/studio';

type Upload = {platform: string; status: string; attempts: number; last_error: string | null};
type QueueJob = {
  id: string; type: string; title: string; enabled?: boolean; platforms?: string[]; generate_at?: string; upload_at?: string;
  generate_human: string; upload_human: string; step: number; needs_review: boolean; link: string; paused: boolean;
  state: {gen_status: string; last_error: string | null} | null; uploads: Upload[];
};
type Auth = {ok: boolean | null; checked_at: string | null; detail: string; paused: boolean; pause_reason?: string};
type ScheduleData = {
  defaults: Record<string, string | number>; jobs: QueueJob[]; events: {at: string; job_id: string | null; kind: string; detail: string}[];
  caps: Record<string, {used: number; cap: number}>; daemon: boolean;
  preflight: {keep_awake: boolean; safe_publish: boolean; auth: Record<string, Auth>};
};
type PreviewRow = {slug: string; title: string; upload_at: string; upload_human: string; generate_human: string; rendered: boolean};
const PLATFORMS = ['youtube', 'instagram', 'tiktok'];
const STEPS = ['Queued', 'Rendering', 'Uploading', 'Published'];

function PreFlight({s, reload}: {s: ScheduleData; reload: () => void}) {
  const {act, watch, toast} = useStudio();
  const setPre = (patch: Record<string, boolean>) => act(async () => { await api('/api/schedule/preflight', {method: 'PUT', body: patch}); reload(); });
  const daemon = (run: boolean) => act(async () => { await api('/api/schedule/daemon', {method: 'POST', body: {run}}); toast(run ? 'Scheduler daemon awake. It checks every minute.' : 'Daemon stopped. Scheduled work will wait.', run ? 'ok' : 'info'); reload(); });
  const check = (platform: string) => act(async () => watch(await api<Job>('/api/schedule/check-auth', {method: 'POST', body: {platform}}), `Checking the ${platformName(platform)} login`, reload));
  return (
    <Panel id="preflight" title="Pre-Flight" description="Everything that must be true before the lab runs unattended overnight.">
      <div className="grid gap-x-8 gap-y-2 lg:grid-cols-3">
        <Switch label={<>Scheduler Daemon <span className={s.daemon ? 'text-volt' : 'text-candle'}>{s.daemon ? 'ON' : 'OFF'}</span></>} hint="Runs scheduled renders and uploads while this app is open." checked={s.daemon} onChange={daemon} />
        <Switch label="Keep PC Awake" hint="Windows will not sleep while jobs are pending or running." checked={s.preflight.keep_awake} onChange={(v) => setPre({keep_awake: v})} />
        <Switch label="Safe-Publish Gate" hint="Videos with unverified facts render, then wait for your approval." checked={s.preflight.safe_publish} onChange={(v) => setPre({safe_publish: v})} />
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {PLATFORMS.map((p) => {
          const a = s.preflight.auth[p];
          const cap = s.caps[p];
          const Icon = a?.paused || a?.ok === false ? CircleX : a?.ok ? CircleCheck : CircleQuestionMark;
          const tone = a?.paused || a?.ok === false ? 'text-blood' : a?.ok ? 'text-volt' : 'text-fog';
          return (
            <div key={p} className="flex min-w-0 items-center gap-3 rounded-md border border-lab-700 bg-lab-850 p-2.5">
              <Icon aria-hidden className={cx('size-5 shrink-0', tone)} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-bone">{platformName(p)} <span className="font-normal text-fog">· {a?.paused ? 'paused' : a?.ok ? 'login OK' : a?.ok === false ? 'login expired' : 'not checked'}</span></p>
                <p className="text-xs text-moss tabular">{cap ? `${cap.used}/${cap.cap} uploads today` : ''}</p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => check(p)}>Check</Button>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function Builder({s, projects, reload}: {s: ScheduleData; projects: ProjectRow[]; reload: () => void}) {
  const {act, toast} = useStudio();
  const route = useRoute();
  const now = useNow(60_000);
  const [picked, setPicked] = useState<string[]>(() => (route.params.get('pick') ? [route.params.get('pick') as string] : []));
  const [first, setFirst] = useState('tonight');
  const [at, setAt] = useState('');
  const [spacing, setSpacing] = useState('1h');
  const [custom, setCustom] = useState('');
  const [mode, setMode] = useState<'just_in_time' | 'all_now'>('just_in_time');
  const [lead, setLead] = useState(20);
  const [platforms, setPlatforms] = useState<string[]>(['youtube']);
  const [visibility, setVisibility] = useState('');
  const [preview, setPreview] = useState<PreviewRow[] | null>(null);
  const [previewErr, setPreviewErr] = useState<string | null>(null);
  const ids = {first: useId(), at: useId(), sp: useId(), custom: useId(), lead: useId(), vis: useId()};
  const pick = route.params.get('pick');
  useEffect(() => {
    if (pick) setPicked((p) => (p.includes(pick) ? p : [...p, pick]));
  }, [pick]);
  const tonightLabel = new Date(now).getHours() >= 23 ? 'Tomorrow 11:00 PM' : 'Tonight 11:00 PM';
  const body = useMemo(
    () => ({projects: picked, first: first === 'picker' ? (at ? `${at}:00` : 'now') : first, spacing: spacing === 'custom' ? custom.trim() : spacing, mode, lead_min: lead, platforms, visibility}),
    [picked, first, at, spacing, custom, mode, lead, platforms, visibility],
  );
  useEffect(() => {
    if (!picked.length) {
      setPreview(null);
      return;
    }
    const t = window.setTimeout(() => {
      api<PreviewRow[]>('/api/schedule/builder/preview', {method: 'POST', body}).then((r) => { setPreview(r); setPreviewErr(null); }).catch((e: Error) => setPreviewErr(e.message));
    }, 250);
    return () => window.clearTimeout(t);
  }, [body, picked.length]);

  const blockers = [
    !s.daemon && 'Scheduler Daemon is OFF',
    ...platforms.filter((p) => s.preflight.auth[p]?.ok !== true).map((p) => `${platformName(p)} login is ${s.preflight.auth[p]?.ok === false ? 'expired' : 'not checked'}`),
  ].filter(Boolean) as string[];
  const create = () =>
    act(async () => {
      const r = await api<{jobs: string[]}>('/api/schedule/builder', {method: 'POST', body});
      toast(`${r.jobs.length} video${r.jobs.length === 1 ? '' : 's'} scheduled.`, 'ok');
      setPicked([]);
      reload();
    });
  const canAdd = picked.length > 0 && !previewErr;
  return (
    <Panel id="builder" title="Schedule Builder" description="Pick videos, the first slot and the spacing. Times update as you go.">
      <div className="flex flex-col gap-5">
        <fieldset className="min-w-0">
          <legend className="mb-2 text-sm font-semibold text-bone">Videos <span className="font-normal text-fog">({picked.length} picked)</span></legend>
          {projects.length ? (
            <div className="max-h-64 overflow-y-auto overscroll-contain rounded-md border border-lab-700 p-1" tabIndex={-1}>
              {projects.map((p) => (
                <Check key={p.slug} label={<span className="flex flex-wrap items-center gap-2"><span className="[overflow-wrap:anywhere]">{p.title || p.slug}</span>{p.rendered ? <Badge tone="volt">Rendered</Badge> : <Badge icon={null}>Renders first</Badge>}</span>} checked={picked.includes(p.slug)} onChange={(v) => setPicked(v ? [...picked, p.slug] : picked.filter((x) => x !== p.slug))} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-moss">No projects yet. Create one first.</p>
          )}
        </fieldset>
        <div className="grid gap-4 @md:grid-cols-2">
          <Field label="First upload" htmlFor={ids.first}>
            <Select id={ids.first} value={first} onChange={(e) => setFirst(e.target.value)}>
              <option value="now">Now</option>
              <option value="tonight">{tonightLabel}</option>
              <option value="picker">Pick a time…</option>
            </Select>
          </Field>
          {first === 'picker' ? (
            <Field label="Date and time" htmlFor={ids.at}>
              <Input id={ids.at} type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />
            </Field>
          ) : null}
          <Field label="Spacing" htmlFor={ids.sp}>
            <Select id={ids.sp} value={spacing} onChange={(e) => setSpacing(e.target.value)}>
              {[['30m', '30 min'], ['45m', '45 min'], ['1h', '1 hr'], ['2h', '2 hr'], ['4h', '4 hr'], ['custom', 'Custom…']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </Select>
          </Field>
          {spacing === 'custom' ? (
            <Field label="Custom spacing" htmlFor={ids.custom} hint="Like 90m or 1.5h.">
              <Input id={ids.custom} spellCheck={false} value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="90m" />
            </Field>
          ) : null}
        </div>
        <fieldset>
          <legend className="mb-2 text-sm font-semibold text-bone">When to render</legend>
          <div className="grid gap-2 @xl:grid-cols-2">
            {([['just_in_time', 'Just before each upload', 'Renders shortly before its slot. Fresh, but needs the PC on all night.'], ['all_now', 'Render all now', 'Renders one at a time right away; uploads stay staggered.']] as const).map(([v, l, h]) => (
              <label key={v} className={cx('flex min-h-16 cursor-pointer items-start gap-3 rounded-md border p-3 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-pumpkin', mode === v ? 'border-pumpkin bg-lab-800' : 'border-lab-600 bg-lab-850 hover:border-lab-400')}>
                <input type="radio" name="sb-mode" value={v} checked={mode === v} onChange={() => setMode(v)} className="mt-1 size-4 accent-[var(--color-pumpkin)]" />
                <span className="min-w-0"><span className="block text-sm font-semibold text-bone">{l}</span><span className="block text-[0.8125rem] text-moss">{h}</span></span>
              </label>
            ))}
          </div>
          {mode === 'just_in_time' ? (
            <div className="mt-3 max-w-56">
              <Field label="Minutes before upload" htmlFor={ids.lead}>
                <Input id={ids.lead} type="number" inputMode="numeric" min={5} max={240} value={lead} onChange={(e) => setLead(Number(e.target.value))} />
              </Field>
            </div>
          ) : null}
        </fieldset>
        <div className="grid gap-4 @lg:grid-cols-2">
          <fieldset>
            <legend className="mb-1 text-sm font-semibold text-bone">Platforms</legend>
            <div className="flex flex-wrap gap-x-4">{PLATFORMS.map((p) => <Check key={p} label={platformName(p)} checked={platforms.includes(p)} onChange={(v) => setPlatforms(v ? [...platforms, p] : platforms.filter((x) => x !== p))} />)}</div>
          </fieldset>
          <Field label="YouTube visibility" htmlFor={ids.vis}>
            <Select id={ids.vis} value={visibility} onChange={(e) => setVisibility(e.target.value)}>
              <option value="">Default ({String(s.defaults.youtube_visibility ?? 'unlisted')})</option>
              <option value="unlisted">Unlisted</option>
              <option value="private">Private</option>
              <option value="public">Public</option>
            </Select>
          </Field>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-bone">Preview</h3>
          {previewErr ? <p className="text-sm text-blood">{previewErr}</p> : preview?.length ? (
            <ol className="divide-y divide-lab-700 rounded-md border border-lab-700">
              {preview.map((r) => (
                <li key={r.slug} className="flex flex-wrap items-center gap-x-3 gap-y-1 p-2.5 text-sm">
                  <span className="min-w-0 flex-1 basis-48 font-semibold text-bone [overflow-wrap:anywhere]">{r.title}</span>
                  <span className="text-moss">{r.rendered ? 'ready' : `renders ${r.generate_human}`}</span>
                  <Badge tone="ghost" icon={CalendarClock}>{r.upload_human}</Badge>
                </li>
              ))}
            </ol>
          ) : <p className="text-sm text-moss">Pick at least one video to see its slot.</p>}
        </div>
        {canAdd && blockers.length ? (
          <Notice tone="candle" title="Not ready for an unattended night" action={<Button size="sm" variant="ghost" onClick={create}>Add Anyway</Button>}>
            <ul className="list-disc pl-5">{blockers.map((b) => <li key={b}>{b}</li>)}</ul>
            <p className="mt-1">Fix these in Pre-Flight above, or add the jobs now and fix them before the first slot.</p>
          </Notice>
        ) : null}
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary" icon={CalendarPlus} disabled={!canAdd || blockers.length > 0} onClick={create}>Add to Schedule</Button>
          <span className="text-sm text-moss">{!picked.length ? 'Pick at least one video.' : blockers.length ? 'Waiting on Pre-Flight.' : 'All checks green.'}</span>
        </div>
      </div>
    </Panel>
  );
}

function QueueCard({j, reload}: {j: QueueJob; reload: () => void}) {
  const {act, watch} = useStudio();
  const [confirm, setConfirm] = useState<'remove' | 'release' | null>(null);
  const now = useNow(30_000);
  // Naive ISO times (no offset) parse as local time, which is the schedule's time zone on this machine.
  const due = j.upload_at ? (Date.parse(j.upload_at) - now) / 1000 : null;
  const late = due != null && due < 0 && j.step < 3;
  const failed = j.state?.gen_status === 'failed' || j.uploads.some((u) => u.status === 'failed');
  const put = (enabled: boolean) => act(async () => { await api(`/api/schedule/jobs/${encodeURIComponent(j.id)}`, {method: 'PUT', body: {enabled}}); reload(); });
  const run = () => act(async () => watch(await api<Job>(`/api/schedule/run/${encodeURIComponent(j.id)}`, {method: 'POST'}), `Running “${j.title}” now`, reload));
  const retry = () => act(async () => watch(await api<Job>(`/api/schedule/retry/${encodeURIComponent(j.id)}`, {method: 'POST'}), 'Resetting the failed parts', reload));
  const remove = () => act(async () => { await api(`/api/schedule/jobs/${encodeURIComponent(j.id)}`, {method: 'DELETE'}); reload(); });
  const release = () => act(async () => { await api(`/api/schedule/release/${encodeURIComponent(j.id)}`, {method: 'POST'}); setConfirm(null); reload(); });
  return (
    <li className={cx('rounded-lg border p-4', j.paused ? 'border-lab-700 bg-lab-900' : failed ? 'border-blood/50 bg-lab-850' : 'border-lab-600 bg-lab-850')}>
      <div className="flex flex-wrap items-start gap-2">
        <p className="min-w-0 flex-1 basis-48 font-semibold text-bone [overflow-wrap:anywhere]">{j.title}</p>
        {j.paused ? <Badge icon={Pause}>Paused</Badge> : null}
        {late && !j.paused ? <Badge tone="candle">{countdown(due ?? 0)} late</Badge> : null}
        {j.needs_review ? <Badge tone="candle">Needs review</Badge> : null}
      </div>
      <p className="mt-1 text-sm text-moss">
        {j.type === 'upload_only' ? 'Already rendered' : `Renders ${j.generate_at ? humanTime(j.generate_at) : 'as soon as possible'}`} · uploads <b className="text-bone">{j.upload_at ? humanTime(j.upload_at) : j.upload_human}</b> · {(j.platforms ?? []).map(platformName).join(', ')}
      </p>
      <ol className="mt-3 grid grid-cols-2 gap-1.5 @md:grid-cols-4" aria-label="Progress">
        {STEPS.map((st, i) => {
          const done = i < j.step || j.step === 3;
          const nowStep = i === j.step && j.step < 3 && !j.paused;
          return (
            <li key={st} aria-current={nowStep ? 'step' : undefined} className={cx('flex min-w-0 items-center justify-center gap-1 rounded-md border px-1 py-1.5 text-xs font-semibold', done ? 'border-volt/40 bg-volt-deep/50 text-volt' : nowStep ? 'border-pumpkin text-pumpkin' : 'border-lab-600 text-fog')}>
              {done ? <CheckIcon aria-hidden className="size-3.5 shrink-0" /> : null}
              <span className="truncate">{st}</span>
            </li>
          );
        })}
      </ol>
      {j.uploads.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {j.uploads.map((u) => <Badge key={u.platform} tone={u.status === 'done' ? 'volt' : u.status === 'failed' ? 'blood' : u.status === 'needs_review' ? 'candle' : 'neutral'}>{platformName(u.platform)}: {u.status.replace('_', ' ')}</Badge>)}
          {j.link ? <a href={j.link} target="_blank" rel="noopener noreferrer" className="inline-flex h-6 items-center gap-1 text-xs font-semibold text-pumpkin underline underline-offset-4">View post <ExternalLink aria-hidden className="size-3" /></a> : null}
        </div>
      ) : null}
      {j.state?.last_error ? <p className="mt-2 text-sm text-blood [overflow-wrap:anywhere]">{j.state.last_error.split('\n')[0]}</p> : null}
      {j.needs_review ? (
        <div className="mt-3">
          <Notice tone="candle" title="Held by the Safe-Publish Gate" action={confirm === 'release' ? <div className="flex gap-2"><Button size="sm" variant="primary" icon={ShieldCheck} onClick={release}>Yes, release it</Button><Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>Not yet</Button></div> : <Button size="sm" variant="secondary" onClick={() => setConfirm('release')}>Approve Upload</Button>}>
            This video has unverified facts. Check them in the Library, then approve.
          </Notice>
        </div>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant="ghost" icon={j.paused ? Play : Pause} onClick={() => put(j.paused)}>{j.paused ? 'Resume' : 'Pause'}</Button>
        {j.step < 3 ? <Button size="sm" variant="ghost" icon={Zap} onClick={run}>Run Now</Button> : null}
        {failed ? <Button size="sm" variant="ghost" icon={RotateCcw} onClick={retry}>Retry</Button> : null}
        {confirm === 'remove' ? (
          <span className="flex gap-2"><Button size="sm" variant="danger" icon={Trash} onClick={remove}>Remove for good</Button><Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>Keep</Button></span>
        ) : (
          <Button size="sm" variant="ghost" icon={Trash} onClick={() => setConfirm('remove')}>Remove</Button>
        )}
      </div>
    </li>
  );
}

function Defaults({s, reload}: {s: ScheduleData; reload: () => void}) {
  const {act, toast} = useStudio();
  const [d, setD] = useState({timezone: String(s.defaults.timezone ?? ''), youtube_daily_cap: Number(s.defaults.youtube_daily_cap ?? 5), instagram_daily_cap: Number(s.defaults.instagram_daily_cap ?? 2), tiktok_daily_cap: Number(s.defaults.tiktok_daily_cap ?? 3)});
  const ids = {tz: useId(), yt: useId(), ig: useId(), tt: useId()};
  return (
    <details className="group rounded-lg border border-lab-700 bg-lab-900 px-4 sm:px-6">
      <summary className="flex min-h-14 list-none items-center gap-2 font-semibold text-bone [&::-webkit-details-marker]:hidden">
        <ChevronDown aria-hidden className="size-4 transition-transform group-open:rotate-180" />
        Time zone and daily caps
      </summary>
      <div className="grid gap-4 pb-5 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Time zone" htmlFor={ids.tz} hint="IANA name, e.g. Asia/Kolkata"><Input id={ids.tz} spellCheck={false} value={d.timezone} onChange={(e) => setD({...d, timezone: e.target.value})} /></Field>
        <Field label="YouTube per day" htmlFor={ids.yt}><Input id={ids.yt} type="number" min={0} max={50} value={d.youtube_daily_cap} onChange={(e) => setD({...d, youtube_daily_cap: Number(e.target.value)})} /></Field>
        <Field label="Instagram per day" htmlFor={ids.ig} hint="Keep at 1-2 to avoid challenges."><Input id={ids.ig} type="number" min={0} max={10} value={d.instagram_daily_cap} onChange={(e) => setD({...d, instagram_daily_cap: Number(e.target.value)})} /></Field>
        <Field label="TikTok per day" htmlFor={ids.tt}><Input id={ids.tt} type="number" min={0} max={20} value={d.tiktok_daily_cap} onChange={(e) => setD({...d, tiktok_daily_cap: Number(e.target.value)})} /></Field>
        <div className="sm:col-span-2 lg:col-span-4"><Button onClick={() => act(async () => { await api('/api/schedule/defaults', {method: 'PUT', body: d}); toast('Defaults saved.', 'ok'); reload(); })}>Save Defaults</Button></div>
      </div>
    </details>
  );
}

export default function Schedule() {
  const sched = useApi<ScheduleData>('/api/schedule');
  const projects = useApi<ProjectRow[]>('/api/projects');
  const reload = () => void sched.reload();
  if (sched.error) return <Notice tone="blood" title={sched.error.message} action={<Button size="sm" onClick={reload}>Retry</Button>}>{sched.error.hint}</Notice>;
  if (!sched.data) return <Skeleton className="h-[480px]" />;
  const s = sched.data;
  const active = s.jobs.filter((j) => j.step < 3);
  const done = s.jobs.filter((j) => j.step >= 3);
  return (
    <div className="flex flex-col gap-6">
      <PreFlight s={s} reload={reload} />
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Builder s={s} projects={projects.data ?? []} reload={reload} />
        <Panel id="queue" title="Queue" description={`${active.length} waiting · ${done.length} published`}>
          {s.jobs.length ? (
            <ul className="flex flex-col gap-3">{[...active, ...done].map((j) => <QueueCard key={j.id} j={j} reload={reload} />)}</ul>
          ) : (
            <EmptyState art={<Moon aria-hidden className="size-8 text-ghost" />} title="A quiet night">Nothing is queued. Pick videos in the builder and give them a slot.</EmptyState>
          )}
        </Panel>
      </div>
      <Defaults s={s} reload={reload} />
      <details className="group rounded-lg border border-lab-700 bg-lab-900 px-4 sm:px-6">
        <summary className="flex min-h-14 list-none items-center gap-2 font-semibold text-bone [&::-webkit-details-marker]:hidden">
          <ChevronDown aria-hidden className="size-4 transition-transform group-open:rotate-180" />
          Recent scheduler events
        </summary>
        <pre tabIndex={0} aria-label="Scheduler events" className="mb-5 max-h-72 overflow-auto rounded-md border border-lab-700 bg-lab-950 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-moss [overflow-wrap:anywhere]">
          {s.events.length ? s.events.map((e) => `${e.at.slice(0, 19).replace('T', ' ')}  ${e.job_id ?? '-'}  ${e.kind}  ${e.detail ?? ''}`).join('\n') : 'No events yet.'}
        </pre>
      </details>
    </div>
  );
}
