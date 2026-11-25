import {Clapperboard, FileText, Film, Send} from 'lucide-react';
import {useMemo, useState} from 'react';
import type {ProjectRow} from '../lib/api';
import {href} from '../lib/hooks';
import {styleImage, styleInfo} from '../lib/styles';
import {Badge, EmptyState, Panel, Skeleton, cx} from './ui';

/*
 * The creatures, sorted by how alive they are:
 *   On the slab  - a script exists, no video yet          -> opens it on the Operating Table (render page)
 *   Alive        - rendered, ready to upload               -> opens it in Dracula's Vault (library)
 *   Released     - published somewhere                     -> opens it in the Vault
 */
type Stage = ProjectRow['stage'];
const SHELVES: {stage: Stage; label: string; plain: string; icon: typeof FileText; empty: string}[] = [
  {stage: 'script', label: 'On the slab', plain: 'Scripts ready to render', icon: FileText, empty: 'No scripts waiting. Write one in the Laboratory.'},
  {stage: 'rendered', label: 'Alive', plain: 'Videos ready to upload', icon: Film, empty: 'Nothing rendered yet. Pull the lever on the Operating Table.'},
  {stage: 'published', label: 'Released', plain: 'Uploaded', icon: Send, empty: 'Nothing uploaded yet.'},
];
const LANG_TAG: Record<string, string> = {hindi: 'हिन्दी', hinglish: 'Hinglish'};
const len = (s: number) => (s < 60 ? `~${s}s` : `~${Math.round(s / 60)} min`);

export function hrefFor(p: ProjectRow) {
  return p.stage === 'script' ? href('render', {project: p.slug}) : href('library', {item: p.slug});
}

export function Shelf({rows, loading, current, title = 'Your creatures', description = 'Every script you have written, sorted by how alive it is.', start, className}: {rows: ProjectRow[] | null; loading: boolean; current?: string; title?: string; description?: string; start?: Stage; className?: string}) {
  const counts = useMemo(() => Object.fromEntries(SHELVES.map((s) => [s.stage, (rows ?? []).filter((r) => r.stage === s.stage).length])) as Record<Stage, number>, [rows]);
  const first = start ?? (counts.script ? 'script' : counts.rendered ? 'rendered' : 'script');
  const [tab, setTab] = useState<Stage | null>(null);
  const active = tab ?? first;
  const shelf = SHELVES.find((s) => s.stage === active)!;
  const list = (rows ?? []).filter((r) => r.stage === active);
  return (
    <Panel id="shelf" title={title} description={description} className={className}>
      <div role="tablist" aria-label="Project stage" className="mb-3 grid grid-cols-3 gap-1 rounded-lg border border-lab-600 bg-lab-950 p-1">
        {SHELVES.map((s) => (
          <button
            key={s.stage}
            role="tab"
            type="button"
            aria-selected={active === s.stage}
            aria-controls="shelf-list"
            onClick={() => setTab(s.stage)}
            title={s.plain}
            className={cx('flex min-h-11 min-w-0 items-center justify-center gap-1 rounded-md px-1 text-center text-sm font-semibold whitespace-nowrap transition-colors', active === s.stage ? 'bg-lab-700 text-bone shadow-[inset_0_0_0_1px_var(--color-lab-400)]' : 'text-moss hover:text-bone')}
          >
            <span>{s.label}</span>
            <span className="tabular text-xs font-normal text-fog">{rows ? counts[s.stage] : ''}</span>
          </button>
        ))}
      </div>
      <p className="mb-2 text-xs text-fog">{shelf.plain}: {active === 'script' ? 'opens on the Operating Table' : 'opens in Dracula\'s Vault'}</p>
      <div id="shelf-list" role="tabpanel" aria-label={shelf.plain}>
        {loading && !rows ? (
          <div className="flex flex-col gap-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-16" />)}</div>
        ) : list.length ? (
          <ul className="flex flex-col gap-2">
            {list.map((p) => (
              <li key={p.slug}>
                <a href={hrefFor(p)} aria-current={current === p.slug ? 'true' : undefined} className={cx('group flex min-w-0 items-center gap-3 rounded-md border p-2.5 transition-colors', current === p.slug ? 'border-pumpkin bg-lab-800' : 'border-lab-700 bg-lab-850 hover:border-lab-500')}>
                  <img src={styleImage(p.style)} alt="" width={36} height={48} loading="lazy" className="h-12 w-9 shrink-0 rounded-sm bg-lab-950 object-cover object-top p-0.5 ring-1 ring-lab-500" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold leading-snug text-bone [overflow-wrap:anywhere]">{p.title || p.slug}</span>
                    <span className="block text-xs text-fog">{[styleInfo(p.style).name, p.aspect_ratio, `${p.scenes} scenes`, len(p.duration_sec)].filter(Boolean).join(' · ')}</span>
                    <span className="mt-1.5 flex flex-wrap gap-1.5">
                      {LANG_TAG[p.language] ? <Badge tone="ghost">{LANG_TAG[p.language]}</Badge> : null}
                      {p.needs_approval ? <Badge tone="candle">Approve idea first</Badge> : null}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-1 text-xs font-semibold text-moss group-hover:text-pumpkin">
                    {p.stage === 'script' ? <><Clapperboard aria-hidden className="size-4" /><span className="hidden @sm:inline">Render</span></> : <><Film aria-hidden className="size-4" /><span className="hidden @sm:inline">Open</span></>}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState art={<shelf.icon aria-hidden className="size-8 text-fog" />} title={`${shelf.label}: empty`}>{shelf.empty}</EmptyState>
        )}
      </div>
    </Panel>
  );
}
