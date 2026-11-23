import {ArrowDown, ArrowUp, Check, ChevronDown, Clapperboard, FileText, FlaskConical, Plus, Save, ScrollText, Sparkles, Trash, Wand} from 'lucide-react';
import {useEffect, useId, useMemo, useState} from 'react';
import {api, type Job, type Onboarding, type Options, type ProjectRow, type Script} from '../lib/api';
import {platformName, titleCase} from '../lib/format';
import {href, navigate, useApi, useRoute} from '../lib/hooks';
import {slugFromJobLog, useStudio} from '../lib/studio';
import {STYLE_INFO, styleImage, styleInfo} from '../lib/styles';
import {Badge, Button, Check as CheckBox, EmptyState, Field, Input, LinkButton, Notice, Panel, Segmented, Select, Skeleton, SpecimenTag, Textarea, cx} from '../components/ui';

function StyleCard({id, selected, onPick, beats, name}: {id: string; selected: boolean; onPick: () => void; beats?: string; name: string}) {
  const info = styleInfo(id);
  return (
    <label className={cx('group relative flex min-w-0 cursor-pointer flex-col overflow-hidden rounded-lg border bg-lab-850 transition-[border-color,box-shadow,transform] duration-200 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pumpkin', selected ? 'border-pumpkin shadow-[0_0_0_1px_var(--color-pumpkin),0_10px_30px_-12px_rgb(255_166_77/0.55)]' : 'border-lab-600 hover:-translate-y-0.5 hover:border-lab-400')}>
      <input type="radio" name={name} value={id} checked={selected} onChange={onPick} className="sr-only" />
      <div className="relative aspect-[4/5] overflow-hidden bg-lab-950">
        <img src={styleImage(id)} alt="" width={270} height={480} loading="lazy" className="absolute inset-0 size-full object-cover object-top transition-transform duration-300 group-hover:scale-[1.03]" />
        <SpecimenTag className="absolute bottom-2 left-2 max-w-[calc(100%-1rem)] -rotate-2 bg-lab-900/90 shadow-[var(--shadow-lift)]">{info.engine}</SpecimenTag>
        {selected ? (
          <span className="absolute top-2 right-2 grid size-7 place-items-center rounded-full bg-pumpkin text-pumpkin-ink">
            <Check aria-hidden className="size-4" />
          </span>
        ) : null}
      </div>
      <div className="flex flex-1 flex-col gap-1.5 p-3">
        <span className="font-semibold leading-tight text-bone [overflow-wrap:anywhere]">{info.name}</span>
        <span className="text-[0.8125rem] leading-snug text-moss">{info.blurb}</span>
        {beats ? <span title={beats} className="mt-auto pt-1 text-xs leading-snug text-fog line-clamp-2">{beats}</span> : null}
      </div>
    </label>
  );
}

function StylePicker({styles, value, onChange, templates}: {styles: string[]; value: string; onChange: (s: string) => void; templates: Options['templates']}) {
  const name = useId();
  const featured = styles.filter((s) => STYLE_INFO[s]?.featured);
  const rest = styles.filter((s) => !STYLE_INFO[s]?.featured);
  const [more, setMore] = useState(!featured.includes(value));
  const beatsOf = (s: string) => templates[s]?.beats.map((b) => b.label || b.id).join(' → ');
  return (
    <fieldset className="min-w-0">
      <legend className="mb-2 text-sm font-semibold text-bone">Style</legend>
      <div role="radiogroup" aria-label="Video style" className="grid grid-cols-2 gap-3 @lg:grid-cols-3 @5xl:grid-cols-6">
        {featured.map((s) => <StyleCard key={s} id={s} name={name} selected={value === s} onPick={() => onChange(s)} beats={beatsOf(s)} />)}
      </div>
      <button type="button" aria-expanded={more} onClick={() => setMore(!more)} className="mt-3 flex min-h-10 items-center gap-1.5 text-sm font-semibold text-moss hover:text-bone">
        <ChevronDown aria-hidden className={cx('size-4 transition-transform', more && 'rotate-180')} />
        {more ? 'Fewer styles' : `${rest.length} more styles and engines`}
      </button>
      {more ? (
        <div role="radiogroup" aria-label="More styles" className="mt-2 grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-2">
          {rest.map((s) => {
            const info = styleInfo(s);
            const on = value === s;
            return (
              <label key={s} className={cx('flex min-h-14 min-w-0 cursor-pointer items-center gap-3 rounded-md border p-2 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-pumpkin', on ? 'border-pumpkin bg-lab-800' : 'border-lab-600 bg-lab-850 hover:border-lab-400')}>
                <input type="radio" name={name} value={s} checked={on} onChange={() => onChange(s)} className="sr-only" />
                <img src={styleImage(s)} alt="" width={40} height={50} loading="lazy" className="h-12 w-10 shrink-0 rounded-sm bg-lab-950 object-cover object-top p-0.5 ring-1 ring-lab-500" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-bone">{info.name}</span>
                  <span className="block truncate text-xs text-fog">{info.engine}</span>
                </span>
                {on ? <Check aria-hidden className="size-4 shrink-0 text-pumpkin" /> : null}
              </label>
            );
          })}
        </div>
      ) : null}
    </fieldset>
  );
}

// ------------------------------------------------------------------ new video form
function NewVideo({opts, onWritten}: {opts: Options; onWritten: (slug: string) => void}) {
  const {act, watch, toast, demo} = useStudio();
  const onboarding = useApi<Onboarding>('/api/onboarding');
  const d = opts.defaults;
  const [mode, setMode] = useState<'idea' | 'script'>('idea');
  const [prompt, setPrompt] = useState('');
  const [scriptText, setScriptText] = useState('');
  const [title, setTitle] = useState('');
  const [style, setStyle] = useState(String(d.style ?? 'concept_explainer'));
  const [aspect, setAspect] = useState(String(d.aspect_ratio ?? '9:16'));
  const [mood, setMood] = useState(String(d.music_mood ?? 'documentary'));
  const [duration, setDuration] = useState(Number(d.target_duration_sec ?? 50));
  const [platforms, setPlatforms] = useState<string[]>(['youtube']);
  const [ground, setGround] = useState(opts.grounding !== false);
  const [overwrite, setOverwrite] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const ids = {prompt: useId(), script: useId(), title: useId(), aspect: useId(), mood: useId(), duration: useId()};
  const forced = opts.templates[style]?.family === 'long_form' ? '16:9' : null;
  useEffect(() => {
    if (forced) setAspect(forced);
  }, [forced]);
  const keyMissing = onboarding.data ? !onboarding.data.key_set : false;
  const words = scriptText.trim() ? scriptText.trim().split(/\s+/).length : 0;

  const write = () =>
    act(async () => {
      setErr(null);
      if (mode === 'idea' && !prompt.trim()) return setErr('Describe what the video should explain.');
      if (mode === 'script' && words < 8) return setErr('Paste a script of at least a couple of sentences.');
      setBusy(true);
      try {
        const body = {mode, title: title.trim(), style, aspect, mood, duration, platforms, overwrite, grounding: ground, ...(mode === 'idea' ? {prompt: prompt.trim()} : {script: scriptText.trim()})};
        const job = await api<Job>('/api/projects/write', {method: 'POST', body});
        watch(job, mode === 'script' ? 'Splitting your script' : 'Writing the script', async (s) => {
          setBusy(false);
          if (s !== 'done') return toast('Script writing failed. Open Studio Activity for the log.', 'err');
          const slug = await slugFromJobLog(job.id).catch(() => null);
          toast('Script stitched together. Review the scenes, then render.', 'ok');
          if (slug) onWritten(slug);
        });
      } catch (e) {
        setBusy(false);
        throw e;
      }
    });
  const renderSample = () =>
    act(async () => {
      const slug = onboarding.data?.demo.sample_project ?? 'concept-001';
      const job = await api<Job>(`/api/projects/${slug}/render`, {method: 'POST', body: {no_llm: true}});
      watch(job, 'Rendering the sample (no key needed)', (s) => toast(s === 'done' ? 'It’s alive! The sample is in the Library.' : 'The sample render failed. See Studio Activity.', s === 'done' ? 'ok' : 'err'));
    });

  return (
    <Panel id="new-video" title="Stitch a new video" description="Pick how the words arrive, choose a look, and the lab does the rest.">
      <div className="flex flex-col gap-5">
        <Segmented
          label="Input mode"
          value={mode}
          onChange={(v) => { setMode(v); setErr(null); }}
          options={[
            {value: 'idea', label: 'From Idea', hint: 'AI writes the script', icon: Sparkles},
            {value: 'script', label: 'From Script', hint: 'Keep my exact words', icon: ScrollText},
          ]}
        />
        {mode === 'idea' ? (
          <Field label="What should the video explain?" htmlFor={ids.prompt} error={err ?? undefined} hint="One sentence is enough. The style decides the beats.">
            <Textarea id={ids.prompt} name="prompt" rows={3} autoGrow value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="e.g. Why Costco sells hot dogs for $1.50 and still makes money…" />
          </Field>
        ) : (
          <Field label="Your script" htmlFor={ids.script} error={err ?? undefined} hint={<><span className="tabular">{words}</span> words. Used word for word for the voice; only split into scenes. A blank line starts a new scene.</>}>
            <Textarea id={ids.script} name="script" rows={7} autoGrow value={scriptText} onChange={(e) => setScriptText(e.target.value)} placeholder="Paste the full narration…" />
          </Field>
        )}
        <StylePicker styles={opts.styles} value={style} onChange={setStyle} templates={opts.templates} />
        <div className="grid gap-4 @lg:grid-cols-2 @4xl:grid-cols-4">
          <Field label="Video title" htmlFor={ids.title} optional hint="Becomes the folder name." className="@lg:col-span-2 @4xl:col-span-1">
            <Input id={ids.title} name="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="AI suggests one…" />
          </Field>
          <Field label="Aspect" htmlFor={ids.aspect} hint={forced ? 'Long-form is always 16:9.' : undefined}>
            <Select id={ids.aspect} value={aspect} disabled={Boolean(forced)} onChange={(e) => setAspect(e.target.value)}>
              {opts.aspects.map((a) => <option key={a} value={a}>{a === '9:16' ? '9:16 Shorts' : a === '16:9' ? '16:9 Wide' : '1:1 Square'}</option>)}
            </Select>
          </Field>
          <Field label="Music mood" htmlFor={ids.mood}>
            <Select id={ids.mood} value={mood} onChange={(e) => setMood(e.target.value)}>
              {opts.moods.map((m) => <option key={m} value={m}>{titleCase(m)}</option>)}
            </Select>
          </Field>
          {mode === 'idea' ? (
            <Field label="Length (seconds)" htmlFor={ids.duration}>
              <Input id={ids.duration} type="number" inputMode="numeric" min={15} max={1800} value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
            </Field>
          ) : null}
        </div>
        <fieldset>
          <legend className="mb-1 text-sm font-semibold text-bone">Platforms</legend>
          <div className="flex flex-wrap gap-x-4">
            {opts.platforms.map((p) => (
              <CheckBox key={p} label={platformName(p)} checked={platforms.includes(p)} onChange={(v) => setPlatforms(v ? [...platforms, p] : platforms.filter((x) => x !== p))} />
            ))}
          </div>
        </fieldset>
        <details className="group rounded-md border border-lab-700 px-3">
          <summary className="flex min-h-11 list-none items-center gap-2 text-sm font-semibold text-moss hover:text-bone [&::-webkit-details-marker]:hidden">
            <ChevronDown aria-hidden className="size-4 transition-transform group-open:rotate-180" />
            Advanced
          </summary>
          <div className="pb-2">
            <CheckBox label="Check facts with Google Search" hint="Paid Gemini only. On the free tier, numbers are marked unverified and the Safe-Publish Gate holds the upload." checked={ground} onChange={setGround} />
            <CheckBox label="Replace a project with the same folder name" hint="Overwrites that project’s script.json." checked={overwrite} onChange={setOverwrite} />
          </div>
        </details>
        {keyMissing ? (
          <Notice tone="candle" title="No brain connected yet" action={<div className="flex flex-wrap gap-2"><LinkButton size="sm" href={href('settings', {section: 'model'})}>Add Gemini key</LinkButton><Button size="sm" variant="secondary" icon={FlaskConical} onClick={renderSample}>Render the sample (no key)</Button></div>}>
            Writing a script needs a language model. {demo ? 'In Judge Demo Mode you can render the bundled sample project instead.' : 'Add a free Gemini key, or render the bundled sample project without one.'}
          </Notice>
        ) : null}
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary" icon={Wand} loading={busy} disabled={keyMissing} onClick={write}>{mode === 'script' ? 'Split Into Scenes' : 'Write Script'}</Button>
          <span className="text-[0.8125rem] text-fog">{keyMissing ? 'Disabled: add a Gemini key first.' : 'Takes about 20 seconds. Rendering is a separate step.'}</span>
        </div>
      </div>
    </Panel>
  );
}

// ------------------------------------------------------------------ projects list
function Projects({rows, loading, current}: {rows: ProjectRow[] | null; loading: boolean; current: string}) {
  return (
    <Panel id="projects" title="Projects" description="Scripts on the slab, newest first.">
      {loading && !rows ? (
        <div className="flex flex-col gap-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : rows && rows.length ? (
        <ul className="flex flex-col gap-2">
          {rows.map((p) => (
            <li key={p.slug}>
              <a href={href('create', {project: p.slug})} aria-current={current === p.slug ? 'true' : undefined} className={cx('flex min-w-0 items-center gap-3 rounded-md border p-2.5 transition-colors', current === p.slug ? 'border-pumpkin bg-lab-800' : 'border-lab-700 bg-lab-850 hover:border-lab-500')}>
                <img src={styleImage(p.style)} alt="" width={36} height={48} loading="lazy" className="h-12 w-9 shrink-0 rounded-sm bg-lab-950 object-cover object-top p-0.5 ring-1 ring-lab-500" />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold leading-snug text-bone [overflow-wrap:anywhere]">{p.title || p.slug}</span>
                  <span className="block text-xs text-fog">{[styleInfo(p.style).name, p.aspect_ratio, `${p.scenes} scenes`].filter(Boolean).join(' · ')}</span>
                  {p.needs_approval ? <Badge tone="candle" className="mt-1.5">Approve idea first</Badge> : p.rendered ? <Badge tone="volt" className="mt-1.5">Rendered</Badge> : null}
                </span>
              </a>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState art={<FileText aria-hidden className="size-8 text-fog" />} title="The slab is empty">
          Write your first script on the left, or brainstorm one in Ideas.
        </EmptyState>
      )}
    </Panel>
  );
}

// ------------------------------------------------------------------ scene editor
function Editor({slug, opts, onSaved}: {slug: string; opts: Options; onSaved: () => void}) {
  const {act, watch, toast} = useStudio();
  const [script, setScript] = useState<Script | null>(null);
  const [dirty, setDirty] = useState(false);
  const [safe, setSafe] = useState(false);
  const [strict, setStrict] = useState(false);
  const [busy, setBusy] = useState(false);
  const [json, setJson] = useState('');
  const [jsonErr, setJsonErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void act(async () => {
      const s = await api<Script>(`/api/projects/${encodeURIComponent(slug)}`);
      if (live) {
        setScript(s);
        setDirty(false);
        setJson(JSON.stringify(s, null, 2));
      }
    });
    return () => {
      live = false;
    };
  }, [slug, act]);
  useEffect(() => {
    if (!dirty) return;
    const on = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener('beforeunload', on);
    return () => window.removeEventListener('beforeunload', on);
  }, [dirty]);

  const update = (next: Script) => {
    setScript(next);
    setJson(JSON.stringify(next, null, 2));
    setDirty(true);
  };
  const scenes = script?.scenes ?? [];
  const setScene = (i: number, patch: Partial<Script['scenes'][number]>, visual?: Record<string, unknown>) => {
    if (!script) return;
    const copy = scenes.map((s, j) => (j === i ? {...s, ...patch, visual: visual ? {...(s.visual ?? {}), ...visual} : s.visual} : s));
    update({...script, scenes: copy});
  };
  const move = (i: number, j: number) => {
    if (!script || j < 0 || j >= scenes.length) return;
    const copy = [...scenes];
    [copy[i], copy[j]] = [copy[j], copy[i]];
    update({...script, scenes: copy});
  };
  const save = async () => {
    if (!script) return;
    const empty = scenes.findIndex((s) => !String(s.narration ?? '').trim());
    if (empty >= 0) throw new Error(`Scene ${empty + 1} has no narration. Write it or delete the scene.`);
    await api(`/api/projects/${encodeURIComponent(slug)}`, {method: 'PUT', body: script});
    setDirty(false);
    onSaved();
  };
  const render = () =>
    act(async () => {
      setBusy(true);
      try {
        await save();
        const job = await api<Job>(`/api/projects/${encodeURIComponent(slug)}/render`, {method: 'POST', body: {safe_zones: safe, strict_qa: strict}});
        watch(job, `Rendering ${script?.title ?? slug}`, (s) => {
          setBusy(false);
          if (s === 'done') {
            toast('It’s alive! Your video is in the Library.', 'ok');
            navigate('library', {item: slug});
          } else toast('The render failed. Studio Activity has the log.', 'err');
        });
      } catch (e) {
        setBusy(false);
        throw e;
      }
    });

  if (!script) return <Skeleton className="h-64" />;
  const claims = script.claims ?? [];
  const facts = claims.length ? claims.filter((c) => !c.verified).map((c) => c.text) : script.facts_to_verify ?? [];
  return (
    <Panel
      id="editor"
      title={<span className="[overflow-wrap:anywhere]">{script.title || slug}</span>}
      description={<>{styleInfo(String(script.style ?? '')).name} · {script.aspect_ratio} · {scenes.length} scenes {dirty ? <Badge tone="candle" className="ml-1">Unsaved</Badge> : null}</>}
      action={
        <div className="flex flex-wrap gap-2">
          <Button icon={Save} disabled={!dirty} onClick={() => act(async () => { await save(); toast('Saved.', 'ok'); })}>Save</Button>
          <Button variant="primary" icon={Clapperboard} loading={busy} onClick={render}>Render</Button>
        </div>
      }
    >
      {facts.length ? (
        <div className="mb-4">
          <Notice tone="candle" title={`${facts.length} unverified fact${facts.length === 1 ? '' : 's'}`}>
            <p>{script.grounded ? 'Checked against web sources; these still need you.' : 'Not web-checked (free tier).'} The Safe-Publish Gate holds uploads until you approve them.</p>
            <ul className="mt-1 list-disc pl-5">{facts.slice(0, 6).map((f) => <li key={f}>{f}</li>)}</ul>
          </Notice>
        </div>
      ) : null}
      {script.sources?.length ? (
        <p className="mb-4 text-sm text-moss">
          Sources:{' '}
          {script.sources.map((s, i) => (
            <span key={s.url}>
              {i ? ' · ' : ''}
              <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-pumpkin underline underline-offset-4">{s.title}</a>
            </span>
          ))}
        </p>
      ) : null}
      <ol className="flex flex-col gap-3">
        {scenes.map((s, i) => (
          <li key={i} className="rounded-md border border-lab-700 bg-lab-850 p-3">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="font-display text-xl leading-none text-pumpkin tabular">{String(i + 1).padStart(2, '0')}</span>
              {s.beat ? <SpecimenTag>{s.beat}</SpecimenTag> : null}
              <label className="sr-only" htmlFor={`vt-${i}`}>Scene {i + 1} visual type</label>
              <Select id={`vt-${i}`} value={String(s.visual?.type ?? 'headline')} onChange={(e) => setScene(i, {}, {type: e.target.value})} className="!h-8 w-auto text-sm">
                {opts.visual_types.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}
              </Select>
              <span className="ml-auto flex gap-1">
                <Button size="sm" variant="ghost" icon={ArrowUp} aria-label={`Move scene ${i + 1} up`} disabled={i === 0} onClick={() => move(i, i - 1)} />
                <Button size="sm" variant="ghost" icon={ArrowDown} aria-label={`Move scene ${i + 1} down`} disabled={i === scenes.length - 1} onClick={() => move(i, i + 1)} />
                <Button size="sm" variant="ghost" icon={Trash} aria-label={`Delete scene ${i + 1}`} disabled={scenes.length <= 1} onClick={() => script && update({...script, scenes: scenes.filter((_, j) => j !== i)})} />
              </span>
            </div>
            <label className="sr-only" htmlFor={`nar-${i}`}>Scene {i + 1} narration</label>
            <Textarea id={`nar-${i}`} autoGrow rows={2} value={String(s.narration ?? '')} onChange={(e) => setScene(i, {narration: e.target.value})} placeholder="What the voice says…" />
            <label className="mt-2 block text-xs font-semibold text-moss" htmlFor={`hd-${i}`}>On-screen heading</label>
            <Input id={`hd-${i}`} className="mt-1" value={String(s.visual?.heading ?? '')} onChange={(e) => setScene(i, {}, {heading: e.target.value})} placeholder="Short headline…" />
          </li>
        ))}
      </ol>
      <div className="mt-3 flex flex-wrap items-center gap-x-4">
        <Button icon={Plus} onClick={() => update({...script, scenes: [...scenes, {beat: 'other', narration: '', visual: {type: 'headline', heading: ''}}]})}>Add Scene</Button>
        <CheckBox label="Draw safe-zone overlay" checked={safe} onChange={setSafe} />
        <CheckBox label="Stop if visual QA fails" checked={strict} onChange={setStrict} />
      </div>
      <details className="group mt-4 rounded-md border border-lab-700 px-3">
        <summary className="flex min-h-11 list-none items-center gap-2 text-sm font-semibold text-moss hover:text-bone [&::-webkit-details-marker]:hidden">
          <ChevronDown aria-hidden className="size-4 transition-transform group-open:rotate-180" />
          Raw script.json
        </summary>
        <label className="sr-only" htmlFor="raw-json">Raw script JSON</label>
        <Textarea
          id="raw-json"
          rows={14}
          spellCheck={false}
          className="mb-3 font-mono text-xs"
          value={json}
          onChange={(e) => {
            setJson(e.target.value);
            try {
              setScript(JSON.parse(e.target.value) as Script);
              setDirty(true);
              setJsonErr(null);
            } catch {
              setJsonErr('Not valid JSON yet; keep typing.');
            }
          }}
        />
        {jsonErr ? <p className="mb-3 text-sm text-candle">{jsonErr}</p> : null}
      </details>
    </Panel>
  );
}

export default function Create() {
  const route = useRoute();
  const opts = useApi<Options>('/api/options');
  const projects = useApi<ProjectRow[]>('/api/projects');
  const current = route.params.get('project') ?? '';
  const sorted = useMemo(() => projects.data ?? null, [projects.data]);
  if (opts.error) return <Notice tone="blood" title={opts.error.message}>{opts.error.hint}</Notice>;
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        {opts.data ? <NewVideo opts={opts.data} onWritten={(slug) => { void projects.reload(); navigate('create', {project: slug}); }} /> : <Skeleton className="h-[560px]" />}
        <Projects rows={sorted} loading={projects.loading} current={current} />
      </div>
      {current && opts.data ? <Editor key={current} slug={current} opts={opts.data} onSaved={() => void projects.reload()} /> : null}
    </div>
  );
}
