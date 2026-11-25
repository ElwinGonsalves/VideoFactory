import {Check, ChevronDown, FlaskConical, ScrollText, Sparkles, Wand} from 'lucide-react';
import {useEffect, useId, useState} from 'react';
import {AUTO_VOICE, GhostVoice, LengthPicker, NarratorFields} from '../components/Narrator';
import {Shelf} from '../components/Shelf';
import {Button, Check as CheckBox, Field, Input, LinkButton, Notice, Panel, Segmented, Select, Skeleton, SpecimenTag, Textarea, cx} from '../components/ui';
import {api, type Job, type Onboarding, type Options, type ProjectRow} from '../lib/api';
import {platformName, titleCase} from '../lib/format';
import {href, navigate, useApi} from '../lib/hooks';
import {slugFromJobLog, useStudio} from '../lib/studio';
import {FAMILIES, STYLE_INFO, styleImage, styleInfo, type StyleFamily} from '../lib/styles';

function StyleCard({id, selected, onPick, beats, name, line, voice, language}: {id: string; selected: boolean; onPick: () => void; beats?: string; name: string; line: string; voice: string; language: string}) {
  const info = styleInfo(id);
  return (
    <div className="relative min-w-0">
    <label className={cx('group relative flex h-full min-w-0 cursor-pointer flex-col overflow-hidden rounded-lg border bg-lab-850 transition-[border-color,box-shadow,transform] duration-200 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pumpkin', selected ? 'border-pumpkin shadow-[0_0_0_1px_var(--color-pumpkin),0_10px_30px_-12px_rgb(255_166_77/0.55)]' : 'border-lab-600 hover:-translate-y-0.5 hover:border-lab-400')}>
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
        {info.bestFor ? <span className="text-xs font-semibold text-pumpkin">Best for: {info.bestFor}</span> : null}
        <span className="text-[0.8125rem] leading-snug text-moss">{info.blurb}</span>
        {beats ? <span title={beats} className="mt-auto pt-1 text-xs leading-snug text-fog line-clamp-2">{beats}</span> : null}
      </div>
    </label>
    <GhostVoice style={id} language={language} voice={voice} line={line} className="absolute top-2 left-2" />
    </div>
  );
}

function StylePicker({styles, value, onChange, templates, line, voice, language}: {styles: string[]; value: string; onChange: (s: string) => void; templates: Options['templates']; line: string; voice: string; language: string}) {
  const name = useId();
  const beatsOf = (s: string) => templates[s]?.beats.map((b) => b.label || b.id).join(' → ');
  // one shelf per family, so look-alike styles sit side by side and their differences are obvious
  const [tab, setTab] = useState<StyleFamily>(styleInfo(value).family);
  useEffect(() => setTab(styleInfo(value).family), [value]);
  const order = Object.keys(STYLE_INFO);
  const rank = (s: string) => (order.indexOf(s) < 0 ? 999 : order.indexOf(s));
  const inTab = styles.filter((s) => styleInfo(s).family === tab).sort((a, b) => rank(a) - rank(b)); // curated order, not A-Z
  const fam = FAMILIES.find((f) => f.id === tab)!;
  return (
    <fieldset className="min-w-0">
      <legend className="mb-2 flex w-full flex-wrap items-baseline justify-between gap-2 text-sm font-semibold text-bone">
        <span>Style</span>
        <span className="text-xs font-normal text-fog">Picked: <b className="text-pumpkin">{styleInfo(value).name}</b> · {styleInfo(value).bestFor}</span>
      </legend>
      <div role="tablist" aria-label="Style families" className="mb-3 flex gap-1 overflow-x-auto rounded-lg border border-lab-600 bg-lab-950 p-1">
        {FAMILIES.map((f) => {
          const count = styles.filter((s) => styleInfo(s).family === f.id).length;
          const has = styleInfo(value).family === f.id;
          return (
            <button key={f.id} type="button" role="tab" aria-selected={tab === f.id} onClick={() => setTab(f.id)}
              className={cx('flex min-h-11 shrink-0 items-center gap-1.5 rounded-md px-3 text-sm font-semibold whitespace-nowrap transition-colors', tab === f.id ? 'bg-lab-700 text-bone shadow-[inset_0_0_0_1px_var(--color-lab-400)]' : 'text-moss hover:text-bone')}>
              {f.label}
              <span className="text-xs font-normal text-fog tabular">{count}</span>
              {has ? <span aria-label="(current style)" className="size-1.5 rounded-full bg-pumpkin" /> : null}
            </button>
          );
        })}
      </div>
      <p className="mb-2 text-xs text-fog">{fam.hint}</p>
      {tab !== 'engine' ? (
        <div role="radiogroup" aria-label={`${fam.label} styles`} className="grid grid-cols-2 gap-3 @2xl:grid-cols-4">
          {inTab.map((s) => <StyleCard key={s} id={s} name={name} selected={value === s} onPick={() => onChange(s)} beats={beatsOf(s)} line={line} voice={voice} language={language} />)}
        </div>
      ) : (
        <div role="radiogroup" aria-label="Specialist engines" className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-2">
          {inTab.map((s) => {
            const info = styleInfo(s);
            const on = value === s;
            return (
              <label key={s} className={cx('flex min-h-16 min-w-0 cursor-pointer items-center gap-3 rounded-md border p-2 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-pumpkin', on ? 'border-pumpkin bg-lab-800' : 'border-lab-600 bg-lab-850 hover:border-lab-400')}>
                <input type="radio" name={name} value={s} checked={on} onChange={() => onChange(s)} className="sr-only" />
                <img src={styleImage(s)} alt="" width={40} height={50} loading="lazy" className="h-12 w-10 shrink-0 rounded-sm bg-lab-950 object-cover object-top p-0.5 ring-1 ring-lab-500" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-bone">{info.name}</span>
                  <span className="block truncate text-xs text-moss">{info.bestFor}</span>
                  <span className="block truncate text-xs text-fog">{info.engine}</span>
                </span>
                {on ? <Check aria-hidden className="size-4 shrink-0 text-pumpkin" /> : null}
              </label>
            );
          })}
        </div>
      )}
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
  const [language, setLanguage] = useState(String(d.language ?? 'english').toLowerCase() in {english: 1, hinglish: 1, hindi: 1} ? String(d.language ?? 'english').toLowerCase() : 'english');
  const [voice, setVoice] = useState(AUTO_VOICE);
  const [ground, setGround] = useState(opts.grounding !== false);
  const [overwrite, setOverwrite] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const ids = {prompt: useId(), script: useId(), title: useId(), aspect: useId(), mood: useId()};
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
        const body = {mode, title: title.trim(), style, aspect, mood, duration, platforms, overwrite, grounding: ground, language, ...(voice ? {voice} : {}), ...(mode === 'idea' ? {prompt: prompt.trim()} : {script: scriptText.trim()})};
        const job = await api<Job>('/api/projects/write', {method: 'POST', body});
        watch(job, mode === 'script' ? 'Splitting your script' : 'Writing the script', async (s) => {
          setBusy(false);
          if (s !== 'done') return toast('Script writing failed. Open Studio Activity for the log.', 'err');
          const slug = await slugFromJobLog(job.id).catch(() => null);
          toast('Script stitched together and saved. It is waiting on the Operating Table.', 'ok');
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
        <NarratorFields opts={opts} style={style} language={language} setLanguage={setLanguage} voice={voice} setVoice={setVoice} line={mode === 'script' ? scriptText : ''} />
        <StylePicker styles={opts.styles} value={style} onChange={setStyle} templates={opts.templates} line={mode === 'script' ? scriptText : ''} voice={voice} language={language} />
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
        </div>
        {mode === 'idea' ? <LengthPicker value={duration} onChange={setDuration} longForm={opts.templates[style]?.family === 'long_form'} aspect={aspect} /> : null}
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

export default function Create() {
  const opts = useApi<Options>('/api/options');
  const projects = useApi<ProjectRow[]>('/api/projects');
  if (opts.error) return <Notice tone="blood" title={opts.error.message}>{opts.error.hint}</Notice>;
  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
      {opts.data ? <NewVideo opts={opts.data} onWritten={(slug) => { void projects.reload(); navigate('render', {project: slug}); }} /> : <Skeleton className="h-[560px]" />}
      <Shelf rows={projects.data ?? null} loading={projects.loading} />
    </div>
  );
}
