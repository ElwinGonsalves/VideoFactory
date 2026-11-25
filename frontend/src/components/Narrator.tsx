import {AnimatePresence, motion} from 'framer-motion';
import {Ghost, LoaderCircle, Square} from 'lucide-react';
import {useCallback, useEffect, useId, useState, type MouseEvent} from 'react';
import {withToken, type Options} from '../lib/api';
import {useStudio} from '../lib/studio';
import {styleInfo} from '../lib/styles';
import {GhostShape, useHaunted} from './Haunt';
import {Field, Segmented, Select, cx} from './ui';

/* Narrators: language + voice pickers and the ghost that reads a line aloud (Edge-TTS preview). */

export const AUTO_VOICE = '';

/** The voice a style + language would get when the user leaves "Style's narrator" selected. */
export function autoVoice(opts: Options, style: string, language: string): string {
  if (language === 'english' && opts.style_narrators[style]) return opts.style_narrators[style].voice;
  return opts.languages.find((l) => l.id === language)?.default_voice ?? 'en-US-AndrewNeural';
}

export function LanguagePicker({opts, value, onChange}: {opts: Options; value: string; onChange: (v: string) => void}) {
  return (
    <Segmented
      label="Language"
      value={value}
      onChange={onChange}
      options={opts.languages.map((l) => ({value: l.id, label: l.label, hint: l.id === 'hinglish' ? 'Roman script' : l.id === 'hindi' ? 'देवनागरी' : 'Global'}))}
    />
  );
}

export function VoicePicker({opts, language, style, value, onChange, id}: {opts: Options; language: string; style: string; value: string; onChange: (v: string) => void; id?: string}) {
  const auto = autoVoice(opts, style, language);
  const autoName = opts.voices.find((v) => v.id === auto)?.name ?? auto;
  // voices for this language first, then the rest (Hinglish reads fine in the Hindi voices and vice versa)
  const near = opts.voices.filter((v) => v.lang === language || (language !== 'english' && v.lang !== 'english'));
  const far = opts.voices.filter((v) => !near.includes(v));
  const fallbackId = useId();
  return (
    <Select id={id ?? fallbackId} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value={AUTO_VOICE}>{language === 'english' ? `Style's narrator (${autoName})` : `${autoName} (default)`}</option>
      <optgroup label={`${opts.languages.find((l) => l.id === language)?.label ?? 'This language'} voices`}>
        {near.map((v) => <option key={v.id} value={v.id}>{v.name} · {v.about}</option>)}
      </optgroup>
      <optgroup label="Other voices">
        {far.map((v) => <option key={v.id} value={v.id}>{v.name} · {v.about}</option>)}
      </optgroup>
    </Select>
  );
}

// one preview at a time across the whole page
let playing: {audio: HTMLAudioElement; stop: () => void} | null = null;

/** "Hear it": a ghost rises and the narrator reads a line. Each style has its own narrator and sample line. */
export function GhostVoice({style, language, voice, line, className, compact}: {style: string; language: string; voice: string; line: string; className?: string; compact?: boolean}) {
  const {toast} = useStudio();
  const fx = useHaunted();
  const [state, setState] = useState<'idle' | 'loading' | 'playing'>('idle');
  const stop = useCallback(() => {
    playing?.audio.pause();
    playing = null;
    setState('idle');
  }, []);
  useEffect(() => () => {
    if (playing?.stop === stop) stop();
  }, [stop]);
  const play = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (state !== 'idle') return stop();
    playing?.stop();
    const first = line.trim().split(/(?<=[.!?।])\s+/)[0]?.slice(0, 200) ?? '';
    // no text: the server reads this style's own line in this language
    const q = new URLSearchParams({style, language, ...(voice ? {voice} : {}), ...(first.length >= 3 ? {text: first} : {})});
    const audio = new Audio(withToken(`/api/voice/preview?${q}`));
    playing = {audio, stop};
    setState('loading');
    audio.onplaying = () => setState('playing');
    audio.onended = stop;
    audio.onerror = () => {
      stop();
      toast('The ghost lost its voice.', 'err', 'Edge-TTS needs internet. Try again in a moment.');
    };
    void audio.play().catch(() => undefined);
  };
  const name = styleInfo(style).name;
  return (
    <>
      <button
        type="button"
        onClick={play}
        aria-label={state === 'idle' ? `Hear the ${name} narrator` : 'Stop the preview'}
        className={cx(
          'z-10 inline-flex h-8 items-center gap-1.5 rounded-full border px-2.5 text-xs font-semibold backdrop-blur transition-colors pointer-coarse:h-10',
          state === 'idle' ? 'border-lab-400 bg-lab-950/80 text-bone hover:border-ghost hover:text-ghost' : 'border-ghost bg-ghost-deep/90 text-ghost',
          className,
        )}
      >
        {state === 'loading' ? <LoaderCircle aria-hidden className="size-3.5 animate-spin" /> : state === 'playing' ? <Square aria-hidden className="size-3.5" /> : <Ghost aria-hidden className="size-3.5" />}
        {compact ? null : state === 'idle' ? 'Hear it' : state === 'loading' ? 'Summoning' : 'Stop'}
      </button>
      <AnimatePresence>
        {state === 'playing' && fx.motion ? (
          <motion.div key="ghost" aria-hidden className="pointer-events-none absolute top-6 left-1/2 z-10 -ml-6" initial={{y: 40, opacity: 0, scale: 0.6}} animate={{y: [40, -8, 0], opacity: 0.95, scale: 1}} exit={{y: -50, opacity: 0, scale: 0.8, transition: {duration: 0.5}}} transition={{duration: 0.7, ease: [0.16, 1, 0.3, 1]}}>
            <div className="ghost-bob">
              <GhostShape className="ghost h-14 w-12" look={-1} />
            </div>
            <span className="voice-wave mt-1 flex justify-center gap-0.5">{[0, 1, 2, 3, 4].map((i) => <i key={i} style={{animationDelay: `${i * 90}ms`}} />)}</span>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </>
  );
}

// ------------------------------------------------------------------ length: presets + a marked dial
const PRESETS = [
  {sec: 15, label: '15s', hint: 'Teaser'},
  {sec: 30, label: '30s', hint: 'Quick hit'},
  {sec: 45, label: '45s', hint: 'Classic Short'},
  {sec: 58, label: '58s', hint: 'Max Short'},
  {sec: 90, label: '90s', hint: 'Reel'},
  {sec: 180, label: '3 min', hint: 'Explainer'},
  {sec: 600, label: '10 min', hint: 'Long-form'},
];
const fmt = (s: number) => (s < 60 ? `${s}s` : s % 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s / 60} min`);
const STEPS = [15, 20, 25, 30, 35, 40, 45, 50, 55, 58, 60, 75, 90, 120, 150, 180, 240, 300, 420, 600, 900, 1200, 1800];

export function LengthPicker({value, onChange, longForm, aspect}: {value: number; onChange: (n: number) => void; longForm: boolean; aspect: string}) {
  const id = useId();
  const idx = STEPS.reduce((best, s, i) => (Math.abs(s - value) < Math.abs(STEPS[best] - value) ? i : best), 0);
  const words = Math.round(value * 2.6);
  const scenes = Math.max(2, Math.round(value / 7));
  const short = aspect === '9:16' && value <= 60;
  const warn = aspect === '9:16' && value > 60 ? 'Over 60 s: YouTube treats it as a regular video, not a Short.' : longForm && value < 120 ? 'Long-form works best from 3 minutes.' : null;
  return (
    <fieldset className="min-w-0 rounded-lg border border-lab-600 bg-lab-900/60 p-3">
      <legend className="px-1 text-sm font-semibold text-bone">Length</legend>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <output htmlFor={id} className="font-display text-4xl leading-none text-pumpkin tabular" aria-live="polite">{fmt(value)}</output>
        <span className="text-[0.8125rem] text-moss tabular">≈ {words} spoken words · {scenes} scenes{short ? ' · fits a Short' : ''}</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5" role="group" aria-label="Length presets">
        {PRESETS.filter((p) => (longForm ? p.sec >= 90 : p.sec <= 180)).map((p) => (
          <button
            key={p.sec}
            type="button"
            aria-pressed={value === p.sec}
            onClick={() => onChange(p.sec)}
            className={cx('flex min-h-11 flex-col items-start rounded-md border px-2.5 py-1 text-left transition-colors', value === p.sec ? 'border-pumpkin bg-pumpkin/10 text-pumpkin' : 'border-lab-500 bg-lab-850 text-bone hover:border-lab-400')}
          >
            <span className="text-sm font-semibold leading-tight">{p.label}</span>
            <span className="text-[0.6875rem] leading-tight text-fog">{p.hint}</span>
          </button>
        ))}
      </div>
      <label htmlFor={id} className="sr-only">Length, fine adjust</label>
      <input
        id={id}
        type="range"
        min={0}
        max={STEPS.length - 1}
        step={1}
        value={idx}
        onChange={(e) => onChange(STEPS[Number(e.target.value)])}
        aria-valuetext={fmt(value)}
        className="length-dial mt-3 w-full"
        style={{'--fill': `${(idx / (STEPS.length - 1)) * 100}%`} as React.CSSProperties}
      />
      <div aria-hidden className="mt-1 flex justify-between text-[0.6875rem] text-fog tabular"><span>15s</span><span>1 min</span><span>5 min</span><span>30 min</span></div>
      {warn ? <p className="mt-2 text-[0.8125rem] text-candle">{warn}</p> : null}
    </fieldset>
  );
}

export function NarratorFields({opts, style, language, setLanguage, voice, setVoice, line}: {opts: Options; style: string; language: string; setLanguage: (v: string) => void; voice: string; setVoice: (v: string) => void; line: string}) {
  const vid = useId();
  return (
    <div className="grid gap-4 @lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <LanguagePicker opts={opts} value={language} onChange={(l) => { setLanguage(l); setVoice(AUTO_VOICE); }} />
      <Field label="Narrator" htmlFor={vid} hint={language === 'hinglish' ? 'Indian English voices read Roman Hinglish best.' : language === 'hindi' ? 'Scripts are written in Devanagari.' : 'Each style has its own narrator unless you pick one.'}>
        <div className="relative flex gap-2">
          <div className="min-w-0 flex-1"><VoicePicker id={vid} opts={opts} language={language} style={style} value={voice} onChange={setVoice} /></div>
          <GhostVoice style={style} language={language} voice={voice} line={line} className="h-10 shrink-0 pointer-coarse:h-11" />
        </div>
      </Field>
    </div>
  );
}
