import {motion, useAnimationControls} from 'framer-motion';
import {useEffect, useRef, useState} from 'react';
import {useHaunted} from './Haunt';
import {cx} from './ui';

/**
 * The mad scientist's switch: the render control. A real <button> (click, Enter or Space all pull it),
 * and on a pointer you can also drag the handle down. The handle drops, current arcs across the
 * contacts, then `onPull` runs. While a render runs the lever stays down and the contacts glow.
 */
export function Lever({onPull, busy, label = 'Render', hint = 'Pull to bring it to life'}: {onPull: () => void; busy?: boolean; label?: string; hint?: string}) {
  const {motion: animate} = useHaunted();
  const knob = useAnimationControls();
  const [armed, setArmed] = useState(false); // the short moment between the pull and onPull
  const drag = useRef<{y: number; id: number} | null>(null);
  const down = busy || armed;

  useEffect(() => {
    void knob.start({y: down ? 22 : 0, transition: animate ? {type: 'spring', stiffness: 520, damping: 22} : {duration: 0}});
  }, [down, knob, animate]);

  const pull = () => {
    if (busy || armed) return;
    setArmed(true);
    window.setTimeout(() => {
      setArmed(false);
      onPull();
    }, animate ? 320 : 0);
  };

  return (
    <button
      type="button"
      data-variant="primary"
      aria-label={busy ? `${label}: running` : `Pull the lever: ${label}`}
      aria-busy={busy || undefined}
      disabled={busy}
      onClick={pull}
      onPointerDown={(e) => {
        if (e.pointerType === 'mouse' && e.button !== 0) return;
        drag.current = {y: e.clientY, id: e.pointerId};
      }}
      onPointerMove={(e) => {
        const d = drag.current;
        if (!d || d.id !== e.pointerId || armed) return;
        const dy = Math.max(0, Math.min(22, e.clientY - d.y));
        void knob.set({y: dy});
      }}
      onPointerUp={() => {
        drag.current = null;
      }}
      onPointerCancel={() => {
        drag.current = null;
        void knob.start({y: 0});
      }}
      className={cx(
        'group relative inline-flex h-14 shrink-0 touch-none items-center gap-3 rounded-lg border-2 py-1.5 pr-4 pl-2 text-left font-semibold transition-[border-color,box-shadow,background-color] duration-200 select-none',
        down ? 'border-volt bg-volt-deep/40 shadow-[0_0_0_3px_rgb(142_240_166/0.15),0_0_24px_rgb(142_240_166/0.35)]' : 'border-pumpkin bg-lab-850 hover:shadow-[0_0_20px_-4px_rgb(255_166_77/0.6)]',
        busy && 'cursor-progress',
      )}
    >
      {/* the switch plate: a slot, two contacts and the handle */}
      <span aria-hidden className="relative h-11 w-8 shrink-0 rounded-md border border-lab-400 bg-lab-950 shadow-[inset_0_2px_6px_rgb(0_0_0/0.6)]">
        <span className="absolute top-1.5 bottom-1.5 left-1/2 w-1 -translate-x-1/2 rounded-full bg-lab-700" />
        <span className={cx('absolute bottom-1 left-1 size-1.5 rounded-full', down ? 'bg-volt shadow-[0_0_6px_#8ef0a6]' : 'bg-lab-500')} />
        <span className={cx('absolute right-1 bottom-1 size-1.5 rounded-full', down ? 'bg-volt shadow-[0_0_6px_#8ef0a6]' : 'bg-lab-500')} />
        {down && animate ? (
          <svg className="absolute bottom-0.5 left-1 h-3 w-6 overflow-visible" viewBox="0 0 24 12">
            <path className="lever-arc" d="M2 8 L7 3 L11 9 L15 2 L19 8 L22 6" fill="none" stroke="#e9ffe9" strokeWidth="1.2" strokeLinejoin="round" />
          </svg>
        ) : null}
        <motion.span animate={knob} initial={{y: 0}} className="absolute top-0.5 left-1/2 -ml-[11px] block">
          <span className="block h-2 w-[22px] rounded-sm bg-[linear-gradient(#ffbd78,#ffa64d_55%,#b8642a)] shadow-[0_2px_4px_rgb(0_0_0/0.6)]" />
          <span className="mx-auto block h-2 w-1.5 bg-lab-400" />
        </motion.span>
      </span>
      <span className="flex min-w-0 flex-col leading-tight">
        <span className={cx('font-display text-xl leading-none tracking-wide', down ? 'text-volt' : 'text-pumpkin')}>{busy ? 'Alive and rendering…' : label}</span>
        <span className="mt-0.5 text-xs font-normal text-moss">{busy ? 'Follow it in Studio Activity' : hint}</span>
      </span>
    </button>
  );
}
