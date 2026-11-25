import {ArrowDown, ArrowUp, ChevronDown, Clapperboard, Plus, Save, Trash} from 'lucide-react';
import {useEffect, useState} from 'react';
import {Lever} from '../components/Lever';
import {AUTO_VOICE, autoVoice, NarratorFields} from '../components/Narrator';
import {Shelf} from '../components/Shelf';
import {Badge, Button, Check as CheckBox, EmptyState, Input, LinkButton, Notice, Panel, Select, Skeleton, SpecimenTag, Textarea} from '../components/ui';
import {api, type Job, type Options, type ProjectRow, type Script} from '../lib/api';
import {safeHref, titleCase} from '../lib/format';
import {href, navigate, useApi, useRoute} from '../lib/hooks';
import {useStudio} from '../lib/studio';
import {styleInfo} from '../lib/styles';

/*
 * The Operating Table: every written script lands here. Pick one from the slab, adjust scenes and the
 * narrator, then pull the lever. Finished videos move to Dracula's Vault (Library).
 */

/** Narrator controls bound to a script: language + voice, written into script.json on Save/Render. */
function ScriptNarrator({opts, script, onChange}: {opts: Options; script: Script; onChange: (s: Script) => void}) {
  const style = String(script.style ?? 'concept_explainer');
  const language = String(script.language ?? 'english');
  const cur = (script.voice as {voice?: string; engine?: string; rate?: string} | undefined) ?? {};
  const isAuto = !cur.voice || cur.voice === autoVoice(opts, style, language);
  const firstLine = String(script.scenes[0]?.narration ?? '');
  const setVoice = (id: string, lang = language) => {
    const vid = id === AUTO_VOICE ? autoVoice(opts, style, lang) : id;
    const engine = opts.voices.find((v) => v.id === vid)?.engine ?? 'edge-tts';
    onChange({...script, language: lang, voice: {...cur, engine, voice: vid}});
  };
  return (
    <section aria-labelledby="narrator-h" className="mb-5 rounded-lg border border-lab-600 bg-lab-900/60 p-3">
      <h3 id="narrator-h" className="mb-2 font-display text-xl leading-none text-bone">Narrator</h3>
      <NarratorFields opts={opts} style={style} language={language} setLanguage={(l) => setVoice(AUTO_VOICE, l)} voice={isAuto ? AUTO_VOICE : String(cur.voice)} setVoice={(v) => setVoice(v)} line={firstLine} />
      <p className="mt-2 text-xs text-fog">Changing the language here swaps the narrator and caption mode; it does not translate the scenes. To get a Hindi or Hinglish script, write it in that language in the Laboratory.</p>
    </section>
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
            toast('It’s alive! Your video is in Dracula’s Vault.', 'ok');
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
          <Lever onPull={() => void render()} busy={busy} label="Render" />
        </div>
      }
    >
      <ScriptNarrator opts={opts} script={script} onChange={update} />
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
              <a href={safeHref(s.url)} target="_blank" rel="noopener noreferrer" className="text-pumpkin underline underline-offset-4">{s.title}</a>
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


export default function Render() {
  const route = useRoute();
  const opts = useApi<Options>('/api/options');
  const projects = useApi<ProjectRow[]>('/api/projects');
  const current = route.params.get('project') ?? '';
  const scripts = (projects.data ?? []).filter((p) => p.stage === 'script');
  // nothing picked: open the newest waiting script so the table is never empty when there is work
  useEffect(() => {
    if (!current && route.page === 'render' && scripts[0]) navigate('render', {project: scripts[0].slug}, '', {replace: true});
  }, [current, route.page, scripts]);
  if (opts.error) return <Notice tone="blood" title={opts.error.message}>{opts.error.hint}</Notice>;
  return (
    <div className="grid items-start gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
      <Shelf rows={projects.data ?? null} loading={projects.loading} current={current} title="The slab" description="Scripts wait here until you bring them to life." start="script" className="xl:sticky xl:top-20" />
      {current && opts.data ? (
        <Editor key={current} slug={current} opts={opts.data} onSaved={() => void projects.reload()} />
      ) : projects.data ? (
        <EmptyState art={<Clapperboard aria-hidden className="size-8 text-fog" />} title="Nothing on the table" action={<LinkButton href={href('create')} variant="primary">Write a script</LinkButton>}>
          Every script you write in the Laboratory lands here, ready to render whenever you want.
        </EmptyState>
      ) : (
        <Skeleton className="h-96" />
      )}
    </div>
  );
}
