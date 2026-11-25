import {AnimatePresence, motion} from 'framer-motion';
import {Bone, Brain, Ear, Eye, Footprints, Hand, HeartPulse, Mic, Zap, type LucideIcon} from 'lucide-react';
import {useCallback, useEffect, useState, type DragEvent} from 'react';
import {api, type Engine, type Onboarding} from '../lib/api';
import {href} from '../lib/hooks';
import {useStudio} from '../lib/studio';
import {useHaunted} from './Haunt';
import {Badge, cx} from './ui';

/*
 * The creature: every stitched engine is an organ on one body. Green organs answered their last check.
 * Click an organ to read what it does. The brain and the voice box take transplants: drop (or click) a
 * donor and every later video uses it (a real Settings change, nothing simulated).
 */
type OrganId = 'brain' | 'eyes' | 'ears' | 'voice' | 'heart' | 'spine' | 'lhand' | 'rhand' | 'legs';
type Organ = {id: OrganId; label: string; icon: LucideIcon; engine?: string; role: string; x: number; y: number; swappable?: boolean};
// positions are % of the figure box
const ORGANS: Organ[] = [
  {id: 'brain', label: 'Brain', icon: Brain, role: 'Writes scripts, ideas, titles and hashtags.', x: 50, y: 7, swappable: true},
  {id: 'eyes', label: 'Eyes', icon: Eye, engine: 'watchvideo', role: 'Watch reference videos and read their Style DNA.', x: 50, y: 17},
  {id: 'ears', label: 'Ears', icon: Ear, engine: 'whisper', role: 'Hear the narration and time every caption word.', x: 77, y: 13},
  {id: 'voice', label: 'Voice box', icon: Mic, engine: 'tts', role: 'Speaks the narration in the chosen voice.', x: 50, y: 28, swappable: true},
  {id: 'heart', label: 'Heart', icon: HeartPulse, engine: 'ffmpeg', role: 'Pumps audio and video: music ducking, SFX, loudness, encoding.', x: 40, y: 42},
  {id: 'spine', label: 'Skeleton', icon: Bone, engine: 'remotion', role: 'Holds every frame together: Remotion draws the scenes.', x: 60, y: 52},
  {id: 'lhand', label: 'Left hand', icon: Hand, engine: 'explainroo', role: 'Sketches whiteboard videos (Explainroo, Rough.js).', x: 12, y: 50},
  {id: 'rhand', label: 'Right hand', icon: Hand, engine: 'manim', role: 'Draws math and algorithm animations (Manim).', x: 88, y: 50},
  {id: 'legs', label: 'Legs', icon: Footprints, engine: 'playwright', role: 'Carry finished videos out to YouTube, Instagram and TikTok.', x: 50, y: 86},
];
type Donor = {id: string; organ: 'brain' | 'voice'; name: string; note: string};
const DONORS: Donor[] = [
  {id: 'gemini', organ: 'brain', name: 'Gemini', note: 'Google, free tier'},
  {id: 'groq', organ: 'brain', name: 'Groq', note: 'Llama, free and fast'},
  {id: 'openrouter', organ: 'brain', name: 'OpenRouter', note: 'free :free models'},
  {id: 'ollama', organ: 'brain', name: 'Ollama', note: 'offline on this PC'},
  {id: 'edge-tts', organ: 'voice', name: 'Edge-TTS', note: '12 free voices, Hindi too'},
  {id: 'kokoro', organ: 'voice', name: 'Kokoro', note: 'local, GPU'},
];
const VOICE_DEFAULT: Record<string, string> = {'edge-tts': 'en-US-AndrewNeural', kokoro: 'af_heart'};

export function Transplant() {
  const {act, toast, refreshEngines, engines} = useStudio();
  const {motion: animate} = useHaunted();
  const [info, setInfo] = useState<Onboarding | null>(null);
  const [focus, setFocus] = useState<OrganId>('brain');
  const [over, setOver] = useState<OrganId | null>(null);
  const [dragging, setDragging] = useState<Donor | null>(null);
  const [zap, setZap] = useState<{organ: OrganId; at: number} | null>(null);
  const load = useCallback(() => void api<Onboarding>('/api/onboarding').then(setInfo).catch(() => undefined), []);
  useEffect(load, [load]);

  const installed = {brain: info?.provider ?? 'gemini', voice: info?.voice_engine ?? 'edge-tts'};
  const ready = (d: Donor) => (d.organ === 'brain' ? info?.brains?.[d.id] !== false : info?.voices?.[d.id] !== false);
  const engineOf = (o: Organ): Engine | undefined => (o.engine ? engines?.engines.find((e) => e.key === o.engine) : undefined);
  const health = (o: Organ): 'alive' | 'dormant' | 'missing' => {
    if (o.id === 'brain') return info ? (info.key_set ? 'alive' : 'dormant') : 'alive';
    const e = engineOf(o);
    return !e ? 'alive' : e.ok ? 'alive' : e.required ? 'missing' : 'dormant';
  };

  const transplant = (d: Donor) =>
    act(async () => {
      setFocus(d.organ);
      if (installed[d.organ] === d.id) return toast(`${d.name} is already the ${d.organ === 'brain' ? 'brain' : 'voice box'}.`, 'info');
      if (!ready(d)) {
        return toast(
          d.organ === 'brain' ? `${d.name} needs an API key first.` : `${d.name} is not installed.`,
          'err',
          d.organ === 'brain' ? 'Add it in The Apothecary > Brain & spend.' : 'pip install kokoro (needs a GPU for speed).',
        );
      }
      const body = d.organ === 'brain' ? {llm: {provider: d.id}} : {defaults: {voice_engine: d.id, voice: VOICE_DEFAULT[d.id]}};
      await api('/api/settings/prefs', {method: 'PUT', body});
      setZap({organ: d.organ, at: Date.now()});
      toast(`${d.name} transplanted into the ${d.organ === 'brain' ? 'brain' : 'voice box'}. It lives!`, 'ok');
      load();
      void refreshEngines(true);
    });

  const onDrop = (o: Organ) => (e: DragEvent) => {
    e.preventDefault();
    setOver(null);
    const d = DONORS.find((x) => x.id === e.dataTransfer.getData('text/organ'));
    if (!d) return;
    if (d.organ !== o.id) return toast(`${d.name} will not take in the ${o.label.toLowerCase()}.`, 'err', `It is a ${d.organ === 'brain' ? 'brain' : 'voice box'}.`);
    void transplant(d);
  };

  const cur = ORGANS.find((o) => o.id === focus)!;
  const curEngine = engineOf(cur);
  const curHealth = health(cur);
  const donors = DONORS.filter((d) => d.organ === focus);
  return (
    <section aria-labelledby="creature-h">
      <h3 id="creature-h" className="font-display text-2xl leading-none text-bone">The creature</h3>
      <p className="mt-1 text-sm text-moss">Nine organs, one body. Click an organ to see what it does; drag a donor onto the brain or voice box to transplant it.</p>
      <div className="mt-4 grid gap-5 sm:grid-cols-[240px_minmax(0,1fr)]">
        {/* the body */}
        <div className="relative mx-auto aspect-[2/3] w-[240px]">
          <svg viewBox="0 0 200 300" className="absolute inset-0 size-full" aria-hidden>
            <g className="fill-lab-850 stroke-lab-400" strokeWidth="1.5" strokeLinejoin="round">
              {/* head with the flat top, neck bolts, shoulders, arms, torso and legs */}
              <path d="M74 6h52l6 8v34l-8 12H76l-8-12V14z" />
              <path d="M88 60h24v16H88z" />
              <path d="M52 78h96l14 18-6 92H44l-6-92z" />
              <path d="M38 96 18 150l-6 20 14 4 8-18 18-40z" />
              <path d="M162 96l20 54 6 20-14 4-8-18-18-40z" />
              <path d="M56 188h40l-4 96H66z" />
              <path d="M104 188h40l-10 96h-26z" />
            </g>
            <g className="fill-lab-500"><circle cx="64" cy="66" r="4" /><circle cx="136" cy="66" r="4" /></g>
            {/* stitches */}
            <g className="stroke-volt/60" strokeWidth="1.2" strokeDasharray="3 3" fill="none">
              <path d="M70 16h60" /><path d="M100 82v104" /><path d="M54 130h92" /><path d="M76 200v80M124 200v80" /><path d="M30 120l-12 40M170 120l12 40" />
            </g>
          </svg>
          {ORGANS.map((o) => {
            const h = health(o);
            const fits = dragging?.organ === o.id;
            return (
              <button
                key={o.id}
                type="button"
                onClick={() => setFocus(o.id)}
                onDragOver={(e) => {
                  if (!dragging || dragging.organ !== o.id) return;
                  e.preventDefault();
                  setOver(o.id);
                }}
                onDragLeave={() => setOver((x) => (x === o.id ? null : x))}
                onDrop={onDrop(o)}
                aria-label={`${o.label}: ${h}${o.swappable ? ', takes transplants' : ''}`}
                aria-pressed={focus === o.id}
                className={cx(
                  'absolute grid size-10 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-2 transition-[transform,box-shadow,border-color,background-color] duration-150 hover:scale-110 pointer-coarse:size-11',
                  h === 'alive' ? 'border-volt bg-volt-deep text-volt' : h === 'missing' ? 'border-blood bg-blood-deep text-blood' : 'border-candle/70 bg-candle-deep text-candle',
                  focus === o.id && 'ring-2 ring-pumpkin ring-offset-2 ring-offset-lab-900',
                  o.swappable && 'border-dashed',
                  (over === o.id || fits) && 'scale-125 shadow-glow',
                )}
                style={{left: `${o.x}%`, top: `${o.y}%`}}
              >
                <o.icon aria-hidden className={cx('size-[18px]', o.id === 'rhand' && '-scale-x-100', h === 'alive' && o.id === 'heart' && animate && 'heart-beat')} />
                <AnimatePresence>
                  {zap?.organ === o.id && animate ? (
                    <motion.span key={zap.at} aria-hidden className="pointer-events-none absolute -inset-2 rounded-full border-2 border-volt" initial={{opacity: 1, scale: 0.8}} animate={{opacity: 0, scale: 2}} exit={{opacity: 0}} transition={{duration: 0.7}} style={{boxShadow: '0 0 22px #8ef0a6'}} />
                  ) : null}
                </AnimatePresence>
              </button>
            );
          })}
        </div>
        {/* the organ card */}
        <div className="min-w-0">
          <div className="rounded-lg border border-lab-600 bg-lab-850 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <cur.icon aria-hidden className="size-5 text-pumpkin" />
              <span className="font-display text-xl leading-none text-bone">{cur.label}</span>
              <Badge tone={curHealth === 'alive' ? 'volt' : curHealth === 'missing' ? 'blood' : 'candle'} className="ml-auto">{curHealth}</Badge>
            </div>
            <p className="mt-1.5 text-sm text-moss">{cur.role}</p>
            <p className="mt-1 font-mono text-xs text-fog [overflow-wrap:anywhere]">
              {cur.id === 'brain' ? `${DONORS.find((d) => d.id === installed.brain)?.name ?? installed.brain}${info?.key_set ? '' : ' (no key yet)'}` : cur.id === 'voice' ? `${DONORS.find((d) => d.id === installed.voice)?.name ?? installed.voice} · ${curEngine?.detail ?? ''}` : curEngine ? `${curEngine.name} · ${curEngine.detail}` : ''}
            </p>
          </div>
          {cur.swappable ? (
            <div className="mt-4">
              <p className="mb-1.5 text-sm font-semibold text-bone">Donor {cur.id === 'brain' ? 'brains' : 'voice boxes'}</p>
              <ul className="grid grid-cols-2 gap-2">
                {donors.map((d) => {
                  const inUse = installed[d.organ] === d.id;
                  const ok = ready(d);
                  return (
                    <li key={d.id}>
                      <button
                        type="button"
                        draggable={!inUse}
                        onDragStart={(e) => {
                          e.dataTransfer.setData('text/organ', d.id);
                          e.dataTransfer.effectAllowed = 'move';
                          setDragging(d);
                        }}
                        onDragEnd={() => {
                          setDragging(null);
                          setOver(null);
                        }}
                        onClick={() => void transplant(d)}
                        aria-label={inUse ? `${d.name}: in the ${cur.label} now` : `Transplant ${d.name} into the ${cur.label}${ok ? '' : ' (not set up yet)'}`}
                        className={cx('flex w-full min-w-0 flex-col items-start rounded-md border px-2.5 py-2 text-left transition-[border-color,background-color,transform] duration-150',
                          inUse ? 'cursor-default border-volt/60 bg-volt-deep/30' : ok ? 'cursor-grab border-lab-500 bg-lab-850 hover:-translate-y-0.5 hover:border-pumpkin active:cursor-grabbing' : 'border-dashed border-lab-500 bg-lab-900 hover:border-candle')}
                      >
                        <span className="flex w-full items-center gap-1.5 text-sm font-semibold text-bone">
                          {inUse ? <Zap aria-hidden className="size-3.5 text-volt" /> : null}
                          <span className="truncate">{d.name}</span>
                        </span>
                        <span className="w-full truncate text-xs text-fog">{inUse ? 'in the creature' : ok ? d.note : d.organ === 'brain' ? 'needs a key' : 'not installed'}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
              <p className="mt-2 text-xs text-fog">
                {cur.id === 'brain' ? <>Keys live in <a className="text-pumpkin underline underline-offset-4" href={href('settings', {section: 'model'})}>The Apothecary &gt; Brain &amp; spend</a>. If the brain fails mid-script, the backup brains take over.</> : 'Pick the narrator itself per video in the Laboratory or on the Operating Table.'}
              </p>
            </div>
          ) : (
            <p className="mt-3 text-xs text-fog">This organ is fixed for now. A dormant organ only matters for the styles that use it; the deep check below tests it properly.</p>
          )}
        </div>
      </div>
    </section>
  );
}
