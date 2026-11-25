import {Brain, Castle, CircleQuestionMark, Clapperboard, Ellipsis, ExternalLink, FlaskConical, FlaskRound, Moon, PanelLeftClose, PanelLeftOpen, Sheet, Skull, SlidersHorizontal, Sparkles, Spline, X, Zap, type LucideIcon} from 'lucide-react';
import {useEffect, useState, type ReactNode} from 'react';
import {href, useLocalFlag, useMedia, useRoute, type Page} from '../lib/hooks';
import {useStudio} from '../lib/studio';
import {StudioPill} from './Activity';
import {EnginesBadge} from './Engines';
import {ExorciseButton} from './Haunt';
import {Overlay} from './Overlay';
import {Button, cx} from './ui';

/*
 * The rooms of the lab. Each has a monster-movie name and keeps its plain name underneath, so a first-time
 * visitor never has to guess where "Library" went.
 *   Frankenstein (1931): the Laboratory, the Operating Table.  Dracula (1931): the Vault.
 *   The Others / seances: Ideas summoned from references.  Night of the Living Dead (1968): the Horde.
 *   The Wolf Man (1941): uploads at the Witching Hour.  Hocus Pocus (1993): the Apothecary's potions.
 */
export const NAV: {page: Page; label: string; plain: string; short: string; icon: LucideIcon; blurb: string}[] = [
  {page: 'create', label: 'The Laboratory', plain: 'Create', short: 'Lab', icon: FlaskConical, blurb: 'Write a new script'},
  {page: 'render', label: 'Operating Table', plain: 'Render', short: 'Table', icon: Clapperboard, blurb: 'Bring saved scripts to life'},
  {page: 'library', label: "Dracula's Vault", plain: 'Library', short: 'Vault', icon: Castle, blurb: 'Finished videos, ready to ship'},
  {page: 'ideas', label: 'The Séance', plain: 'Ideas', short: 'Séance', icon: Sparkles, blurb: 'Summon ideas and Style DNA'},
  {page: 'batch', label: 'The Horde', plain: 'Batch', short: 'Horde', icon: Sheet, blurb: 'Raise many videos from a sheet'},
  {page: 'schedule', label: 'Witching Hour', plain: 'Schedule', short: 'Hours', icon: Moon, blurb: 'Overnight uploads'},
  {page: 'settings', label: 'The Apothecary', plain: 'Settings', short: 'Potions', icon: SlidersHorizontal, blurb: 'Brains, voices, accounts'},
];
const MOBILE_MAIN: Page[] = ['create', 'render', 'library', 'ideas'];

function Logo({small}: {small?: boolean}) {
  return (
    <a href={href('create')} className="flex min-w-0 items-center gap-2.5 rounded-md" aria-label="video-factory home">
      <svg aria-hidden viewBox="0 0 32 32" className="size-8 shrink-0">
        <rect width="32" height="32" rx="8" fill="#0f1a13" stroke="#2d4034" />
        <path d="M6 21h20" stroke="#8ef0a6" strokeWidth="2" strokeDasharray="2 2.5" />
        <path d="M9 17.5v7M13 17.5v7M17 17.5v7M21 17.5v7" stroke="#8ef0a6" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M12 6.5v9l7.5-4.5z" fill="#ffa64d" />
      </svg>
      {!small ? (
        <span className="font-display text-2xl leading-none tracking-wide text-bone">
          video<span className="text-pumpkin">factory</span>
        </span>
      ) : null}
    </a>
  );
}

function NavLink({item, active, collapsed}: {item: (typeof NAV)[number]; active: boolean; collapsed: boolean}) {
  const Icon = item.icon;
  return (
    <a
      href={href(item.page)}
      aria-current={active ? 'page' : undefined}
      aria-label={`${item.label} (${item.plain})`}
      title={collapsed ? `${item.label} · ${item.plain}` : undefined}
      className={cx(
        'group flex min-h-11 min-w-0 items-center gap-3 rounded-md border px-3 py-1 text-[0.9375rem] font-semibold transition-[background-color,border-color,color] duration-150',
        collapsed && 'justify-center px-0',
        active ? 'border-lab-500 bg-lab-800 text-bone' : 'border-transparent text-moss hover:bg-lab-850 hover:text-bone',
      )}
    >
      <Icon aria-hidden className={cx('size-5 shrink-0 transition-colors', active ? 'text-pumpkin' : 'text-fog group-hover:text-moss')} />
      {!collapsed ? (
        <span className="min-w-0 leading-tight">
          <span className="block truncate">{item.label}</span>
          <span className="block truncate text-[0.6875rem] font-normal text-fog">{item.plain}</span>
        </span>
      ) : null}
    </a>
  );
}

function Sidebar({collapsed, onToggle, canToggle}: {collapsed: boolean; onToggle: () => void; canToggle: boolean}) {
  const route = useRoute();
  const {setOnboardingOpen} = useStudio();
  return (
    <aside className={cx('sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-lab-700 bg-lab-900 md:flex', collapsed ? 'w-16 px-2' : 'w-60 px-3')} aria-label="Primary">
      <div className={cx('flex h-16 items-center', collapsed ? 'justify-center' : 'px-1')}>
        <Logo small={collapsed} />
      </div>
      <nav aria-label="Main" className="flex flex-col gap-1">
        {NAV.map((n) => <NavLink key={n.page} item={n} active={route.page === n.page} collapsed={collapsed} />)}
      </nav>
      <div className="mt-auto flex flex-col gap-2 pb-4">
        <EnginesBadge collapsed={collapsed} />
        <button type="button" onClick={() => setOnboardingOpen(true)} aria-label="Setup guide" title={collapsed ? 'Setup guide' : undefined} className={cx('flex h-10 items-center gap-3 rounded-md px-3 text-sm text-moss hover:bg-lab-850 hover:text-bone', collapsed && 'justify-center px-0')}>
          <CircleQuestionMark aria-hidden className="size-5 shrink-0 text-fog" />
          {!collapsed ? 'Setup guide' : null}
        </button>
        {canToggle ? (
          <button type="button" onClick={onToggle} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} title={collapsed ? 'Expand sidebar' : undefined} className={cx('flex h-10 items-center gap-3 rounded-md px-3 text-sm text-moss hover:bg-lab-850 hover:text-bone', collapsed && 'justify-center px-0')}>
            {collapsed ? <PanelLeftOpen aria-hidden className="size-5 shrink-0" /> : <PanelLeftClose aria-hidden className="size-5 shrink-0" />}
            {!collapsed ? 'Collapse' : null}
          </button>
        ) : null}
      </div>
    </aside>
  );
}

function BottomNav() {
  const route = useRoute();
  const [more, setMore] = useState(false);
  const {setEnginesOpen, setOnboardingOpen} = useStudio();
  const moreActive = !MOBILE_MAIN.includes(route.page as Page);
  return (
    <>
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-lab-700 bg-lab-900/95 backdrop-blur [padding-bottom:env(safe-area-inset-bottom)] md:hidden">
        {NAV.filter((n) => MOBILE_MAIN.includes(n.page)).map((n) => {
          const active = route.page === n.page;
          const Icon = n.icon;
          return (
            <a key={n.page} href={href(n.page)} aria-label={`${n.label} (${n.plain})`} aria-current={active ? 'page' : undefined} className={cx('flex h-16 flex-col items-center justify-center gap-1 text-xs font-semibold', active ? 'text-bone' : 'text-moss')}>
              <Icon aria-hidden className={cx('size-5', active ? 'text-pumpkin' : 'text-fog')} />
              {n.short}
            </a>
          );
        })}
        <button type="button" onClick={() => setMore(true)} aria-haspopup="dialog" aria-expanded={more} className={cx('flex h-16 flex-col items-center justify-center gap-1 text-xs font-semibold', moreActive ? 'text-bone' : 'text-moss')}>
          <Ellipsis aria-hidden className={cx('size-5', moreActive ? 'text-pumpkin' : 'text-fog')} />
          More
        </button>
      </nav>
      <Overlay open={more} onClose={() => setMore(false)} variant="bottom" title="More of the lab">
        <div className="flex flex-col gap-1 pb-2">
          {NAV.filter((n) => !MOBILE_MAIN.includes(n.page)).map((n) => (
            <a key={n.page} href={href(n.page)} onClick={() => setMore(false)} aria-current={route.page === n.page ? 'page' : undefined} className="flex min-h-12 items-center gap-3 rounded-md px-3 text-bone hover:bg-lab-850">
              <n.icon aria-hidden className="size-5 text-pumpkin" />
              <span className="min-w-0">
                <span className="block font-semibold">{n.label} <span className="font-normal text-fog">· {n.plain}</span></span>
                <span className="block text-sm text-moss">{n.blurb}</span>
              </span>
            </a>
          ))}
          <button type="button" onClick={() => { setMore(false); setEnginesOpen(true); }} className="flex min-h-12 items-center gap-3 rounded-md px-3 text-left text-bone hover:bg-lab-850">
            <Spline aria-hidden className="size-5 text-volt" />
            <span className="font-semibold">Stitched Engines</span>
          </button>
          <button type="button" onClick={() => { setMore(false); setOnboardingOpen(true); }} className="flex min-h-12 items-center gap-3 rounded-md px-3 text-left text-bone hover:bg-lab-850">
            <CircleQuestionMark aria-hidden className="size-5 text-fog" />
            <span className="font-semibold">Setup guide</span>
          </button>
          <a href="/classic" className="flex min-h-12 items-center gap-3 rounded-md px-3 text-moss hover:bg-lab-850">
            <ExternalLink aria-hidden className="size-5 text-fog" />
            Classic UI
          </a>
        </div>
      </Overlay>
    </>
  );
}

function DemoBanner() {
  const {demo, setDemo} = useStudio();
  if (!demo) return null;
  return (
    <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-volt/30 bg-volt-deep/40 px-4 py-2 text-sm text-volt sm:px-6">
      <FlaskConical aria-hidden className="size-4 shrink-0" />
      <span className="min-w-0 flex-1 basis-56"><b>Judge Demo Mode.</b> <span className="text-bone/90">Exploring with sample data; anything labelled “sample” was not generated by you.</span></span>
      <Button size="sm" variant="ghost" icon={X} onClick={() => setDemo(false)} className="text-volt hover:text-bone">Exit demo</Button>
    </div>
  );
}

// Every room of the lab has its monster. Decorative: the h1 carries the name.
const EMBLEMS: Record<Page, {icon: LucideIcon; who: string; className?: string}> = {
  create: {icon: Zap, who: "Frankenstein's lab", className: 'emblem-flicker text-volt'},
  render: {icon: Clapperboard, who: 'The operating table', className: 'text-pumpkin'},
  ideas: {icon: Brain, who: 'The brain in the jar'},
  batch: {icon: Skull, who: 'The horde'},
  library: {icon: Castle, who: "Dracula's vault"},
  schedule: {icon: Moon, who: 'Werewolf hours', className: 'text-candle'},
  settings: {icon: FlaskRound, who: 'The potion shelf'},
};

function Emblem({page}: {page: Page}) {
  const e = EMBLEMS[page];
  return (
    <span key={page} title={e.who} aria-hidden className="emblem-in hidden size-9 shrink-0 place-items-center sm:grid rounded-full border border-dashed border-lab-400 bg-lab-850 text-bone shadow-[0_0_18px_-6px_rgb(194_173_255/0.6)]">
      <e.icon className={cx('size-[18px]', e.className)} />
    </span>
  );
}

export function Shell({title, page, children}: {title: string; page: Page; children: ReactNode}) {
  const tablet = useMedia('(min-width: 768px) and (max-width: 1023px)');
  const [userCollapsed, setUserCollapsed] = useLocalFlag('vf-rail');
  const collapsed = tablet || userCollapsed;
  const desktop = useMedia('(min-width: 768px)');
  // the sidebar's width, for overlays that sit just right of it (scroll ghost, page bolt)
  useEffect(() => {
    document.documentElement.style.setProperty('--vf-sb', desktop ? (collapsed ? '64px' : '240px') : '0px');
  }, [desktop, collapsed]);
  return (
    <div className="flex min-h-dvh">
      <a href="#main" className="sr-only z-50 rounded-md bg-pumpkin px-4 py-2 font-semibold text-pumpkin-ink focus:not-sr-only focus:fixed focus:top-3 focus:left-3">Skip to content</a>
      <Sidebar collapsed={collapsed} canToggle={!tablet} onToggle={() => setUserCollapsed(!userCollapsed)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-lab-700 bg-lab-950/90 px-4 backdrop-blur [padding-top:env(safe-area-inset-top)] sm:px-6">
          <span className="md:hidden"><Logo small /></span>
          <Emblem page={page} />
          <h1 className="min-w-0 flex-1 font-display text-2xl leading-none tracking-wide text-bone sm:text-3xl">
            <span className="sm:hidden">{NAV.find((n) => n.page === page)?.short ?? title}</span>
            <span className="hidden sm:inline">{title}</span>
          </h1>
          <ExorciseButton />
          <StudioPill />
        </header>
        <DemoBanner />
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1320px] min-w-0 flex-1 px-4 pt-6 pb-28 outline-none sm:px-6 md:pb-12">
          {children}
        </main>
      </div>
      <BottomNav />
    </div>
  );
}
