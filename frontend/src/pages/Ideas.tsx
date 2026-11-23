import {CalendarClock, Dna, Eye, FlaskConical, Link2, Pencil, RefreshCw, Sparkles, Undo2, Wand, X} from 'lucide-react';
import {useId, useState} from 'react';
import {api, fileUrl, type Blueprint, type Job, type Onboarding} from '../lib/api';
import {titleCase} from '../lib/format';
import {href, navigate, useApi} from '../lib/hooks';
import {slugFromJobLog, useStudio} from '../lib/studio';
import {styleInfo} from '../lib/styles';
import {Badge, Button, Check, EmptyState, Field, Input, Notice, Panel, Segmented, Select, Skeleton, SpecimenTag, Textarea, cx} from '../components/ui';

type Idea = {n: number; title: string; hook: string; hook_visual?: string; angle: string; case_study: string; style: string; aspect_ratio?: string; duration_sec?: number; music_mood: string; why_it_works: string; dismissed?: boolean};
type Run = {run: string; status: string; approved: number[]; projects: string[]; blueprint: Blueprint; ideas: Idea[]; sheets: string[]; sources: string[]; mode: string; topic: string};
type BlueprintRow = {name: string; aspect_ratio?: string; target_duration_sec?: number; created?: string};

// Illustrative cards for Judge Demo Mode. Labelled as samples everywhere they appear.
const SAMPLE_IDEAS: Idea[] = [
  {n: 1, title: 'Why IKEA Wants You Lost', hook: 'That maze is not an accident.', hook_visual: 'Top-down floor plan with one winding arrow', angle: 'Store layouts that slow you down raise basket size.', case_study: 'IKEA’s one-way showroom path', style: 'case_study', aspect_ratio: '9:16', duration_sec: 50, music_mood: 'documentary', why_it_works: 'Everyone has been lost in IKEA; the reveal reframes a shared memory.'},
  {n: 2, title: 'The $1 Bet That Built Costco', hook: 'This hot dog has cost $1.50 since 1985.', hook_visual: 'Counter rolling from 1985 to today, price frozen', angle: 'A loss leader that buys loyalty.', case_study: 'Costco food court pricing', style: 'concept_explainer', aspect_ratio: '9:16', duration_sec: 45, music_mood: 'upbeat', why_it_works: 'A concrete, checkable number in the first second.'},
  {n: 3, title: 'When Netflix Mailed DVDs', hook: 'Netflix waited ten years to stream.', hook_visual: 'Paper envelope slides into a timeline', angle: 'Patience as a strategy.', case_study: 'Netflix 1998 to 2007', style: 'vox_documentary', aspect_ratio: '9:16', duration_sec: 50, music_mood: 'documentary', why_it_works: 'Contradicts what viewers assume about tech speed.'},
];

/** Beats drawn to scale: the proportions of a reference video, at a glance. */
function BeatStrip({beats}: {beats: NonNullable<Blueprint['beat_template']>}) {
  const total = beats.reduce((s, b) => s + (b.pct_duration || 0), 0) || 1;
  const tones = ['bg-pumpkin', 'bg-volt', 'bg-ghost', 'bg-candle', 'bg-moss'];
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full" role="img" aria-label={`Beats: ${beats.map((b) => `${b.beat} ${Math.round((b.pct_duration / total) * 100)} percent`).join(', ')}`}>
        {beats.map((b, i) => <span key={b.beat + i} className={cx('h-full', tones[i % tones.length])} style={{width: `${(b.pct_duration / total) * 100}%`}} />)}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-moss">
        {beats.map((b, i) => (
          <li key={b.beat + i} className="flex items-center gap-1.5">
            <span aria-hidden className={cx('size-2 rounded-full', tones[i % tones.length])} />
            {titleCase(b.beat)} <span className="text-fog tabular">{Math.round((b.pct_duration / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DnaCard({bp, sample}: {bp: Blueprint; sample?: boolean}) {
  const h = bp.hook_first_3s ?? {};
  const p = bp.pacing ?? {};
  return (
    <article className="min-w-0 rounded-lg border border-lab-600 bg-lab-850 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Dna aria-hidden className="size-5 text-volt" />
        <h3 className="min-w-0 font-semibold text-bone [overflow-wrap:anywhere]">{bp.style_name}</h3>
        {sample ? <Badge tone="ghost" icon={FlaskConical}>Sample</Badge> : null}
        <span className="ml-auto text-xs text-fog tabular">{bp.aspect_ratio} · ~{bp.target_duration_sec}s</span>
      </div>
      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        <div><dt className="text-xs font-semibold text-fog">Hook says</dt><dd className="text-bone">{h.verbal_pattern || '–'}</dd></div>
        <div><dt className="text-xs font-semibold text-fog">Hook shows</dt><dd className="text-bone">{h.visual_pattern || '–'}</dd></div>
        <div><dt className="text-xs font-semibold text-fog">Pacing</dt><dd className="text-bone tabular">{p.avg_shot_sec ?? '–'}s per shot · {p.words_per_minute ?? '–'} wpm</dd></div>
        <div><dt className="text-xs font-semibold text-fog">Captions · cuts</dt><dd className="text-bone">{titleCase(p.caption_style ?? '–')} · {titleCase(p.transition_style ?? '–')}</dd></div>
      </dl>
      {bp.beat_template?.length ? <div className="mt-3"><BeatStrip beats={bp.beat_template} /></div> : null}
    </article>
  );
}

function IdeaCard({idea, run, sample, onChanged}: {idea: Idea; run?: string; sample?: boolean; onChanged: () => void}) {
  const {act, watch, toast} = useStudio();
  const [edit, setEdit] = useState(false);
  const [f, setF] = useState(idea);
  const [busy, setBusy] = useState<string | null>(null);
  const base = useId();
  const approved = false;
  const save = async () => {
    if (!run) return;
    await api(`/api/ideas/${encodeURIComponent(run)}/${idea.n}`, {method: 'PUT', body: {title: f.title, hook: f.hook, hook_visual: f.hook_visual ?? '', angle: f.angle, case_study: f.case_study}});
  };
  const go = (what: 'approve' | 'edit' | 'schedule') =>
    act(async () => {
      if (!run) return;
      setBusy(what);
      try {
        if (edit) await save();
        const job = await api<Job>(`/api/ideas/${encodeURIComponent(run)}/approve`, {method: 'POST', body: {ideas: [idea.n], render_after: what === 'approve'}});
        watch(job, what === 'approve' ? `Approving “${f.title}” and rendering it` : `Writing the script for “${f.title}”`, async (s) => {
          setBusy(null);
          onChanged();
          if (s !== 'done') return toast('The approval job failed. Studio Activity has the log.', 'err');
          const slug = await slugFromJobLog(job.id).catch(() => null);
          if (what === 'edit' && slug) navigate('create', {project: slug});
          else if (what === 'schedule' && slug) navigate('schedule', {pick: slug});
          else toast('Approved. The render is in Studio Activity.', 'ok');
        });
      } catch (e) {
        setBusy(null);
        throw e;
      }
    });
  const dismiss = () =>
    act(async () => {
      if (!run) return;
      await api(`/api/ideas/${encodeURIComponent(run)}/${idea.n}`, {method: 'PUT', body: {dismissed: !idea.dismissed}});
      onChanged();
    });
  const field = (k: keyof Idea, label: string, multiline = false) => (
    <Field label={label} htmlFor={`${base}-${k}`}>
      {multiline ? (
        <Textarea id={`${base}-${k}`} rows={2} autoGrow value={String(f[k] ?? '')} onChange={(e) => setF({...f, [k]: e.target.value})} />
      ) : (
        <Input id={`${base}-${k}`} value={String(f[k] ?? '')} onChange={(e) => setF({...f, [k]: e.target.value})} />
      )}
    </Field>
  );
  return (
    <article className={cx('flex min-w-0 flex-col rounded-lg border bg-lab-850 p-4 transition-opacity', idea.dismissed ? 'border-lab-700 opacity-55' : 'border-lab-600')}>
      {edit ? (
        <div className="flex flex-col gap-3">
          {field('title', 'Title')}
          {field('hook', 'Opening hook (spoken)')}
          {field('hook_visual', 'Opening hook (on screen)')}
          {field('angle', 'Core concept', true)}
          {field('case_study', 'Case study', true)}
        </div>
      ) : (
        <>
          <div className="flex items-start gap-2">
            <span className="font-display text-2xl leading-none text-pumpkin tabular">{idea.n}</span>
            <h4 className="min-w-0 flex-1 font-semibold leading-snug text-bone [overflow-wrap:anywhere]">{f.title}</h4>
            {sample ? <Badge tone="ghost" icon={FlaskConical}>Sample</Badge> : null}
          </div>
          <blockquote className="mt-3 border-l-0 text-[0.9375rem] text-bone">“{f.hook}”</blockquote>
          {f.hook_visual ? <p className="mt-1 flex items-start gap-1.5 text-sm text-moss"><Eye aria-hidden className="mt-0.5 size-4 shrink-0 text-fog" />{f.hook_visual}</p> : null}
          <p className="mt-3 text-sm text-moss line-clamp-2">{f.angle}</p>
          <p className="mt-1 text-sm text-moss line-clamp-2"><span className="font-semibold text-bone">Case:</span> {f.case_study}</p>
        </>
      )}
      <div className="mt-3 flex flex-wrap gap-1.5">
        <SpecimenTag>{styleInfo(idea.style).name}</SpecimenTag>
        <Badge icon={null}>{idea.aspect_ratio ?? '9:16'}</Badge>
        <Badge icon={null}><span className="tabular">{idea.duration_sec ?? 50}s</span></Badge>
        <Badge icon={null}>{titleCase(idea.music_mood)}</Badge>
      </div>
      <p className="mt-2 text-[0.8125rem] text-fog">Why it works: {idea.why_it_works}</p>
      <div className="mt-auto flex flex-wrap gap-2 pt-4">
        {sample ? (
          <p className="text-[0.8125rem] text-fog">Sample card: brainstorm a topic to get real ones.</p>
        ) : idea.dismissed ? (
          <Button size="sm" variant="ghost" icon={Undo2} onClick={dismiss}>Restore</Button>
        ) : (
          <>
            <Button size="sm" variant="primary" icon={Wand} loading={busy === 'approve'} disabled={approved} onClick={() => go('approve')}>Approve &amp; Generate</Button>
            <Button size="sm" icon={Pencil} loading={busy === 'edit'} onClick={() => (edit ? go('edit') : setEdit(true))}>{edit ? 'Write Script' : 'Edit Script'}</Button>
            <Button size="sm" icon={CalendarClock} loading={busy === 'schedule'} title="Writes the script first, then opens the Schedule Builder" onClick={() => go('schedule')}>Add to Schedule</Button>
            <Button size="sm" variant="ghost" icon={X} onClick={dismiss}>Dismiss</Button>
          </>
        )}
      </div>
    </article>
  );
}

function RunPanel({r, onChanged}: {r: Run; onChanged: () => void}) {
  const {act, watch} = useStudio();
  const title = r.mode === 'brainstorm' ? `Brainstorm: ${r.topic}` : r.blueprint?.style_name || r.run;
  const regen = () => act(async () => watch(await api<Job>(`/api/ideas/${encodeURIComponent(r.run)}/propose`, {method: 'POST', body: {topic: r.topic}}), 'Generating fresh ideas', onChanged));
  return (
    <Panel id={`run-${r.run}`} title={<span className="[overflow-wrap:anywhere]">{title}</span>} description={r.sources.length ? `${r.sources.length} reference video${r.sources.length === 1 ? '' : 's'}` : 'Topic brainstorm'} action={<Button size="sm" icon={RefreshCw} onClick={regen}>{r.ideas.length ? 'Regenerate' : 'Generate 5 Ideas'}</Button>}>
      {r.sheets.length ? (
        <div className="mb-4 flex gap-2 overflow-x-auto pb-2" tabIndex={0} aria-label="Contact sheets">
          {r.sheets.map((s) => <img key={s} src={fileUrl(s)} alt="Contact sheet frame grid" width={160} height={284} loading="lazy" className="h-36 w-auto shrink-0 rounded-md border border-lab-600 object-cover" />)}
        </div>
      ) : null}
      {r.blueprint?.style_name && r.mode !== 'brainstorm' ? <div className="mb-4"><DnaCard bp={r.blueprint} /></div> : null}
      {r.ideas.length ? (
        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">{r.ideas.map((i) => <IdeaCard key={`${r.run}-${i.n}`} idea={i} run={r.run} onChanged={onChanged} />)}</div>
      ) : (
        <p className="text-sm text-moss">No pitches yet. Generate five.</p>
      )}
      {r.projects.length ? (
        <p className="mt-4 text-sm text-moss">
          Became projects:{' '}
          {r.projects.map((p, i) => {
            const slug = p.split('/').pop() ?? p;
            return <span key={p}>{i ? ', ' : ''}<a className="text-pumpkin underline underline-offset-4" href={href('create', {project: slug})}>{slug}</a></span>;
          })}
        </p>
      ) : null}
    </Panel>
  );
}

export default function Ideas() {
  const {act, watch, demo} = useStudio();
  const runs = useApi<Run[]>('/api/ideas');
  const bps = useApi<BlueprintRow[]>('/api/blueprints');
  const onboarding = useApi<Onboarding>('/api/onboarding');
  const analytics = useApi<{top: {title: string; views: number}[]}>('/api/analytics');
  const [mode, setMode] = useState<'brainstorm' | 'reference'>('brainstorm');
  const [topic, setTopic] = useState('');
  const [bp, setBp] = useState('');
  const [urls, setUrls] = useState('');
  const [name, setName] = useState('');
  const [depth, setDepth] = useState<'fast' | 'detailed'>('detailed');
  const [hint, setHint] = useState('');
  const [large, setLarge] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const ids = {topic: useId(), bp: useId(), urls: useId(), name: useId(), hint: useId()};
  const reload = () => void runs.reload();

  const brainstorm = () =>
    act(async () => {
      setErr(null);
      if (!topic.trim()) return setErr('Type a topic or niche to brainstorm from.');
      watch(await api<Job>('/api/ideas/brainstorm', {method: 'POST', body: {topic: topic.trim(), blueprint: bp}}), 'Brainstorming 5 ideas', reload);
    });
  const analyze = () =>
    act(async () => {
      setErr(null);
      const list = urls.split(/\s+/).filter(Boolean);
      if (!list.length) return setErr('Paste at least one link, one per line.');
      watch(await api<Job>('/api/analyze', {method: 'POST', body: {urls: list, style: name.trim() || 'my_style', depth, topic: hint, confirm_large: large}}), 'Reading the reference DNA', () => { reload(); void bps.reload(); });
    });

  const sampleBp = onboarding.data?.demo.blueprint;
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel id="idea-source" title="Find the next video" description="Topics and case studies already in your Library are never proposed again.">
          <div className="flex flex-col gap-4">
            <Segmented label="Idea source" value={mode} onChange={(v) => { setMode(v); setErr(null); }} options={[{value: 'brainstorm', label: 'Brainstorm from Topic', hint: 'or niche', icon: Sparkles}, {value: 'reference', label: 'Learn from References', hint: 'extract Style DNA', icon: Dna}]} />
            {mode === 'brainstorm' ? (
              <>
                <Field label="Topic or niche" htmlFor={ids.topic} error={err ?? undefined}>
                  <Input id={ids.topic} name="topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. companies that nearly went bankrupt…" />
                </Field>
                <Field label="Copy the style of a saved blueprint" htmlFor={ids.bp} optional>
                  <Select id={ids.bp} value={bp} onChange={(e) => setBp(e.target.value)}>
                    <option value="">No blueprint (use the style’s own beats)</option>
                    {(bps.data ?? []).map((b) => <option key={b.name} value={b.name}>{b.name}</option>)}
                  </Select>
                </Field>
                <div><Button variant="primary" icon={Sparkles} onClick={brainstorm}>Brainstorm 5 Ideas</Button></div>
              </>
            ) : (
              <>
                <Field label="Reference links" htmlFor={ids.urls} error={err ?? undefined} hint="YouTube, Shorts, Reels or TikTok. One per line. Nothing renders until you approve an idea.">
                  <Textarea id={ids.urls} name="urls" rows={3} spellCheck={false} value={urls} onChange={(e) => setUrls(e.target.value)} placeholder="https://www.youtube.com/shorts/…" />
                </Field>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Blueprint name" htmlFor={ids.name} hint="Saved as a reusable Style DNA.">
                    <Input id={ids.name} value={name} spellCheck={false} onChange={(e) => setName(e.target.value)} placeholder="my_style" />
                  </Field>
                  <Field label="Topic hint" htmlFor={ids.hint} optional>
                    <Input id={ids.hint} value={hint} onChange={(e) => setHint(e.target.value)} placeholder="e.g. personal finance…" />
                  </Field>
                </div>
                <Segmented label="Analysis depth" value={depth} onChange={setDepth} options={[{value: 'fast', label: 'Fast', hint: 'first 20 seconds'}, {value: 'detailed', label: 'Detailed', hint: 'whole video'}]} />
                <Check label="Allow long videos" hint="Over 15 contact sheets; slower and uses more of the free quota." checked={large} onChange={setLarge} />
                <div><Button variant="primary" icon={Link2} onClick={analyze}>Analyze &amp; Propose Ideas</Button></div>
              </>
            )}
          </div>
        </Panel>
        <Panel id="dna" title="Saved Style DNA" description="Blueprints measured from reference videos.">
          {bps.loading && !bps.data ? <Skeleton className="h-24" /> : bps.data?.length ? (
            <ul className="flex flex-col gap-2">
              {bps.data.map((b) => (
                <li key={b.name} className="flex min-w-0 items-center gap-3 rounded-md border border-lab-700 bg-lab-850 p-2.5">
                  <Dna aria-hidden className="size-5 shrink-0 text-volt" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-bone" title={b.name}>{b.name}</span>
                    <span className="block text-xs text-fog tabular">{b.aspect_ratio} · ~{b.target_duration_sec}s{b.created ? ` · ${b.created}` : ''}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-moss">None yet. Analyze a reference video to grow one.</p>
          )}
          <p className="mt-4 text-[0.8125rem] text-fog">
            {analytics.data?.top.length ? <>Top hooks so far feed every new brainstorm: {analytics.data.top.map((t) => `${t.title} (${t.views})`).join(' · ')}.</> : <>Paste published links in the <a className="text-pumpkin underline underline-offset-4" href={href('library')}>Library</a> and sync analytics so the best hooks feed new ideas.</>}
          </p>
        </Panel>
      </div>

      {demo && sampleBp ? (
        <Panel id="demo-ideas" title="Sample Style DNA and pitches" description="Judge Demo Mode: an illustrative blueprint and three hand-written sample pitches. Nothing here was generated.">
          <DnaCard bp={sampleBp} sample />
          <div className="mt-4 grid gap-3 md:grid-cols-2 2xl:grid-cols-3">{SAMPLE_IDEAS.map((i) => <IdeaCard key={i.n} idea={i} sample onChanged={() => undefined} />)}</div>
        </Panel>
      ) : null}

      {runs.loading && !runs.data ? (
        <Skeleton className="h-48" />
      ) : runs.error ? (
        <Notice tone="blood" title={runs.error.message}>{runs.error.hint}</Notice>
      ) : runs.data?.length ? (
        runs.data.map((r) => <RunPanel key={r.run} r={r} onChanged={reload} />)
      ) : !demo ? (
        <EmptyState art={<FlaskConical aria-hidden className="size-9 text-volt" />} title="No experiments yet" action={<Button variant="secondary" icon={Sparkles} onClick={() => document.getElementById(ids.topic)?.focus()}>Brainstorm a Topic</Button>}>
          Brainstorm a topic or feed the lab a reference video. Pitches land here as cards you can edit, approve or dismiss.
        </EmptyState>
      ) : null}
    </div>
  );
}
