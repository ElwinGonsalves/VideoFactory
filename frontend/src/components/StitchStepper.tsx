import {AudioLines, Check, Clapperboard, Mic, ScanSearch, ScrollText, X, type LucideIcon} from 'lucide-react';
import {useEffect, useRef, useState} from 'react';
import {cx} from './ui';

export const NODE_META: {id: string; label: string; engine: string; icon: LucideIcon}[] = [
  {id: 'script', label: 'Script', engine: 'Gemini / Groq', icon: ScrollText},
  {id: 'voice', label: 'Voice', engine: 'Edge-TTS · Whisper', icon: Mic},
  {id: 'music', label: 'Music+\u200bSFX', engine: 'FFmpeg', icon: AudioLines},
  {id: 'render', label: 'Render', engine: 'Remotion', icon: Clapperboard},
  {id: 'qa', label: 'QA', engine: 'Pixel QA', icon: ScanSearch},
];

type State = 'done' | 'active' | 'pending' | 'failed';

/**
 * The Frankenstein stitch: five organs joined by seams. A seam carries current (animated dashes)
 * only into the node that is working; finished seams are solid, unreached seams are dashed and dim.
 */
export function StitchStepper({activeIndex, failed, finished, compact}: {activeIndex: number | null; failed?: boolean; finished?: boolean; compact?: boolean}) {
  const stateOf = (i: number): State => {
    if (finished) return 'done';
    if (activeIndex == null) return 'pending';
    if (i < activeIndex) return 'done';
    if (i === activeIndex) return failed ? 'failed' : 'active';
    return 'pending';
  };
  const current = activeIndex == null ? null : NODE_META[Math.min(activeIndex, 4)];
  // organs that finished since the last render flash once ("node-zap")
  const doneCount = finished ? 5 : activeIndex ?? 0;
  const prevDone = useRef(doneCount);
  const [zapped, setZapped] = useState<number[]>([]);
  useEffect(() => {
    if (doneCount > prevDone.current) {
      const fresh = Array.from({length: doneCount - prevDone.current}, (_, k) => prevDone.current + k);
      setZapped(fresh);
      const t = window.setTimeout(() => setZapped([]), 800);
      prevDone.current = doneCount;
      return () => window.clearTimeout(t);
    }
    prevDone.current = doneCount;
  }, [doneCount]);
  return (
    <div>
      <ol className="grid grid-cols-5" aria-label="Pipeline stages">
        {NODE_META.map((n, i) => {
          const s = stateOf(i);
          const Icon = s === 'done' ? Check : s === 'failed' ? X : n.icon;
          const into = i > 0 ? stateOf(i) : null;
          return (
            <li key={n.id} className="relative flex min-w-0 flex-col items-center text-center" aria-current={s === 'active' ? 'step' : undefined}>
              {i > 0 ? (
                <svg aria-hidden className="absolute top-[19px] right-1/2 h-1 w-full overflow-visible" preserveAspectRatio="none">
                  <line
                    x1="0" y1="2" x2="100%" y2="2"
                    strokeWidth={2}
                    strokeLinecap="round"
                    className={cx(
                      into === 'done' && 'stroke-volt',
                      into === 'active' && 'seam-live stroke-volt',
                      into === 'failed' && 'stroke-blood',
                      into === 'pending' && 'stroke-lab-500 [stroke-dasharray:3_6]',
                    )}
                  />
                </svg>
              ) : null}
              {into === 'active' ? (
                <span aria-hidden className="absolute top-0 right-1/2 h-10 w-full">
                  <span className="seam-spark" />
                </span>
              ) : null}
              <span
                className={cx(
                  'relative z-10 grid size-10 place-items-center rounded-full border-2 transition-[background-color,border-color,box-shadow] duration-300',
                  s === 'done' && 'border-volt bg-volt-deep text-volt',
                  s === 'active' && 'border-pumpkin bg-lab-850 text-pumpkin shadow-[0_0_0_4px_rgb(255_166_77/0.15),0_0_18px_rgb(142_240_166/0.35)]',
                  s === 'failed' && 'border-blood bg-blood-deep text-blood',
                  s === 'pending' && 'border-lab-500 bg-lab-900 text-fog',
                )}
              >
                <Icon aria-hidden className={cx('size-[18px]', s === 'active' && 'animate-flicker')} />
                {zapped.includes(i) ? <span aria-hidden className="node-zap" /> : null}
              </span>
              <span className={cx('mt-1.5 w-full px-0.5 text-xs leading-tight font-semibold', s === 'pending' ? 'text-fog' : 'text-bone')}>{n.label}</span>
              {!compact ? <span className="mt-0.5 hidden w-full px-0.5 text-xs leading-tight text-fog min-[400px]:block">{n.engine}</span> : null}
              <span className="sr-only">{s === 'done' ? 'done' : s === 'active' ? 'in progress' : s === 'failed' ? 'failed' : 'waiting'}</span>
            </li>
          );
        })}
      </ol>
      {current && !finished ? (
        <p className="mt-2 text-center text-xs text-fog">
          {failed ? 'Stopped at' : 'Stitching'} <span className="font-semibold text-moss">{current.label}</span> with {current.engine}
        </p>
      ) : null}
    </div>
  );
}
