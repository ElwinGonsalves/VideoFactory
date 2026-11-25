import {CircleCheck, CircleExclamationPoint, CircleX, Clock, Info, LoaderCircle, type LucideIcon} from 'lucide-react';
import {forwardRef, useId, useLayoutEffect, useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes} from 'react';

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ');

// ------------------------------------------------------------------ buttons (one height per size: sm 32, md 40, 44 on touch)
type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-pumpkin text-pumpkin-ink hover:bg-pumpkin-hi shadow-[0_6px_20px_-8px_rgb(255_166_77/0.6)]',
  secondary: 'bg-lab-800 text-bone border border-lab-500 hover:border-lab-400 hover:bg-lab-700',
  ghost: 'text-moss hover:text-bone hover:bg-lab-800',
  danger: 'text-blood border border-blood/40 hover:bg-blood-deep',
};
export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {variant?: Variant; size?: 'sm' | 'md'; icon?: LucideIcon; loading?: boolean};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {variant = 'secondary', size = 'md', icon: Icon, loading, className, children, disabled, type = 'button', ...rest},
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      data-variant={variant}
      className={cx(
        'inline-flex shrink-0 items-center justify-center gap-2 rounded-md font-semibold whitespace-nowrap transition-[background-color,border-color,color,box-shadow,transform] duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none',
        size === 'md' ? 'h-10 px-4 text-sm pointer-coarse:h-11' : 'h-8 px-3 text-[0.8125rem] pointer-coarse:h-10',
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {loading ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : Icon ? <Icon aria-hidden className="size-4" /> : null}
      {children}
    </button>
  );
});

/** Navigation styled as a button: a real <a> (middle-click and copy-link work), never <a><button>. */
export function LinkButton({href, variant = 'secondary', size = 'md', icon: Icon, children, className, download, external}: {href: string; variant?: Variant; size?: 'sm' | 'md'; icon?: LucideIcon; children: ReactNode; className?: string; download?: string | boolean; external?: boolean}) {
  return (
    <a
      href={href}
      download={download === true ? '' : download || undefined}
      target={external ? '_blank' : undefined}
      rel={external ? 'noopener noreferrer' : undefined}
      data-variant={variant}
      className={cx(
        'inline-flex shrink-0 items-center justify-center gap-2 rounded-md font-semibold whitespace-nowrap transition-[background-color,border-color,color] duration-150',
        size === 'md' ? 'h-10 px-4 text-sm pointer-coarse:h-11' : 'h-8 px-3 text-[0.8125rem] pointer-coarse:h-10',
        VARIANTS[variant],
        className,
      )}
    >
      {Icon ? <Icon aria-hidden className="size-4" /> : null}
      {children}
    </a>
  );
}

export function IconButton({label, icon: Icon, className, size = 'md', ...rest}: ButtonHTMLAttributes<HTMLButtonElement> & {label: string; icon: LucideIcon; size?: 'sm' | 'md'}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cx(
        'inline-grid shrink-0 place-items-center rounded-md text-moss transition-colors duration-150 hover:bg-lab-800 hover:text-bone disabled:opacity-40',
        size === 'md' ? 'size-10 pointer-coarse:size-11' : 'size-8 pointer-coarse:size-10',
        className,
      )}
      {...rest}
    >
      <Icon aria-hidden className={size === 'md' ? 'size-5' : 'size-4'} />
    </button>
  );
}

// ------------------------------------------------------------------ fields: label above, hint and error as text below
export function Field({label, hint, error, children, htmlFor, className, optional}: {label: ReactNode; hint?: ReactNode; error?: string; children: ReactNode; htmlFor: string; className?: string; optional?: boolean}) {
  return (
    <div className={cx('flex min-w-0 flex-col gap-1.5', className)}>
      <label htmlFor={htmlFor} className="text-sm font-semibold text-bone">
        {label}
        {optional ? <span className="ml-1.5 font-normal text-fog">optional</span> : null}
      </label>
      {children}
      {error ? (
        <p role="alert" className="flex items-start gap-1.5 text-sm text-blood">
          <CircleExclamationPoint aria-hidden className="mt-0.5 size-4 shrink-0" />
          {error}
        </p>
      ) : hint ? (
        <p className="text-[0.8125rem] text-fog">{hint}</p>
      ) : null}
    </div>
  );
}

const control =
  'w-full min-w-0 rounded-md border border-lab-400/70 bg-lab-950 px-3 text-bone placeholder:text-fog transition-[border-color,box-shadow] duration-150 hover:border-lab-400 focus:border-pumpkin focus:outline-none focus-visible:outline-none focus:ring-2 focus:ring-pumpkin/35 disabled:opacity-50';

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({className, ...p}, ref) {
  return <input ref={ref} autoComplete="off" className={cx(control, 'h-10 pointer-coarse:h-11 text-[0.9375rem]', className)} {...p} />;
});

export function Textarea({className, autoGrow, value, ...p}: TextareaHTMLAttributes<HTMLTextAreaElement> & {autoGrow?: boolean}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!autoGrow || !el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight + 2}px`;
  }, [value, autoGrow]);
  return <textarea ref={ref} value={value} className={cx(control, 'py-2.5 text-[0.9375rem] leading-relaxed', autoGrow && 'resize-none overflow-hidden', className)} {...p} />;
}

export function Select({className, children, ...p}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cx(control, 'h-10 pointer-coarse:h-11 pr-8 text-[0.9375rem]', className)} {...p}>
      {children}
    </select>
  );
}

/** Checkbox whose whole label is the hit target (no 13px dead zones). */
export function Check({label, hint, checked, onChange, id, disabled}: {label: ReactNode; hint?: ReactNode; checked: boolean; onChange: (v: boolean) => void; id?: string; disabled?: boolean}) {
  const auto = useId();
  const cid = id ?? auto;
  return (
    <label htmlFor={cid} className={cx('flex min-h-10 cursor-pointer items-start gap-3 rounded-md px-1 py-2 hover:bg-lab-800/60', disabled && 'cursor-not-allowed opacity-50')}>
      <input id={cid} type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} className="mt-0.5 size-5 shrink-0 accent-[var(--color-pumpkin)]" />
      <span className="min-w-0">
        <span className="block text-sm text-bone">{label}</span>
        {hint ? <span className="block text-[0.8125rem] text-fog">{hint}</span> : null}
      </span>
    </label>
  );
}

export function Switch({label, hint, checked, onChange, disabled}: {label: ReactNode; hint?: ReactNode; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean}) {
  const id = useId();
  return (
    <div className="flex min-h-11 items-center justify-between gap-4">
      <div className="min-w-0">
        <label htmlFor={id} className="block cursor-pointer text-sm font-semibold text-bone">{label}</label>
        {hint ? <p className="text-[0.8125rem] text-fog">{hint}</p> : null}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cx('relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border transition-colors duration-200 disabled:opacity-50', checked ? 'border-volt bg-volt-deep' : 'border-lab-400 bg-lab-900')}
      >
        <span className={cx('absolute size-5 rounded-full transition-transform duration-200', checked ? 'translate-x-6 bg-volt' : 'translate-x-1 bg-moss')} />
        <span className="sr-only">{checked ? 'On' : 'Off'}</span>
      </button>
    </div>
  );
}

/** Radio group drawn as a segmented control. */
export function Segmented<T extends string>({label, value, onChange, options, className}: {label: string; value: T; onChange: (v: T) => void; options: {value: T; label: ReactNode; hint?: ReactNode; icon?: LucideIcon}[]; className?: string}) {
  const name = useId();
  return (
    <div role="radiogroup" aria-label={label} className={cx('grid gap-1 rounded-lg border border-lab-600 bg-lab-950 p-1', className)} style={{gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))`}}>
      {options.map((o) => {
        const on = o.value === value;
        const Icon = o.icon;
        return (
          <label key={o.value} className={cx('flex min-h-10 min-w-0 cursor-pointer items-center justify-center gap-2 rounded-md px-3 py-2 text-center text-sm font-semibold transition-colors duration-150 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-pumpkin', on ? 'bg-lab-700 text-bone shadow-[inset_0_0_0_1px_var(--color-lab-400)]' : 'text-moss hover:text-bone')}>
            <input type="radio" name={name} value={o.value} checked={on} onChange={() => onChange(o.value)} className="sr-only" />
            {Icon ? <Icon aria-hidden className={cx('size-4 shrink-0', on && 'text-pumpkin')} /> : null}
            <span className="min-w-0">
              <span className="block">{o.label}</span>
              {o.hint ? <span className="block text-xs font-normal text-fog">{o.hint}</span> : null}
            </span>
          </label>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------ surfaces and status
export function Panel({title, action, children, className, id, description}: {title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; id?: string; description?: ReactNode}) {
  return (
    <section id={id} aria-labelledby={title && id ? `${id}-h` : undefined} className={cx('@container min-w-0 rounded-lg border border-lab-700 bg-lab-900 p-4 sm:p-6', className)}>
      {title ? (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 id={id ? `${id}-h` : undefined} className="text-lg font-semibold text-bone">{title}</h2>
            {description ? <p className="mt-1 text-sm text-moss">{description}</p> : null}
          </div>
          {action}
        </header>
      ) : null}
      {children}
    </section>
  );
}

export type Tone = 'volt' | 'pumpkin' | 'ghost' | 'blood' | 'candle' | 'neutral';
const TONES: Record<Tone, string> = {
  volt: 'border-volt/40 bg-volt-deep/60 text-volt',
  pumpkin: 'border-pumpkin/40 bg-pumpkin/10 text-pumpkin',
  ghost: 'border-ghost/40 bg-ghost-deep text-ghost',
  blood: 'border-blood/40 bg-blood-deep text-blood',
  candle: 'border-candle/40 bg-candle-deep text-candle',
  neutral: 'border-lab-500 bg-lab-800 text-moss',
};
const TONE_ICON: Partial<Record<Tone, LucideIcon>> = {volt: CircleCheck, blood: CircleX, candle: CircleExclamationPoint, ghost: Clock, neutral: Info};

/** Status chip: always an icon + a word, never colour alone. */
export function Badge({tone = 'neutral', icon, children, className}: {tone?: Tone; icon?: LucideIcon | null; children: ReactNode; className?: string}) {
  const Icon = icon === null ? null : icon ?? TONE_ICON[tone];
  return (
    <span className={cx('inline-flex h-6 max-w-full shrink-0 items-center gap-1 rounded-full border px-2 text-xs font-semibold whitespace-nowrap', TONES[tone], className)}>
      {Icon ? <Icon aria-hidden className="size-3.5 shrink-0" /> : null}
      <span className="truncate">{children}</span>
    </span>
  );
}

/** A tilted "specimen tag" label for styles: the lab's filing system. */
export function SpecimenTag({children, className}: {children: ReactNode; className?: string}) {
  return (
    <span className={cx('inline-flex h-6 max-w-full items-center rounded-sm border border-dashed border-lab-400 bg-lab-800 px-2 font-mono text-[0.75rem] text-moss', className)}>
      <span className="truncate">{children}</span>
    </span>
  );
}

export function EmptyState({art, title, children, action}: {art?: ReactNode; title: ReactNode; children?: ReactNode; action?: ReactNode}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-lab-600 px-6 py-10 text-center">
      {art}
      <h3 className="font-display text-2xl tracking-wide text-bone">{title}</h3>
      {children ? <p className="max-w-[44ch] text-sm text-moss">{children}</p> : null}
      {action}
    </div>
  );
}

export function Skeleton({className}: {className?: string}) {
  return <div aria-hidden className={cx('animate-pulse rounded-md bg-lab-800', className)} />;
}

export function Notice({tone = 'candle', title, children, action}: {tone?: Tone; title: ReactNode; children?: ReactNode; action?: ReactNode}) {
  const Icon = TONE_ICON[tone] ?? Info;
  return (
    <div role="status" className={cx('flex flex-wrap items-start gap-3 rounded-md border p-3 text-sm', TONES[tone])}>
      <Icon aria-hidden className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 flex-1 basis-60">
        <p className="font-semibold">{title}</p>
        {children ? <div className="mt-1 text-bone/90">{children}</div> : null}
      </div>
      {action}
    </div>
  );
}
