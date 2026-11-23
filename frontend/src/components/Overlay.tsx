import {AnimatePresence, motion} from 'framer-motion';
import {X} from 'lucide-react';
import {useEffect, useId, useRef, type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import {useReducedMotion} from '../lib/hooks';
import {IconButton, cx} from './ui';

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"]),video[controls]';

/**
 * Modal surface: moves focus in on open, traps Tab, closes on Escape and on backdrop click,
 * and returns focus to the element that opened it.
 */
export function Overlay({open, onClose, title, description, children, variant = 'center', footer, wide, labelledBy}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  variant?: 'center' | 'right' | 'bottom';
  footer?: ReactNode;
  wide?: boolean;
  labelledBy?: string;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const opener = useRef<Element | null>(null);
  const titleId = useId();
  const descId = useId();
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!open) return;
    opener.current = document.activeElement;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    // Everything behind the dialog leaves the tab order and the accessibility tree.
    const root = document.getElementById('root');
    const wasInert = root?.inert ?? false;
    if (root) root.inert = true;
    const t = window.setTimeout(() => {
      const first = panel.current?.querySelector<HTMLElement>('[data-autofocus]') ?? panel.current?.querySelector<HTMLElement>(FOCUSABLE);
      (first ?? panel.current)?.focus();
    }, 30);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab' || !panel.current) return;
      const items = [...panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey, true);
    return () => {
      window.clearTimeout(t);
      document.removeEventListener('keydown', onKey, true);
      document.body.style.overflow = prevOverflow;
      if (root) root.inert = wasInert;
      (opener.current as HTMLElement | null)?.focus?.();
    };
  }, [open, onClose]);

  const from = variant === 'right' ? {x: '100%'} : variant === 'bottom' ? {y: '100%'} : {y: 16, scale: 0.98, opacity: 0};
  const to = variant === 'center' ? {y: 0, scale: 1, opacity: 1} : {x: 0, y: 0};
  const shell = {
    center: 'items-end sm:items-center justify-center p-0 sm:p-6',
    right: 'items-stretch justify-end',
    bottom: 'items-end justify-center',
  }[variant];
  const box = {
    center: cx('w-full max-h-[92dvh] rounded-t-lg sm:rounded-lg', wide ? 'sm:max-w-3xl' : 'sm:max-w-lg'),
    right: 'h-dvh w-full sm:max-w-[440px] sm:border-l',
    bottom: 'w-full max-h-[85dvh] rounded-t-lg',
  }[variant];

  return createPortal(
    <AnimatePresence>
      {open ? (
        <div className={cx('fixed inset-0 z-50 flex', shell)}>
          <motion.div
            aria-hidden
            className="absolute inset-0 bg-lab-950/75 backdrop-blur-[2px]"
            initial={{opacity: 0}}
            animate={{opacity: 1}}
            exit={{opacity: 0}}
            transition={{duration: reduce ? 0 : 0.18}}
            onClick={onClose}
          />
          <motion.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-labelledby={labelledBy ?? titleId}
            aria-describedby={description ? descId : undefined}
            tabIndex={-1}
            className={cx('relative flex flex-col overflow-hidden border-lab-600 bg-lab-900 shadow-lift outline-none', variant !== 'right' && 'border', box)}
            initial={reduce ? false : from}
            animate={to}
            exit={reduce ? undefined : {...from, transition: {duration: 0.14}}}
            transition={{type: 'tween', ease: [0.16, 1, 0.3, 1], duration: 0.24}}
          >
            <header className="flex items-start gap-3 border-b border-lab-700 px-5 py-4 [padding-top:max(1rem,env(safe-area-inset-top))] sm:[padding-top:1rem]">
              <div className="min-w-0 flex-1">
                <h2 id={titleId} className="font-display text-2xl leading-tight tracking-wide text-bone">{title}</h2>
                {description ? <p id={descId} className="mt-0.5 text-sm text-moss">{description}</p> : null}
              </div>
              <IconButton label="Close" icon={X} onClick={onClose} className="-mr-2 -mt-1" />
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-4">{children}</div>
            {footer ? <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-lab-700 px-5 py-3 [padding-bottom:max(0.75rem,env(safe-area-inset-bottom))]">{footer}</footer> : null}
          </motion.div>
        </div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
