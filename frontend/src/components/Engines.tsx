import {Bone, Brain, ChevronDown, Ear, Eye, Hand, HeartPulse, Mic, RefreshCw, Spline, Stethoscope, type LucideIcon} from 'lucide-react';
import {useEffect} from 'react';
import {api, type Engine, type Job} from '../lib/api';
import {useStudio} from '../lib/studio';
import {Overlay} from './Overlay';
import {Transplant} from './Transplant';
import {Badge, Button, cx} from './ui';

const ORGAN_ICON: Record<string, LucideIcon> = {
  remotion: Bone,
  ffmpeg: HeartPulse,
  whisper: Ear,
  tts: Mic,
  explainroo: Hand,
  manim: Hand,
  watchvideo: Eye,
  playwright: Hand,
};

/** The organs on one spine. Current runs down the seam while each organ is alive. */
export function EngineSpine({engines, compact}: {engines: Engine[]; compact?: boolean}) {
  return (
    <ol className="relative" aria-label="Stitched engines">
      {engines.map((e, i) => {
        const Icon = ORGAN_ICON[e.key] ?? Brain;
        const last = i === engines.length - 1;
        return (
          <li key={e.key} className={cx('relative flex gap-3', compact ? 'pb-3' : 'pb-4')}>
            {!last ? (
              <svg aria-hidden className="absolute top-10 left-[19px] h-[calc(100%-2.5rem)] w-1 overflow-visible">
                <line x1="2" y1="0" x2="2" y2="100%" strokeWidth={2} strokeLinecap="round" className={e.ok && engines[i + 1].ok ? 'seam-live stroke-volt/80' : 'stroke-lab-500 [stroke-dasharray:3_6]'} />
              </svg>
            ) : null}
            <span className={cx('relative z-10 grid size-10 shrink-0 place-items-center rounded-full border-2', e.ok ? 'border-volt bg-volt-deep text-volt' : e.required ? 'border-blood bg-blood-deep text-blood' : 'border-candle/60 bg-candle-deep text-candle')}>
              <Icon aria-hidden className="size-[18px]" />
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="font-semibold text-bone">{e.name}</span>
                <span className="text-xs text-fog">the {e.organ.toLowerCase()}</span>
                <Badge tone={e.ok ? 'volt' : e.required ? 'blood' : 'candle'} className="ml-auto">{e.ok ? 'alive' : e.required ? 'missing' : 'dormant'}</Badge>
              </div>
              {!compact ? <p className="text-sm text-moss">{e.role}</p> : null}
              <p className="font-mono text-xs text-fog [overflow-wrap:anywhere]">{e.detail}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function EnginesBadge({collapsed}: {collapsed?: boolean}) {
  const {engines, setEnginesOpen, refreshEngines} = useStudio();
  useEffect(() => {
    void refreshEngines(false);
  }, [refreshEngines]);
  const ok = engines?.required_ok ?? true;
  const label = engines ? `${engines.alive}/${engines.total} organs alive` : 'Checking organs…';
  return (
    <button
      type="button"
      onClick={() => setEnginesOpen(true)}
      aria-haspopup="dialog"
      aria-label={`Stitched Engines: ${label}`}
      title={collapsed ? `Stitched Engines · ${label}` : undefined}
      className={cx(
        'group flex w-full min-w-0 items-center gap-3 rounded-md border border-dashed p-2.5 text-left transition-[border-color,box-shadow,background-color] duration-200 hover:bg-lab-850',
        ok ? 'border-volt/40 hover:shadow-glow' : 'border-blood/50',
        collapsed && 'justify-center p-2',
      )}
    >
      <span className={cx('grid size-8 shrink-0 place-items-center rounded-full', ok ? 'bg-volt-deep text-volt' : 'bg-blood-deep text-blood')}>
        <Spline aria-hidden className="size-4 transition-transform duration-300 group-hover:rotate-12" />
      </span>
      {!collapsed ? (
        <span className="min-w-0">
          <span className="block text-sm font-semibold text-bone">Stitched Engines</span>
          <span className="block truncate text-xs text-moss tabular">{label}</span>
        </span>
      ) : null}
    </button>
  );
}

export function EnginesModal() {
  const {enginesOpen, setEnginesOpen, engines, refreshEngines, act, watch} = useStudio();
  const deep = () =>
    act(async () => {
      const job = await api<Job>('/api/health', {method: 'POST'});
      watch(job, 'Deep check (doctor.py)');
      setEnginesOpen(false);
    });
  return (
    <Overlay
      open={enginesOpen}
      onClose={() => setEnginesOpen(false)}
      wide
      title="Stitched Engines"
      description="One body stitched from open-source organs. Green means the organ answered its last check."
      footer={
        <>
          <Button variant="ghost" icon={RefreshCw} onClick={() => act(() => refreshEngines(true))}>Check again</Button>
          <Button variant="secondary" icon={Stethoscope} onClick={deep}>Deep check (doctor.py)</Button>
        </>
      }
    >
      {enginesOpen ? <Transplant /> : null}
      <details className="group mt-6 rounded-md border border-lab-700 px-3">
        <summary className="flex min-h-11 list-none items-center gap-2 text-sm font-semibold text-moss hover:text-bone [&::-webkit-details-marker]:hidden">
          <ChevronDown aria-hidden className="size-4 transition-transform group-open:rotate-180" />
          Every organ, with versions
        </summary>
        <div className="pt-2 pb-3">
          {engines ? <EngineSpine engines={engines.engines} /> : <p className="text-sm text-moss">Listening for a heartbeat…</p>}
          <p className="mt-2 text-[0.8125rem] text-fog">
            These are presence checks (installed, on PATH, cloned). The deep check loads Whisper on the GPU and renders nothing; results open in Studio Activity.
          </p>
        </div>
      </details>
    </Overlay>
  );
}
