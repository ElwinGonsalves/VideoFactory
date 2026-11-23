import {ArrowLeft, BarChart3, CalendarClock, CircleX, ChevronLeft, ChevronRight, Clapperboard, Download, ExternalLink, Film, Link2, RefreshCw, Save, Search, Send, ShieldCheck, Wand} from 'lucide-react';
import {useEffect, useId, useMemo, useState} from 'react';
import {Overlay} from '../components/Overlay';
import {Badge, Button, Check, EmptyState, Field, Input, LinkButton, Notice, Panel, Select, Skeleton, SpecimenTag, Textarea, cx} from '../components/ui';
import {api, fileUrl, withToken, type Job, type LibraryItem, type LibraryPage, type Onboarding} from '../lib/api';
import {fmtDate, fmtNumber} from '../lib/format';
import {href, navigate, useApi, useMedia, useRoute} from '../lib/hooks';
import {useStudio} from '../lib/studio';
import {styleInfo} from '../lib/styles';

// ------------------------------------------------------------------ list
function List({selected, onPicked, autoPick}: {selected: string; onPicked: (slug: string) => void; autoPick?: boolean}) {
  const {act, watch} = useStudio();
  const [q, setQ] = useState('');
  const [qd, setQd] = useState('');
  const [style, setStyle] = useState('');
  const [aspect, setAspect] = useState('');
  const [page, setPage] = useState(1);
  const ids = {q: useId(), style: useId(), aspect: useId()};
  useEffect(() => {
    const t = window.setTimeout(() => {
      setQd(q);
      setPage(1);
    }, 250);
    return () => window.clearTimeout(t);
  }, [q]);
  const path = `/api/library?${new URLSearchParams({q: qd, style, aspect, page: String(page), per_page: '10'})}`;
  const {data, loading, error} = useApi<LibraryPage>(path);
  useEffect(() => {
    if (autoPick && !selected && data?.items[0]) onPicked(data.items[0].slug);
  }, [data, selected, onPicked, autoPick]);
  const sync = () => act(async () => watch(await api<Job>('/api/analytics/sync', {method: 'POST'}), 'Syncing views and likes'));
  return (
    <Panel id="lib-list" title="The vault" description={data ? `${data.total} video${data.total === 1 ? '' : 's'}, newest first` : 'Finished creatures'} action={<Button size="sm" variant="ghost" icon={BarChart3} onClick={sync}>Sync Analytics</Button>} className="lg:sticky lg:top-20">
      <div className="flex flex-col gap-3">
        <div className="relative">
          <label htmlFor={ids.q} className="sr-only">Search titles</label>
          <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fog" />
          <Input id={ids.q} type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search titles…" className="pl-9" />
        </div>
        <div className="grid grid-cols-1 gap-2 min-[1500px]:grid-cols-2">
          <div>
            <label htmlFor={ids.style} className="sr-only">Filter by style</label>
            <Select id={ids.style} value={style} onChange={(e) => { setStyle(e.target.value); setPage(1); }}>
              <option value="">All styles</option>
              {(data?.styles ?? []).map((s) => <option key={s} value={s}>{styleInfo(s).name}</option>)}
            </Select>
          </div>
          <div>
            <label htmlFor={ids.aspect} className="sr-only">Filter by aspect</label>
            <Select id={ids.aspect} value={aspect} onChange={(e) => { setAspect(e.target.value); setPage(1); }}>
              <option value="">All aspects</option>
              <option value="9:16">9:16</option>
              <option value="16:9">16:9</option>
              <option value="1:1">1:1</option>
            </Select>
          </div>
        </div>
        {error ? <Notice tone="blood" title={error.message}>{error.hint}</Notice> : null}
        {loading && !data ? (
          [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)
        ) : data?.items.length ? (
          <ul className="flex flex-col gap-2">
            {data.items.map((v) => (
              <li key={v.slug}>
                <a href={href('library', {item: v.slug})} onClick={(e) => { e.preventDefault(); onPicked(v.slug); }} aria-current={selected === v.slug ? 'true' : undefined} className={cx('flex min-w-0 items-start gap-3 rounded-md border p-2.5 transition-colors', selected === v.slug ? 'border-pumpkin bg-lab-800' : 'border-lab-700 bg-lab-850 hover:border-lab-500')}>
                  <Film aria-hidden className={cx('mt-0.5 size-5 shrink-0', selected === v.slug ? 'text-pumpkin' : 'text-fog')} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold leading-snug text-bone [overflow-wrap:anywhere] line-clamp-2">{v.title}</span>
                    <span className="block text-xs text-fog">{[v.style && styleInfo(v.style).name, v.aspect_ratio, fmtDate(v.mtime * 1000)].filter(Boolean).join(' · ')}</span>
                    <span className="mt-1.5 flex flex-wrap gap-1.5">
                      <Badge tone={v.qa_ok === false ? 'blood' : v.qa_ok ? 'volt' : 'neutral'}>{v.qa_ok == null ? 'QA n/a' : v.qa_ok ? 'QA pass' : 'QA issues'}</Badge>
                      {v.unverified ? <Badge tone="candle">{v.unverified} to verify</Badge> : null}
                    </span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState art={<Film aria-hidden className="size-8 text-fog" />} title={qd || style || aspect ? 'Nothing matches' : 'The vault is empty'} action={!(qd || style || aspect) ? <LinkButton href={href('create')} variant="secondary" icon={Clapperboard}>Create a video</LinkButton> : undefined}>
            {qd || style || aspect ? 'Try a different title or clear the filters.' : 'Rendered videos land here with their QA frames and fact checks.'}
          </EmptyState>
        )}
        {data && data.pages > 1 ? (
          <div className="flex items-center justify-between">
            <Button size="sm" variant="ghost" icon={ChevronLeft} disabled={page <= 1} onClick={() => setPage(page - 1)}>Newer</Button>
            <span className="text-xs text-fog tabular">Page {data.page} of {data.pages}</span>
            <Button size="sm" variant="ghost" disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Older <ChevronRight aria-hidden className="size-4" /></Button>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

// ------------------------------------------------------------------ player
function Player({item}: {item: LibraryItem}) {
  const wide = item.aspect_ratio === '16:9';
  const square = item.aspect_ratio === '1:1';
  const video = (
    <video key={item.slug} controls preload="metadata" playsInline className="block size-full bg-black object-contain" src={withToken(item.stream)} poster={item.thumbnail ? fileUrl(item.thumbnail) : undefined} aria-label={`Video: ${item.meta.title}`}>
      Your browser cannot play this MP4. Use Download instead.
    </video>
  );
  if (wide || square) {
    return <div className={cx('overflow-hidden rounded-lg border border-lab-600 bg-black', wide ? 'aspect-video' : 'mx-auto aspect-square max-w-md')}>{video}</div>;
  }
  // Phone bezel: the Short as a viewer sees it.
  return (
    <div className="mx-auto w-full max-w-[300px]">
      <div className="relative rounded-[2.25rem] border border-lab-500 bg-lab-950 p-2.5 shadow-lift">
        <span aria-hidden className="absolute top-3.5 left-1/2 z-10 h-4 w-20 -translate-x-1/2 rounded-full bg-lab-950" />
        <div className="aspect-[9/16] overflow-hidden rounded-[1.7rem] bg-black">{video}</div>
      </div>
    </div>
  );
}

function QaStrip({item, onZoom}: {item: LibraryItem; onZoom: (src: string, name: string) => void}) {
  if (!item.qa_frames.length) return <p className="text-sm text-moss">No QA frames for this video (this engine renders without the pixel check).</p>;
  return (
    <ul className="grid grid-cols-5 gap-2" aria-label="QA frames">
      {item.qa_frames.map((f) => {
        const r = item.qa?.frames.find((x) => x.frame === f.name);
        const bad = r && !r.ok;
        return (
          <li key={f.name} className="min-w-0">
            <button type="button" onClick={() => onZoom(fileUrl(bad && f.overlay ? f.overlay : f.src), f.name)} aria-label={`${f.name} frame${bad ? `: ${r.issues.join('; ')}` : ', passed'}. Enlarge`} className={cx('block w-full overflow-hidden rounded-md border-2 transition-[border-color,transform] duration-150 hover:-translate-y-0.5', bad ? 'border-blood' : r ? 'border-volt/60' : 'border-lab-600')}>
              <img src={fileUrl(f.src)} alt="" width={108} height={192} loading="lazy" className={cx('w-full bg-lab-950 object-cover', item.aspect_ratio === '16:9' ? 'aspect-video' : 'aspect-[9/16]')} />
            </button>
            <span className={cx('mt-1 flex items-center justify-center gap-0.5 text-xs', bad ? 'text-blood' : 'text-fog')}>{bad ? <CircleX aria-hidden className="size-3 shrink-0" /> : null}{f.name}</span>
          </li>
        );
      })}
    </ul>
  );
}

function PublishDialog({item, open, onClose, facts}: {item: LibraryItem; open: boolean; onClose: () => void; facts: string[]}) {
  const {act, watch, toast} = useStudio();
  const [platform, setPlatform] = useState('youtube');
  const [visibility, setVisibility] = useState('');
  const [headed, setHeaded] = useState(false);
  const [ack, setAck] = useState(false);
  const ids = {pl: useId(), vis: useId()};
  useEffect(() => setAck(false), [open]);
  const vis = visibility || item.meta.visibility || 'unlisted';
  const go = () =>
    act(async () => {
      const job = await api<Job>(`/api/library/${encodeURIComponent(item.slug)}/publish`, {method: 'POST', body: {platform, visibility, headed}});
      watch(job, `Uploading to ${platform}`, (s) => toast(s === 'done' ? `Posted to ${platform}. Paste the link below for analytics.` : `The ${platform} upload failed. Studio Activity has the log.`, s === 'done' ? 'ok' : 'err'));
      onClose();
    });
  return (
    <Overlay
      open={open}
      onClose={onClose}
      title="Publish this video"
      description="Read the summary; this posts for real."
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" icon={Send} disabled={facts.length > 0 && !ack} onClick={go}>Publish to {platform === 'youtube' ? 'YouTube' : platform === 'instagram' ? 'Instagram' : 'TikTok'}</Button></>}
    >
      <div className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Platform" htmlFor={ids.pl}>
            <Select id={ids.pl} value={platform} onChange={(e) => setPlatform(e.target.value)}>
              <option value="youtube">YouTube</option>
              <option value="instagram">Instagram</option>
              <option value="tiktok">TikTok</option>
            </Select>
          </Field>
          {platform === 'youtube' ? (
            <Field label="Visibility" htmlFor={ids.vis}>
              <Select id={ids.vis} value={visibility} onChange={(e) => setVisibility(e.target.value)}>
                <option value="">Default ({item.meta.visibility || 'unlisted'})</option>
                <option value="unlisted">Unlisted</option>
                <option value="private">Private</option>
                <option value="public">Public</option>
              </Select>
            </Field>
          ) : null}
        </div>
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 rounded-md border border-lab-700 bg-lab-850 p-3 text-sm">
          <dt className="text-fog">Title</dt><dd className="text-bone [overflow-wrap:anywhere]">{item.meta.title}</dd>
          <dt className="text-fog">Where</dt><dd className="text-bone">{platform}{platform === 'youtube' ? ` · ${vis}` : ''}</dd>
          <dt className="text-fog">Login</dt><dd className="text-bone">Account set in Settings (cookie or API)</dd>
          <dt className="text-fog">Facts</dt><dd className={facts.length ? 'text-candle' : 'text-volt'}>{facts.length ? `${facts.length} unverified` : 'All verified or none stated'}</dd>
        </dl>
        {facts.length ? <Check label="I checked the unverified facts myself" hint={facts.slice(0, 3).join(' · ')} checked={ack} onChange={setAck} /> : null}
        <Check label="Show the browser while uploading" hint="Recommended for your first upload." checked={headed} onChange={setHeaded} />
      </div>
    </Overlay>
  );
}

function Inspector({slug, onBack}: {slug: string; onBack?: () => void}) {
  const {act, watch, toast} = useStudio();
  const {data: item, error, loading, reload} = useApi<LibraryItem>(`/api/library/${encodeURIComponent(slug)}`, [slug]);
  const [meta, setMeta] = useState({title: '', description: '', hashtags: '', tags: ''});
  const [url, setUrl] = useState('');
  const [zoom, setZoom] = useState<{src: string; name: string} | null>(null);
  const [publish, setPublish] = useState(false);
  const [rerender, setRerender] = useState<string | null>(null);
  const ids = {t: useId(), d: useId(), h: useId(), g: useId(), u: useId()};
  useEffect(() => {
    if (!item) return;
    setMeta({title: item.meta.title ?? '', description: item.meta.description ?? '', hashtags: (item.meta.hashtags ?? []).join(' '), tags: (item.meta.tags ?? []).join(', ')});
    setUrl(item.published_url ?? '');
  }, [item]);
  const facts = useMemo(() => (item ? (item.claims.length ? item.claims.filter((c) => !c.verified).map((c) => c.text) : item.facts_to_verify) : []), [item]);

  if (error) return <Notice tone="blood" title={error.message}>{error.hint}</Notice>;
  if (loading || !item) return <Skeleton className="h-[640px]" />;
  const issues = (item.qa?.frames ?? []).flatMap((f) => f.issues.map((i) => `${f.frame}: ${i}`));
  const saveMeta = () =>
    act(async () => {
      await api(`/api/library/${encodeURIComponent(slug)}/meta`, {method: 'PUT', body: {title: meta.title, description: meta.description, hashtags: meta.hashtags.split(/[\s,]+/).filter(Boolean), tags: meta.tags.split(',').map((s) => s.trim()).filter(Boolean)}});
      toast('Metadata saved. It is kept on re-render.', 'ok');
    });
  const regen = () => act(async () => watch(await api<Job>(`/api/library/${encodeURIComponent(slug)}/metadata`, {method: 'POST'}), 'Writing titles and hashtags', () => void reload()));
  const doRerender = (aspect: string) =>
    act(async () => {
      setRerender(null);
      watch(await api<Job>(`/api/projects/${encodeURIComponent(slug)}/render`, {method: 'POST', body: {aspect}}), `Re-rendering as ${aspect}`, () => void reload());
    });
  const saveUrl = () => act(async () => { await api(`/api/projects/${encodeURIComponent(slug)}/published`, {method: 'PUT', body: {url}}); toast('Link saved for analytics.', 'ok'); });
  const other = item.aspect_ratio === '16:9' ? '9:16' : '16:9';

  return (
    <div className="flex min-w-0 flex-col gap-6">
      {onBack ? <Button variant="ghost" icon={ArrowLeft} onClick={onBack} className="self-start">All videos</Button> : null}
      <Panel id="inspector">
        <div className="grid gap-6 @[760px]:grid-cols-[300px_minmax(0,1fr)]">
          <div className={item.aspect_ratio === '16:9' ? '@[760px]:col-span-2' : ''}><Player item={item} /></div>
          <div className="flex min-w-0 flex-col gap-4">
            <div>
              <h2 className="text-xl font-semibold leading-snug text-bone [overflow-wrap:anywhere]">{item.meta.title}</h2>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <SpecimenTag>{styleInfo(item.style).name}</SpecimenTag>
                <Badge icon={null}>{item.aspect_ratio}</Badge>
                <Badge tone={item.qa ? (item.qa.ok ? 'volt' : 'blood') : 'neutral'}>{item.qa ? (item.qa.ok ? 'QA pass' : 'QA issues') : 'QA n/a'}</Badge>
                {item.stats ? <span className="text-xs text-moss tabular">{fmtNumber(item.stats.views)} views · {fmtNumber(item.stats.likes)} likes</span> : null}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <LinkButton href={withToken(item.download)} download={`${slug}.mp4`} variant="primary" icon={Download}>Download MP4</LinkButton>
              <Button icon={Send} onClick={() => setPublish(true)}>Publish Now</Button>
              <Button icon={CalendarClock} onClick={() => navigate('schedule', {pick: slug})}>Add to Schedule</Button>
              <Button variant="ghost" icon={RefreshCw} onClick={() => setRerender(other)}>Re-render {other}</Button>
            </div>
            {facts.length ? (
              <Notice tone="candle" title={`Fact check: ${facts.length} unverified`}>
                <p>{item.grounded ? 'Checked against web sources; these still need you.' : 'Not web-checked.'} Scheduled uploads are held as “needs review” until you approve.</p>
                <ul className="mt-1 list-disc pl-5">{facts.slice(0, 4).map((f) => <li key={f}>{f}</li>)}</ul>
                {facts.length > 4 ? <p className="mt-1 text-[0.8125rem]">and {facts.length - 4} more in the script editor.</p> : null}
              </Notice>
            ) : item.claims.length ? (
              <Notice tone="volt" title="Every numeric claim was verified against a cited source" />
            ) : null}
            {item.sources.length ? (
              <p className="text-sm text-moss">Sources: {item.sources.map((s, i) => <span key={s.url}>{i ? ' · ' : ''}<a className="text-pumpkin underline underline-offset-4" href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a></span>)}</p>
            ) : null}
            <div>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-bone"><ShieldCheck aria-hidden className="size-4 text-volt" />QA frames</h3>
              <QaStrip item={item} onZoom={(src, name) => setZoom({src, name})} />
              {issues.length ? <ul className="mt-2 text-sm text-blood">{issues.map((i) => <li key={i}>{i}</li>)}</ul> : null}
            </div>
          </div>
        </div>
      </Panel>

      <Panel id="meta" title="Upload metadata" description="Edits are kept when you re-render." action={<div className="flex flex-wrap gap-2"><Button size="sm" variant="ghost" icon={Wand} onClick={regen}>Regenerate with AI</Button><Button size="sm" icon={Save} onClick={saveMeta}>Save Metadata</Button></div>}>
        <div className="grid gap-4 @2xl:grid-cols-2">
          <Field label="Title" htmlFor={ids.t} hint={<span className="tabular">{meta.title.length}/100</span>} className="@2xl:col-span-2">
            <Input id={ids.t} maxLength={100} value={meta.title} onChange={(e) => setMeta({...meta, title: e.target.value})} />
          </Field>
          <Field label="Description" htmlFor={ids.d} className="@2xl:col-span-2">
            <Textarea id={ids.d} rows={4} autoGrow value={meta.description} onChange={(e) => setMeta({...meta, description: e.target.value})} />
          </Field>
          <Field label="Hashtags" htmlFor={ids.h} hint="Shown in the description, e.g. #shorts #business">
            <Input id={ids.h} spellCheck={false} value={meta.hashtags} onChange={(e) => setMeta({...meta, hashtags: e.target.value})} />
          </Field>
          <Field label="Search tags (YouTube only)" htmlFor={ids.g} hint="Hidden keywords, comma separated.">
            <Input id={ids.g} value={meta.tags} onChange={(e) => setMeta({...meta, tags: e.target.value})} />
          </Field>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end @2xl:col-span-2">
            <Field label="Published link" htmlFor={ids.u} optional hint="Lets Sync Analytics pull views and likes." className="flex-1">
              <Input id={ids.u} type="url" inputMode="url" spellCheck={false} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://youtube.com/shorts/…" />
            </Field>
            <Button icon={Link2} onClick={saveUrl} className="sm:mb-[1.6rem]">Save Link</Button>
            {item.published_url ? <LinkButton href={item.published_url} external variant="ghost" icon={ExternalLink} className="sm:mb-[1.6rem]">Open</LinkButton> : null}
          </div>
        </div>
      </Panel>

      <PublishDialog item={item} open={publish} onClose={() => setPublish(false)} facts={facts} />
      <Overlay open={Boolean(rerender)} onClose={() => setRerender(null)} title={`Re-render as ${rerender}?`} description="The current MP4 is replaced when the new one finishes." footer={<><Button variant="ghost" onClick={() => setRerender(null)}>Keep current</Button><Button variant="primary" icon={RefreshCw} onClick={() => rerender && doRerender(rerender)}>Re-render {rerender}</Button></>}>
        <p className="text-sm text-moss">About 3 minutes. Your metadata edits are kept. Download the current file first if you want both versions.</p>
      </Overlay>
      <Overlay open={Boolean(zoom)} onClose={() => setZoom(null)} title={`QA frame: ${zoom?.name ?? ''}`} description="Magenta marks content in a Shorts unsafe zone or touching the edge." wide>
        {zoom ? <img src={zoom.src} alt={`QA frame ${zoom.name}`} width={540} height={960} className="mx-auto max-h-[70dvh] w-auto rounded-md" /> : null}
      </Overlay>
    </div>
  );
}

export default function Library() {
  const route = useRoute();
  const {demo} = useStudio();
  const wide = useMedia('(min-width: 1024px)');
  const onboarding = useApi<Onboarding>(demo ? '/api/onboarding' : null);
  const item = route.params.get('item') ?? '';
  const pick = (slug: string) => navigate('library', {item: slug});
  useEffect(() => {
    if (demo && !item && onboarding.data?.demo.sample_short) pick(onboarding.data.demo.sample_short);
  }, [demo, item, onboarding.data]);
  if (!wide) {
    return item ? <Inspector slug={item} onBack={() => navigate('library')} /> : <List selected="" onPicked={(s) => pick(s)} />;
  }
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
      <List selected={item} onPicked={pick} autoPick />
      {item ? <Inspector slug={item} /> : <EmptyState title="Pick a video" art={<Film aria-hidden className="size-8 text-fog" />}>Choose one on the left to inspect it.</EmptyState>}
    </div>
  );
}
