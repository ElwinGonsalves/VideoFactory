import {AnimatePresence, motion} from 'framer-motion';
import {useEffect, useMemo, useRef, useState} from 'react';
import {Ghost as GhostIcon, WandSparkles} from 'lucide-react';
import {useLocalFlag, useMedia, useReducedMotion, useRoute} from '../lib/hooks';
import {useStudio} from '../lib/studio';

/*
 * The haunting: authored moments, not wallpaper (DESIGN.md, "The Haunt Rule").
 *   - Bat burst: once, when the setup guide is finished (haunt('bats')).
 *   - It's alive!: a lightning strike when a render finishes (haunt('alive')).
 *   - Click zaps: forked sparks burst from primary buttons; other buttons get a volt ring.
 *   - Scroll ghosts: one drifts diagonally with your scroll, two circle; the header wand exorcises them.
 *   - Page bolt: a lightning strike into the page when you switch sections.
 *   - Candle light follows the pointer across the lab floor; fog drifts along the bottom.
 * Everything is pointer-events:none, aria-hidden, off under prefers-reduced-motion (except the
 * "It's alive!" words, which fade without movement), and off when Settings > System > Haunted effects is off.
 */

type Moment = 'bats' | 'alive';
export const haunt = (m: Moment) => window.dispatchEvent(new CustomEvent('vf:haunt', {detail: m}));

/** Effects are on unless the user chose a calm lab. */
export function useHaunted() {
  const [calm, setCalm] = useLocalFlag('vf-calm');
  const reduce = useReducedMotion();
  return {on: !calm, setOn: (v: boolean) => setCalm(!v), motion: !calm && !reduce, reduce};
}

const rand = (a: number, b: number) => a + Math.random() * (b - a);

// ------------------------------------------------------------------ shapes
export function BatShape({className}: {className?: string}) {
  // one silhouette, two wings that flap from the shoulders (see .bat-wing in index.css)
  return (
    <svg viewBox="0 0 64 32" className={className} aria-hidden>
      <g className="bat-wing bat-wing-l">
        <path d="M30 13 C26 7 19 4.5 11 6 C13 8 13.6 10 13 12.4 C10.6 11.4 7.4 11.6 4.6 13.4 C2.8 12.2 1.4 12 0 12.4 C4.4 15.6 7.2 19.6 8.4 24 C10.2 21.8 12.8 21 15.4 21.8 C16 19.4 18 18 20.4 18.4 C22 20.2 23.6 22.6 25.2 25.6 C26.6 21.8 28.4 17.8 30 15 Z" />
      </g>
      <g className="bat-wing bat-wing-r">
        <path d="M34 13 C38 7 45 4.5 53 6 C51 8 50.4 10 51 12.4 C53.4 11.4 56.6 11.6 59.4 13.4 C61.2 12.2 62.6 12 64 12.4 C59.6 15.6 56.8 19.6 55.6 24 C53.8 21.8 51.2 21 48.6 21.8 C48 19.4 46 18 43.6 18.4 C42 20.2 40.4 22.6 38.8 25.6 C37.4 21.8 35.6 17.8 34 15 Z" />
      </g>
      <path d="M32 8.5 L29.6 5.2 L30.2 9.4 C28.6 10.6 28 12.6 28.4 14.8 C28.8 18.6 30.2 21.6 32 23.4 C33.8 21.6 35.2 18.6 35.6 14.8 C36 12.6 35.4 10.6 33.8 9.4 L34.4 5.2 Z" />
    </svg>
  );
}

export function GhostShape({className, look = 0}: {className?: string; look?: number}) {
  return (
    <svg viewBox="0 0 40 48" className={className} aria-hidden>
      <path className="ghost-body" d="M20 2C9.5 2 4 10 4 19.5V44l5.3-4.2 5.4 4.2 5.3-4.2 5.3 4.2 5.4-4.2L36 44V19.5C36 10 30.5 2 20 2Z" />
      <g style={{transform: `translateY(${look}px)`, transition: 'transform 200ms'}}>
        <ellipse cx="14.5" cy="19" rx="2.6" ry="3.6" className="ghost-eye" />
        <ellipse cx="25.5" cy="19" rx="2.6" ry="3.6" className="ghost-eye" />
        <ellipse cx="20" cy="28.5" rx="2.4" ry="3" className="ghost-eye" />
      </g>
    </svg>
  );
}

// ------------------------------------------------------------------ bat burst (end of the setup guide)
type Bat = {id: number; x: number; y: number; r: number; s: number; d: number; delay: number};
function BatBurst() {
  const {motion: allowed} = useHaunted();
  const [bats, setBats] = useState<Bat[] | null>(null);
  useEffect(() => {
    const on = (e: Event) => {
      if ((e as CustomEvent<Moment>).detail !== 'bats' || !allowed) return;
      const far = Math.hypot(window.innerWidth, window.innerHeight) * 0.62;
      const n = window.innerWidth < 640 ? 16 : 28;
      setBats(
        Array.from({length: n}, (_, i) => {
          const a = (i / n) * Math.PI * 2 + rand(-0.25, 0.25);
          const dist = far * rand(0.6, 1.1);
          return {id: i, x: Math.cos(a) * dist, y: Math.sin(a) * dist * 0.8 - rand(40, 140), r: rand(-25, 25), s: rand(0.7, 1.5), d: rand(2, 2.9), delay: rand(0, 0.35)};
        }),
      );
      window.setTimeout(() => setBats(null), 3500);
    };
    window.addEventListener('vf:haunt', on);
    return () => window.removeEventListener('vf:haunt', on);
  }, [allowed]);
  return (
    <AnimatePresence>
      {bats ? (
        <motion.div key="bats" className="pointer-events-none fixed inset-0 z-[80] overflow-hidden" aria-hidden initial={{opacity: 1}} exit={{opacity: 0, transition: {duration: 0.3}}}>
          <motion.div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,transparent_0,rgb(5_8_6/0.55)_70%)]" initial={{opacity: 0}} animate={{opacity: [0, 1, 1, 0]}} transition={{duration: 3.2, times: [0, 0.1, 0.75, 1]}} />
          {/* the moon the bats burst out of */}
          <motion.div
            className="absolute top-1/2 left-1/2 size-56 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle_at_40%_38%,#fff7e0_0,#ffd88a_45%,#ffa64d_70%,transparent_72%)] shadow-[0_0_120px_40px_rgb(255_216_138/0.25)]"
            initial={{scale: 0.2, opacity: 0}}
            animate={{scale: [0.2, 1.05, 1, 1.6], opacity: [0, 1, 0.95, 0]}}
            transition={{duration: 3, times: [0, 0.12, 0.6, 1], ease: [0.16, 1, 0.3, 1]}}
          />
          {bats.map((b) => (
            <motion.div
              key={b.id}
              className="absolute top-1/2 left-1/2 -mt-4 -ml-8"
              initial={{x: 0, y: 0, scale: 0.15, opacity: 0, rotate: 0}}
              animate={{x: b.x, y: b.y, scale: [0.15, b.s, b.s * 1.15], opacity: [0, 1, 1, 0], rotate: b.r}}
              transition={{duration: b.d, delay: 0.25 + b.delay, ease: [0.45, 0.05, 0.55, 0.95], times: [0, 0.08, 0.85, 1]}}
            >
              <BatShape className="bat h-8 w-16" />
            </motion.div>
          ))}
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

// ------------------------------------------------------------------ "It's alive!" (a render finished)
function ItsAlive() {
  const {on, motion: allowed} = useHaunted();
  const [shot, setShot] = useState(0);
  useEffect(() => {
    const fire = (e: Event) => {
      if ((e as CustomEvent<Moment>).detail === 'alive' && on) setShot(Date.now());
    };
    window.addEventListener('vf:haunt', fire);
    return () => window.removeEventListener('vf:haunt', fire);
  }, [on]);
  useEffect(() => {
    if (!shot) return;
    const t = window.setTimeout(() => setShot(0), 1900);
    return () => window.clearTimeout(t);
  }, [shot]);
  return (
    <AnimatePresence>
      {shot ? (
        <motion.div key={shot} className="pointer-events-none fixed inset-0 z-[80] grid place-items-center overflow-hidden" aria-hidden exit={{opacity: 0, transition: {duration: 0.25}}}>
          {allowed ? (
            <>
              {/* one soft flash (never strobing), strongest at the top where the bolt lands */}
              <motion.div className="absolute inset-0 bg-[linear-gradient(to_bottom,rgb(194_173_255/0.32),rgb(142_240_166/0.08)_45%,transparent_75%)]" initial={{opacity: 0}} animate={{opacity: [0, 1, 0]}} transition={{duration: 0.6, times: [0, 0.12, 1]}} />
              <svg viewBox="0 0 400 300" preserveAspectRatio="none" className="absolute inset-x-0 top-0 h-[55dvh] w-full">
                <motion.polyline points="250,0 214,70 238,78 188,160 214,166 160,262" fill="none" stroke="#e9ffe9" strokeWidth="3" strokeLinejoin="round" initial={{pathLength: 0, opacity: 1}} animate={{pathLength: 1, opacity: [1, 1, 0]}} transition={{duration: 0.7, times: [0, 0.4, 1]}} style={{filter: 'drop-shadow(0 0 6px #8ef0a6) drop-shadow(0 0 18px #c2adff)'}} />
              </svg>
            </>
          ) : null}
          <motion.p
            className="font-display text-[clamp(3rem,11vw,8rem)] leading-none text-volt [text-shadow:0_0_24px_rgb(142_240_166/0.7),0_0_60px_rgb(142_240_166/0.35)]"
            initial={allowed ? {opacity: 0, scale: 0.85, rotate: -3} : {opacity: 0}}
            animate={allowed ? {opacity: [0, 1, 1, 0], scale: [0.85, 1.04, 1, 1.02], rotate: -3} : {opacity: [0, 1, 1, 0]}}
            transition={{duration: 1.7, times: [0, 0.14, 0.75, 1], ease: [0.16, 1, 0.3, 1]}}
          >
            It&rsquo;s alive!
          </motion.p>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

// ------------------------------------------------------------------ galvanic zap on clicks
// Primary buttons throw a small burst of forked sparks (the lab's current); others get a quick volt ring.
type Zap = {id: number; x: number; y: number; big: boolean; seed: number};
const BOLT = (len: number, seed: number) => {
  // a jagged 4-segment bolt pointing right, from (0,0) to (len,0)
  const j = (k: number) => ((Math.sin(seed * 12.9898 + k * 78.233) * 43758.5453) % 1) * 7;
  return `M0 0 L${len * 0.3} ${j(1)} L${len * 0.5} ${-j(2)} L${len * 0.75} ${j(3)} L${len} 0`;
};
function ClickZaps() {
  const {motion: allowed} = useHaunted();
  const [zaps, setZaps] = useState<Zap[]>([]);
  const seq = useRef(0);
  useEffect(() => {
    if (!allowed) return;
    const on = (e: MouseEvent) => {
      const el = (e.target as Element | null)?.closest<HTMLElement>('[data-variant]');
      if (!el || el.closest('[data-no-fx]') || (el as HTMLButtonElement).disabled) return;
      const r = el.getBoundingClientRect();
      const keyboard = e.detail === 0; // Enter / Space: start from the button's centre
      const id = ++seq.current;
      const z = {id, x: keyboard ? r.left + r.width / 2 : e.clientX, y: keyboard ? r.top + r.height / 2 : e.clientY, big: el.dataset.variant === 'primary', seed: Math.random() * 100};
      setZaps((s) => [...s.slice(-5), z]);
      window.setTimeout(() => setZaps((s) => s.filter((p) => p.id !== id)), 520);
    };
    document.addEventListener('click', on, true);
    return () => document.removeEventListener('click', on, true);
  }, [allowed]);
  if (!allowed) return null;
  return (
    <div className="pointer-events-none fixed inset-0 z-[90]" aria-hidden>
      {zaps.map((z) => (
        <div key={z.id} className="absolute" style={{left: z.x, top: z.y}}>
          <motion.span
            className="absolute -mt-6 -ml-6 size-12 rounded-full border-2 border-volt/80 shadow-[0_0_14px_rgb(142_240_166/0.55)]"
            initial={{scale: 0.15, opacity: 0.95}}
            animate={{scale: z.big ? 1.5 : 1.1, opacity: 0}}
            transition={{duration: 0.42, ease: 'easeOut'}}
          />
          {z.big
            ? Array.from({length: 6}, (_, i) => {
                const a = (i / 6) * 360 + z.seed;
                return (
                  <motion.svg
                    key={i}
                    width="44" height="16" viewBox="-2 -8 48 16"
                    className="absolute -mt-2 overflow-visible"
                    style={{rotate: a, transformOrigin: '0 50%'}}
                    initial={{opacity: 0, scaleX: 0.2}}
                    animate={{opacity: [0, 1, 1, 0], scaleX: [0.2, 1, 1, 1.15]}}
                    transition={{duration: 0.42, times: [0, 0.2, 0.6, 1], ease: 'easeOut'}}
                  >
                    <path d={BOLT(40, z.seed + i)} fill="none" stroke="#e9ffe9" strokeWidth="1.6" strokeLinejoin="round" style={{filter: 'drop-shadow(0 0 3px #8ef0a6) drop-shadow(0 0 6px #8ef0a6)'}} />
                  </motion.svg>
                );
              })
            : null}
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ the ghosts of scrolling (and how to banish them)
// While you scroll: a lead ghost drifts diagonally from the top-left toward the bottom-right as you go
// down the page, and two companions circle somewhere on screen. They vanish once scrolling stops.
// The header's Exorcise button turns the cursor into a wand; click each ghost to banish it for good.

const WAND_EVENT = 'vf:wand';
const setWand = (on: boolean) => window.dispatchEvent(new CustomEvent(WAND_EVENT, {detail: on}));
function useWand() {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const f = (e: Event) => setOn(Boolean((e as CustomEvent<boolean>).detail));
    window.addEventListener(WAND_EVENT, f);
    return () => window.removeEventListener(WAND_EVENT, f);
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle('wand-mode', on);
    if (!on) return;
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setWand(false);
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [on]);
  return on;
}

/** Header control: start the exorcism, or summon the ghosts back. */
export function ExorciseButton() {
  const {motion: allowed} = useHaunted();
  const [exorcised, setExorcised] = useLocalFlag('vf-exorcised');
  const wand = useWand();
  if (!allowed) return null;
  const label = exorcised ? 'Summon the ghosts back' : wand ? 'Put the wand away' : 'Exorcise the ghosts';
  return (
    <button
      type="button"
      onClick={() => (exorcised ? setExorcised(false) : setWand(!wand))}
      aria-label={label}
      aria-pressed={wand}
      title={label}
      className={cx(
        'grid size-10 shrink-0 place-items-center rounded-full border transition-[background-color,border-color,color,box-shadow] duration-200',
        wand ? 'border-ghost bg-ghost-deep text-ghost shadow-[0_0_18px_-4px_rgb(194_173_255/0.8)]' : 'border-lab-600 bg-lab-900 text-moss hover:border-ghost hover:text-ghost',
      )}
    >
      {exorcised ? <GhostIcon aria-hidden className="size-[18px]" /> : <WandSparkles aria-hidden className="size-[18px]" />}
    </button>
  );
}

type Orbit = {cx: number; cy: number; r: number; dur: number; dir: 1 | -1; phase: number};
const newOrbits = (): Orbit[] => {
  const w = window.innerWidth;
  const h = window.innerHeight;
  return [0, 1].map((i) => ({
    cx: (i === 0 ? rand(0.3, 0.5) : rand(0.6, 0.8)) * w,
    cy: rand(0.3, 0.7) * h,
    r: rand(70, 130),
    dur: rand(3.2, 4.6),
    dir: Math.random() > 0.5 ? 1 : -1,
    phase: rand(0, 360),
  }));
};

function ScrollGhosts() {
  const {motion: allowed} = useHaunted();
  const [exorcised, setExorcised] = useLocalFlag('vf-exorcised');
  const wand = useWand();
  const {toast} = useStudio();
  const [s, setS] = useState({show: false, p: 0, dir: 1});
  const [orbits, setOrbits] = useState<Orbit[]>(() => (typeof window === 'undefined' ? [] : newOrbits()));
  const [gone, setGone] = useState<number[]>([]); // ghosts banished in this exorcism
  const [puffs, setPuffs] = useState<{id: number; x: number; y: number}[]>([]);
  useEffect(() => {
    if (!allowed || exorcised) return;
    let y = window.scrollY;
    let hide = 0;
    let fresh = true;
    const on = () => {
      const dy = window.scrollY - y;
      y = window.scrollY;
      if (Math.abs(dy) < 1) return;
      if (fresh) setOrbits(newOrbits()); // each scroll session, the companions haunt a new spot
      fresh = false;
      const max = document.documentElement.scrollHeight - window.innerHeight;
      setS((o) => ({show: true, p: max > 0 ? Math.min(1, Math.max(0, y / max)) : 0, dir: Math.sign(dy) || o.dir}));
      window.clearTimeout(hide);
      hide = window.setTimeout(() => {
        fresh = true;
        setS((o) => ({...o, show: false}));
      }, 650);
    };
    window.addEventListener('scroll', on, {passive: true});
    return () => {
      window.removeEventListener('scroll', on);
      window.clearTimeout(hide);
    };
  }, [allowed, exorcised]);
  useEffect(() => {
    if (wand) {
      setGone([]);
      setOrbits(newOrbits());
    }
  }, [wand]);
  if (!allowed || exorcised) return null;
  const visible = wand || s.show;
  const banish = (i: number, e: React.MouseEvent) => {
    if (!wand) return;
    const id = Date.now() + i;
    setPuffs((p) => [...p, {id, x: e.clientX, y: e.clientY}]);
    window.setTimeout(() => setPuffs((p) => p.filter((x) => x.id !== id)), 900);
    const next = [...gone, i];
    setGone(next);
    if (next.length >= 3) {
      window.setTimeout(() => {
        setWand(false);
        setExorcised(true);
        toast('The lab is purified. Summon the ghosts back with the ghost button.', 'ok');
      }, 650);
    }
  };
  // lead ghost: top-left -> bottom-right across the page area, by scroll progress (centre of the page while exorcising)
  const p = wand ? 0.45 : s.p;
  const lead = {
    left: `calc(var(--vf-sb, 0px) + 24px + ${p} * (100vw - var(--vf-sb, 0px) - 120px))`,
    top: `calc(84px + ${p} * (100dvh - 84px - 170px))`,
  };
  const ghostBtn = 'pointer-events-auto rounded-full outline-none focus-visible:outline-2 focus-visible:outline-ghost';
  return (
    <div className={cx('fixed inset-0 z-[70]', wand ? 'pointer-events-auto bg-lab-950/35 backdrop-blur-[1px]' : 'pointer-events-none')} aria-hidden={!wand} onClick={wand ? () => undefined : undefined}>
      {wand ? <p className="pointer-events-none absolute top-20 left-1/2 -translate-x-1/2 rounded-md bg-lab-900/90 px-3 py-1.5 text-sm text-ghost shadow-[var(--shadow-lift)]">Click each ghost to banish it · {3 - gone.length} left · Esc to stop</p> : null}
      <AnimatePresence>
        {visible && !gone.includes(0) ? (
          <motion.button
            key="lead"
            type="button"
            tabIndex={wand ? 0 : -1}
            aria-label="Banish this ghost"
            onClick={(e) => banish(0, e)}
            className={cx('absolute', wand ? ghostBtn : 'pointer-events-none')}
            style={lead}
            initial={{opacity: 0, scale: 0.6}}
            animate={{opacity: 0.92, scale: 1, rotate: wand ? 0 : s.dir * 10}}
            exit={{opacity: 0, scale: gone.includes(0) ? 1.8 : 0.85, transition: {duration: 0.35}}}
            transition={{type: 'spring', stiffness: 160, damping: 22, opacity: {duration: 0.2}}}
          >
            <div className="ghost-bob"><GhostShape className="ghost h-14 w-12" look={wand ? 0 : s.dir * 2.5} /></div>
          </motion.button>
        ) : null}
        {visible
          ? orbits.map((o, k) =>
              gone.includes(k + 1) ? null : (
                <motion.div key={`orbit-${k}`} className="absolute" style={{left: o.cx, top: o.cy, width: 0, height: 0}} initial={{opacity: 0}} animate={{opacity: 1}} exit={{opacity: 0, transition: {duration: 0.35}}}>
                  <motion.div className="absolute" style={{width: 0, height: 0}} initial={{rotate: o.phase}} animate={{rotate: o.phase + 360 * o.dir}} transition={{duration: o.dur, ease: 'linear', repeat: Infinity}}>
                    <motion.button
                      type="button"
                      tabIndex={wand ? 0 : -1}
                      aria-label="Banish this ghost"
                      onClick={(e) => banish(k + 1, e)}
                      className={cx('absolute -mt-5 -ml-4', wand ? ghostBtn : 'pointer-events-none')}
                      style={{left: o.r}}
                      animate={{rotate: -(o.phase + 360 * o.dir)}}
                      transition={{duration: o.dur, ease: 'linear', repeat: Infinity}}
                    >
                      <GhostShape className="ghost h-10 w-8 opacity-80" />
                    </motion.button>
                  </motion.div>
                </motion.div>
              ),
            )
          : null}
      </AnimatePresence>
      {puffs.map((pf) => (
        <div key={pf.id} className="pointer-events-none absolute" style={{left: pf.x, top: pf.y}}>
          {Array.from({length: 10}, (_, i) => {
            const a = (i / 10) * Math.PI * 2;
            return <motion.span key={i} className="absolute -mt-1 -ml-1 size-2 rounded-full bg-ghost shadow-[0_0_8px_#c2adff]" initial={{x: 0, y: 0, opacity: 1, scale: 1}} animate={{x: Math.cos(a) * 46, y: Math.sin(a) * 46, opacity: 0, scale: 0.3}} transition={{duration: 0.6, ease: 'easeOut'}} />;
          })}
          <motion.span className="absolute -top-10 -left-10 w-20 text-center font-display text-xl text-ghost" initial={{opacity: 0, y: 4}} animate={{opacity: [0, 1, 0], y: -18}} transition={{duration: 0.85}}>Begone!</motion.span>
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ lightning between rooms (page switches)
function PageBolt() {
  const {motion: allowed} = useHaunted();
  const route = useRoute();
  const first = useRef(true);
  const [shot, setShot] = useState(0);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (allowed) setShot(Date.now());
  }, [route.page, allowed]);
  useEffect(() => {
    if (!shot) return;
    const t = window.setTimeout(() => setShot(0), 650);
    return () => window.clearTimeout(t);
  }, [shot]);
  // a fresh jagged path each strike, from the header down into the page
  const d = useMemo(() => {
    const pts: string[] = [];
    let x = 40 + Math.random() * 20;
    for (let i = 0; i <= 6; i++) {
      pts.push(`${x.toFixed(1)},${(i * 100) / 6}`);
      x += (Math.random() - 0.5) * 14;
    }
    return pts.join(' ');
  }, [shot]);
  return (
    <AnimatePresence>
      {shot ? (
        <motion.div key={shot} className="pointer-events-none fixed inset-x-0 top-16 bottom-0 z-[60] md:left-[var(--vf-sb,0px)]" aria-hidden exit={{opacity: 0, transition: {duration: 0.15}}}>
          <motion.div className="absolute inset-0 bg-[radial-gradient(60%_45%_at_50%_0%,rgb(194_173_255/0.22),rgb(142_240_166/0.06)_55%,transparent_80%)]" initial={{opacity: 0}} animate={{opacity: [0, 1, 0.3, 0.8, 0]}} transition={{duration: 0.5, times: [0, 0.12, 0.3, 0.42, 1]}} />
          {/* the bolt is revealed top-down (clip), then flickers out; a wide soft stroke is its glow */}
          <motion.svg
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            className="absolute inset-x-0 top-0 h-[46%] w-full"
            initial={{clipPath: 'inset(0 0 100% 0)', opacity: 1}}
            animate={{clipPath: 'inset(0 0 0% 0)', opacity: [1, 1, 0.4, 1, 0]}}
            transition={{clipPath: {duration: 0.16, ease: 'easeIn'}, opacity: {duration: 0.5, times: [0, 0.4, 0.55, 0.68, 1]}}}
          >
            <polyline points={d} fill="none" stroke="#8ef0a6" strokeOpacity="0.35" strokeWidth="10" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
            <polyline points={d} fill="none" stroke="#c2adff" strokeOpacity="0.7" strokeWidth="4" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
            <polyline points={d} fill="none" stroke="#f6fff6" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
          </motion.svg>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

// ------------------------------------------------------------------ candle light + fog on the lab floor
function Atmosphere() {
  const {on, motion: allowed} = useHaunted();
  const fine = useMedia('(pointer: fine)');
  const lamp = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!allowed || !fine) return;
    let raf = 0;
    const move = (e: PointerEvent) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        lamp.current?.style.setProperty('--lx', `${e.clientX}px`);
        lamp.current?.style.setProperty('--ly', `${e.clientY}px`);
      });
    };
    window.addEventListener('pointermove', move, {passive: true});
    return () => {
      window.removeEventListener('pointermove', move);
      cancelAnimationFrame(raf);
    };
  }, [allowed, fine]);
  if (!on) return null;
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden>
      {allowed && fine ? <div ref={lamp} className="absolute inset-0 [background:radial-gradient(520px_circle_at_var(--lx,70%)_var(--ly,-10%),rgb(255_166_77/0.10),transparent_70%)]" /> : null}
      <div className={cx('fog fog-a', !allowed && 'fog-still')} />
      <div className={cx('fog fog-b', !allowed && 'fog-still')} />
    </div>
  );
}
const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ');

/** Mount once, at the app root. */
export function Haunt() {
  return (
    <>
      <Atmosphere />
      <ScrollGhosts />
      <ClickZaps />
      <PageBolt />
      <BatBurst />
      <ItsAlive />
    </>
  );
}
