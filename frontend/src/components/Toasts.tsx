import {AnimatePresence, motion} from 'framer-motion';
import {CircleCheck, CircleX, Info, X} from 'lucide-react';
import {useReducedMotion} from '../lib/hooks';
import {useStudio} from '../lib/studio';
import {cx} from './ui';

/** Announced politely; errors stay 10 s and say what to do next. Sits above the mobile bottom nav. */
export function Toasts() {
  const {toasts, dismissToast} = useStudio();
  const reduce = useReducedMotion();
  return (
    <div aria-live="polite" aria-relevant="additions" className="pointer-events-none fixed inset-x-3 bottom-20 z-[60] flex flex-col items-end gap-2 sm:inset-x-auto sm:right-6 sm:bottom-6 sm:w-[380px]">
      <AnimatePresence initial={false}>
        {toasts.map((t) => {
          const Icon = t.kind === 'err' ? CircleX : t.kind === 'ok' ? CircleCheck : Info;
          return (
            <motion.div
              key={t.id}
              role={t.kind === 'err' ? 'alert' : 'status'}
              initial={reduce ? false : {opacity: 0, y: 12}}
              animate={{opacity: 1, y: 0}}
              exit={reduce ? undefined : {opacity: 0, transition: {duration: 0.12}}}
              transition={{duration: 0.2, ease: [0.16, 1, 0.3, 1]}}
              className={cx('pointer-events-auto flex w-full items-start gap-3 rounded-md border bg-lab-850 p-3 text-sm shadow-lift', t.kind === 'err' ? 'border-blood/50' : t.kind === 'ok' ? 'border-volt/40' : 'border-lab-500')}
            >
              <Icon aria-hidden className={cx('mt-0.5 size-5 shrink-0', t.kind === 'err' ? 'text-blood' : t.kind === 'ok' ? 'text-volt' : 'text-moss')} />
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-bone [overflow-wrap:anywhere]">{t.text}</p>
                {t.hint ? <p className="mt-0.5 text-moss [overflow-wrap:anywhere]">{t.hint}</p> : null}
              </div>
              <button type="button" aria-label="Dismiss" onClick={() => dismissToast(t.id)} className="-m-1 grid size-8 shrink-0 place-items-center rounded-md text-fog hover:bg-lab-700 hover:text-bone">
                <X aria-hidden className="size-4" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
