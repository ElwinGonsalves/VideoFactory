import {Bell, Brain, CircleQuestionMark, ExternalLink, Film, KeyRound, LineChart, LogIn, Radio, Save, ShieldCheck, Stethoscope, TestTube, Upload, Users} from 'lucide-react';
import {useEffect, useId, useState, type ReactNode} from 'react';
import {Badge, Button, Check, Field, Input, LinkButton, Notice, Panel, Segmented, Select, Skeleton, cx} from '../components/ui';
import {api, type Job, type Options} from '../lib/api';
import {fmtNumber, platformName, titleCase} from '../lib/format';
import {href, useApi, useRoute} from '../lib/hooks';
import {useStudio} from '../lib/studio';
import {styleInfo} from '../lib/styles';

type EnvView = Record<string, {set: boolean; value: string}>;
type Prefs = {
  llm: Record<string, string | number | boolean | Record<string, {input: number; output: number}>>;
  defaults: Record<string, string | number>;
  publish: Record<string, {method?: string; account?: string; visibility?: string}>;
  analytics?: {weekly?: boolean; channel_url?: string};
};
type SettingsData = {prefs: Prefs; env: EnvView; cookie_accounts: string[]; api_status: Record<string, Record<string, boolean>>};
type Usage = {month: string; calls: number; input_tokens: number; output_tokens: number; spend_inr: number; limit_inr: number; usd_inr: number; tier: string; prices: Record<string, {input: number; output: number}>};

const SECTIONS: {id: string; label: string; icon: typeof Brain}[] = [
  {id: 'model', label: 'Brain & spend', icon: Brain},
  {id: 'defaults', label: 'Video defaults', icon: Film},
  {id: 'accounts', label: 'Publishing accounts', icon: Users},
  {id: 'alerts', label: 'Alerts', icon: Bell},
  {id: 'analytics', label: 'Analytics', icon: LineChart},
  {id: 'system', label: 'System', icon: Stethoscope},
];

/** A secret field: shows whether it is saved as a status, never as a fake value in the box. */
function Secret({name, label, env, value, onChange, hint}: {name: string; label: string; env: EnvView; value: string; onChange: (v: string) => void; hint?: ReactNode}) {
  const id = useId();
  const e = env[name];
  return (
    <Field label={<span className="flex flex-wrap items-center gap-2">{label}{e?.set ? <Badge tone="volt">Saved {e.value}</Badge> : <Badge icon={null}>Not set</Badge>}</span>} htmlFor={id} hint={hint}>
      <Input id={id} type="password" name={name.toLowerCase()} spellCheck={false} autoComplete="off" value={value} onChange={(ev) => onChange(ev.target.value)} placeholder={e?.set ? 'Paste a new value to replace it…' : 'Paste it here…'} />
    </Field>
  );
}

function Plain({name, label, env, value, onChange, placeholder, hint}: {name: string; label: string; env: EnvView; value: string; onChange: (v: string) => void; placeholder?: string; hint?: ReactNode}) {
  const id = useId();
  return (
    <Field label={label} htmlFor={id} hint={hint}>
      <Input id={id} spellCheck={false} value={value} onChange={(e) => onChange(e.target.value)} placeholder={env[name]?.value || placeholder} />
    </Field>
  );
}

function useSecrets() {
  const [vals, setVals] = useState<Record<string, string>>({});
  const set = (k: string) => (v: string) => setVals((s) => ({...s, [k]: v}));
  const save = async (keys: string[]) => {
    const body = Object.fromEntries(keys.filter((k) => vals[k]?.trim()).map((k) => [k, vals[k].trim()]));
    if (Object.keys(body).length) await api('/api/settings/secrets', {method: 'PUT', body});
    setVals((s) => Object.fromEntries(Object.entries(s).filter(([k]) => !keys.includes(k))));
    return Object.keys(body).length;
  };
  return {vals, set, save};
}

function ModelSection({s, reload}: {s: SettingsData; reload: () => void}) {
  const {act, watch, toast} = useStudio();
  const llm = s.prefs.llm;
  const [provider, setProvider] = useState(String(llm.provider));
  const [models, setModels] = useState({gemini_model: String(llm.gemini_model ?? ''), ollama_model: String(llm.ollama_model ?? ''), openai_model: String(llm.openai_model ?? '')});
  const sec = useSecrets();
  const usage = useApi<Usage>('/api/usage');
  const [spend, setSpend] = useState({tier: 'free', limit: 100, rate: 85, pin: 0, pout: 0});
  useEffect(() => {
    if (!usage.data) return;
    const p = usage.data.prices[models.gemini_model] ?? Object.values(usage.data.prices)[0] ?? {input: 0, output: 0};
    setSpend({tier: usage.data.tier, limit: usage.data.limit_inr, rate: usage.data.usd_inr, pin: p.input, pout: p.output});
  }, [usage.data, models.gemini_model]);
  const ids = {prov: useId(), gm: useId(), om: useId(), oam: useId(), limit: useId(), rate: useId(), pin: useId(), pout: useId()};
  const save = () =>
    act(async () => {
      await api('/api/settings/prefs', {method: 'PUT', body: {llm: {provider, ...models}}});
      await sec.save(['GEMINI_API_KEY', 'OLLAMA_HOST', 'OPENAI_BASE_URL', 'OPENAI_API_KEY']);
      toast('Brain settings saved. Keys stay in your local .env.', 'ok');
      reload();
    });
  const saveSpend = () =>
    act(async () => {
      await api('/api/settings/prefs', {method: 'PUT', body: {llm: {gemini_tier: spend.tier, spend_limit_inr: spend.limit, usd_inr: spend.rate, prices: {[models.gemini_model]: {input: spend.pin, output: spend.pout}}}}});
      toast('Spend settings saved.', 'ok');
      void usage.reload();
    });
  const u = usage.data;
  const pct = u && u.limit_inr ? Math.min(100, (u.spend_inr / u.limit_inr) * 100) : 0;
  return (
    <Panel id="model" title="Brain & spend" description="The language model writes scripts, ideas, titles and reads reference frames.">
      <div className="flex flex-col gap-4">
        <Field label="Provider" htmlFor={ids.prov}>
          <Select id={ids.prov} value={provider} onChange={(e) => setProvider(e.target.value)}>
            <option value="gemini">Gemini (free tier, default)</option>
            <option value="ollama">Ollama (offline on this PC)</option>
            <option value="openai">OpenAI-compatible endpoint</option>
          </Select>
        </Field>
        {provider === 'gemini' ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Secret name="GEMINI_API_KEY" label="Gemini API key" env={s.env} value={sec.vals.GEMINI_API_KEY ?? ''} onChange={sec.set('GEMINI_API_KEY')} hint={<>Free at <a className="text-pumpkin underline underline-offset-4" href="https://aistudio.google.com/api-keys" target="_blank" rel="noopener noreferrer">aistudio.google.com</a></>} />
            <Field label="Model" htmlFor={ids.gm}><Input id={ids.gm} spellCheck={false} value={models.gemini_model} onChange={(e) => setModels({...models, gemini_model: e.target.value})} /></Field>
          </div>
        ) : provider === 'ollama' ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Plain name="OLLAMA_HOST" label="Ollama host" env={s.env} value={sec.vals.OLLAMA_HOST ?? ''} onChange={sec.set('OLLAMA_HOST')} placeholder="http://127.0.0.1:11434" />
            <Field label="Model" htmlFor={ids.om} hint="Run `ollama pull` for it first."><Input id={ids.om} spellCheck={false} value={models.ollama_model} onChange={(e) => setModels({...models, ollama_model: e.target.value})} /></Field>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <Plain name="OPENAI_BASE_URL" label="Base URL" env={s.env} value={sec.vals.OPENAI_BASE_URL ?? ''} onChange={sec.set('OPENAI_BASE_URL')} placeholder="https://api.openai.com/v1" />
            <Field label="Model" htmlFor={ids.oam}><Input id={ids.oam} spellCheck={false} value={models.openai_model} onChange={(e) => setModels({...models, openai_model: e.target.value})} /></Field>
            <Secret name="OPENAI_API_KEY" label="API key" env={s.env} value={sec.vals.OPENAI_API_KEY ?? ''} onChange={sec.set('OPENAI_API_KEY')} />
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" icon={Save} onClick={save}>Save Brain Settings</Button>
          <Button icon={TestTube} onClick={() => act(async () => watch(await api<Job>('/api/settings/test-llm', {method: 'POST'}), 'Testing the language model'))}>Test Connection</Button>
          {provider === 'gemini' ? <Button variant="ghost" onClick={() => act(async () => watch(await api<Job>('/api/settings/gemini-models', {method: 'POST'}), 'Listing Gemini models'))}>List Gemini Models</Button> : null}
        </div>

        <div className="mt-2 border-t border-lab-700 pt-5">
          <h3 className="font-semibold text-bone">Gemini spend this month</h3>
          {u ? (
            <>
              <p className="mt-1 text-sm text-moss tabular">
                {fmtNumber(u.calls)} calls · {fmtNumber(u.input_tokens)} input + {fmtNumber(u.output_tokens)} output tokens · about <b className="text-bone">₹{u.spend_inr.toFixed(2)}</b> of ₹{u.limit_inr}
              </p>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-lab-800" role="progressbar" aria-label="Spend against the monthly limit" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}>
                <div className={cx('h-full rounded-full', pct >= 90 ? 'bg-blood' : pct >= 60 ? 'bg-candle' : 'bg-volt')} style={{width: `${pct}%`}} />
              </div>
              {u.tier === 'free' ? <p className="mt-2 text-[0.8125rem] text-fog">Free tier costs ₹0; the limit is not enforced. Switch to Paid to let the limit pause batches.</p> : null}
            </>
          ) : <Skeleton className="mt-2 h-10" />}
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <div className="sm:col-span-2 lg:col-span-1">
              <Segmented label="Gemini plan" value={spend.tier} onChange={(v) => setSpend({...spend, tier: v})} options={[{value: 'free', label: 'Free'}, {value: 'paid', label: 'Paid'}]} />
            </div>
            <Field label="Stop limit (₹ / month)" htmlFor={ids.limit}><Input id={ids.limit} type="number" inputMode="decimal" min={0} step={10} value={spend.limit} onChange={(e) => setSpend({...spend, limit: Number(e.target.value)})} /></Field>
            <Field label="USD to INR" htmlFor={ids.rate}><Input id={ids.rate} type="number" inputMode="decimal" min={1} step={0.5} value={spend.rate} onChange={(e) => setSpend({...spend, rate: Number(e.target.value)})} /></Field>
            <Field label="$ per 1M input" htmlFor={ids.pin}><Input id={ids.pin} type="number" inputMode="decimal" min={0} step={0.05} value={spend.pin} onChange={(e) => setSpend({...spend, pin: Number(e.target.value)})} /></Field>
            <Field label="$ per 1M output" htmlFor={ids.pout}><Input id={ids.pout} type="number" inputMode="decimal" min={0} step={0.05} value={spend.pout} onChange={(e) => setSpend({...spend, pout: Number(e.target.value)})} /></Field>
          </div>
          <Button className="mt-3" icon={Save} onClick={saveSpend}>Save Spend Settings</Button>
        </div>
      </div>
    </Panel>
  );
}

function DefaultsSection({s, opts}: {s: SettingsData; opts: Options | null}) {
  const {act, toast} = useStudio();
  const [d, setD] = useState(() => ({...s.prefs.defaults}));
  const set = (k: string) => (v: string | number) => setD((x) => ({...x, [k]: v}));
  const ids = {niche: useId(), lang: useId(), eng: useId(), voice: useId(), rate: useId(), style: useId(), aspect: useId(), mood: useId(), len: useId()};
  return (
    <Panel id="defaults" title="Video defaults" description="Used whenever a form, sheet row or schedule job leaves something empty.">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Channel niche" htmlFor={ids.niche} hint="Steers brainstorms."><Input id={ids.niche} value={String(d.niche ?? '')} onChange={(e) => set('niche')(e.target.value)} placeholder="e.g. business case studies…" /></Field>
        <Field label="Language" htmlFor={ids.lang}><Input id={ids.lang} value={String(d.language ?? '')} onChange={(e) => set('language')(e.target.value)} /></Field>
        <Field label="Voice engine" htmlFor={ids.eng}>
          <Select id={ids.eng} value={String(d.voice_engine ?? 'edge-tts')} onChange={(e) => set('voice_engine')(e.target.value)}>
            <option value="edge-tts">Edge-TTS (online, free)</option>
            <option value="kokoro">Kokoro (local GPU)</option>
          </Select>
        </Field>
        <Field label="Voice" htmlFor={ids.voice} hint="e.g. en-US-AndrewNeural or af_heart"><Input id={ids.voice} spellCheck={false} value={String(d.voice ?? '')} onChange={(e) => set('voice')(e.target.value)} /></Field>
        <Field label="Speaking rate" htmlFor={ids.rate} hint="e.g. +5%"><Input id={ids.rate} spellCheck={false} value={String(d.rate ?? '')} onChange={(e) => set('rate')(e.target.value)} /></Field>
        <Field label="Length (seconds)" htmlFor={ids.len}><Input id={ids.len} type="number" inputMode="numeric" min={15} max={1800} value={Number(d.target_duration_sec ?? 50)} onChange={(e) => set('target_duration_sec')(Number(e.target.value))} /></Field>
        <Field label="Style" htmlFor={ids.style}>
          <Select id={ids.style} value={String(d.style ?? '')} onChange={(e) => set('style')(e.target.value)}>
            {(opts?.styles ?? [String(d.style)]).map((st) => <option key={st} value={st}>{styleInfo(st).name}</option>)}
          </Select>
        </Field>
        <Field label="Aspect" htmlFor={ids.aspect}>
          <Select id={ids.aspect} value={String(d.aspect_ratio ?? '9:16')} onChange={(e) => set('aspect_ratio')(e.target.value)}>
            {['9:16', '16:9', '1:1'].map((a) => <option key={a} value={a}>{a}</option>)}
          </Select>
        </Field>
        <Field label="Music mood" htmlFor={ids.mood}>
          <Select id={ids.mood} value={String(d.music_mood ?? 'documentary')} onChange={(e) => set('music_mood')(e.target.value)}>
            {(opts?.moods ?? ['documentary']).map((m) => <option key={m} value={m}>{titleCase(m)}</option>)}
          </Select>
        </Field>
      </div>
      <Button className="mt-4" variant="primary" icon={Save} onClick={() => act(async () => { await api('/api/settings/prefs', {method: 'PUT', body: {defaults: d}}); toast('Defaults saved.', 'ok'); })}>Save Defaults</Button>
    </Panel>
  );
}

const PLATFORM_FIELDS: Record<string, [string, string, boolean][]> = {
  youtube: [['YOUTUBE_CLIENT_ID', 'Client ID', true], ['YOUTUBE_CLIENT_SECRET', 'Client secret', true], ['YOUTUBE_ACCESS_TOKEN', 'Access token', true]],
  instagram: [['INSTAGRAM_CLIENT_ID', 'App (client) ID', true], ['INSTAGRAM_CLIENT_SECRET', 'App secret', true], ['INSTAGRAM_USER_ID', 'Instagram user ID', false], ['INSTAGRAM_ACCESS_TOKEN', 'Access token', true]],
  tiktok: [['TIKTOK_CLIENT_KEY', 'Client key', true], ['TIKTOK_CLIENT_SECRET', 'Client secret', true], ['TIKTOK_ACCESS_TOKEN', 'Access token', true]],
};
const API_NOTES: Record<string, string> = {
  youtube: 'API uploads stay private until Google audits your project (about 6 a day).',
  instagram: 'Needs a Business or Creator account and a Meta app.',
  tiktok: 'Unaudited apps can only post privately (SELF_ONLY).',
};

function PlatformCard({platform, s, reload}: {platform: string; s: SettingsData; reload: () => void}) {
  const {act, watch, toast} = useStudio();
  const cfg = s.prefs.publish[platform] ?? {};
  const [method, setMethod] = useState(cfg.method ?? 'cookie');
  const [account, setAccount] = useState(cfg.account ?? 'main');
  const sec = useSecrets();
  const accId = useId();
  const fileId = useId();
  const hasCookie = s.cookie_accounts.includes(`${platform}_${account}`);
  const saveMethod = (m: string) => act(async () => { setMethod(m); await api('/api/settings/prefs', {method: 'PUT', body: {publish: {[platform]: {method: m, account: account.trim() || 'main'}}}}); reload(); });
  const login = () => act(async () => watch(await api<Job>('/api/settings/login', {method: 'POST', body: {platform, account}}), `${platformName(platform)} login: a browser opens; sign in, then close it`, reload));
  const check = () => act(async () => watch(await api<Job>('/api/settings/check', {method: 'POST', body: {platform, account}}), `Checking the ${platformName(platform)} session`, reload));
  const saveApi = () => act(async () => { const n = await sec.save(PLATFORM_FIELDS[platform].map(([k]) => k)); toast(n ? 'Saved to your local .env.' : 'Nothing new to save.', n ? 'ok' : 'info'); reload(); });
  const test = () => act(async () => watch(await api<Job>('/api/settings/test-platform', {method: 'POST', body: {platform}}), `Testing the ${platformName(platform)} API`));
  const uploadClient = (f: File) => act(async () => { const fd = new FormData(); fd.append('file', f); await api('/api/settings/youtube-client', {method: 'POST', body: fd}); toast('client_secret.json saved.', 'ok'); reload(); });
  return (
    <article className="rounded-lg border border-lab-600 bg-lab-850 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h3 className="font-display text-2xl leading-none tracking-wide text-bone">{platformName(platform)}</h3>
        <span className="ml-auto">{method === 'api' ? <Badge tone="ghost" icon={KeyRound}>Official API</Badge> : hasCookie ? <Badge tone="volt">Login saved</Badge> : <Badge tone="candle">Not logged in</Badge>}</span>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Account label" htmlFor={accId} hint="Name of the saved login.">
          <Input id={accId} spellCheck={false} value={account} onChange={(e) => setAccount(e.target.value)} onBlur={() => saveMethod(method)} />
        </Field>
        <div className="flex min-w-0 flex-col gap-1.5">
          <span className="text-sm font-semibold text-bone">Login method</span>
          <Segmented label={`${platformName(platform)} login method`} value={method} onChange={saveMethod} options={[{value: 'cookie', label: 'Cookie Login', icon: LogIn}, {value: 'api', label: 'Official API', icon: KeyRound}]} />
        </div>
      </div>
      {method === 'cookie' ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="primary" icon={LogIn} onClick={login}>Connect / Refresh Login</Button>
          <Button icon={ShieldCheck} onClick={check}>Check Session</Button>
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            {PLATFORM_FIELDS[platform].map(([k, label, secret]) =>
              secret ? <Secret key={k} name={k} label={label} env={s.env} value={sec.vals[k] ?? ''} onChange={sec.set(k)} /> : <Plain key={k} name={k} label={label} env={s.env} value={sec.vals[k] ?? ''} onChange={sec.set(k)} />,
            )}
          </div>
          {platform === 'youtube' ? (
            <div className="flex flex-wrap items-center gap-2">
              <input id={fileId} type="file" accept=".json" className="sr-only" onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadClient(f); e.target.value = ''; }} />
              <label htmlFor={fileId} className="inline-flex h-10 items-center gap-2 rounded-md border border-lab-500 bg-lab-800 px-4 text-sm font-semibold text-bone hover:border-lab-400 has-[:focus-visible]:outline-2 pointer-coarse:h-11">
                <Upload aria-hidden className="size-4" />Upload client_secret.json
              </label>
              {s.api_status.youtube?.client_file ? <Badge tone="volt">Client file saved</Badge> : null}
              <Button variant="ghost" onClick={() => act(async () => watch(await api<Job>('/api/settings/youtube-connect', {method: 'POST'}), 'YouTube consent: a browser opens', reload))}>Connect YouTube API</Button>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" icon={Save} onClick={saveApi}>Save</Button>
            <Button icon={Radio} onClick={test}>Test Connection</Button>
          </div>
          <p className="text-[0.8125rem] text-fog">{API_NOTES[platform]}</p>
        </div>
      )}
    </article>
  );
}

function AlertsSection({s, reload}: {s: SettingsData; reload: () => void}) {
  const {act, toast} = useStudio();
  const sec = useSecrets();
  return (
    <Panel id="alerts" title="Alerts" description="A message when an overnight batch finishes or a job fails, with links. Optional.">
      <div className="grid gap-4 md:grid-cols-2">
        <Secret name="TELEGRAM_BOT_TOKEN" label="Telegram bot token" env={s.env} value={sec.vals.TELEGRAM_BOT_TOKEN ?? ''} onChange={sec.set('TELEGRAM_BOT_TOKEN')} hint="From @BotFather." />
        <Plain name="TELEGRAM_CHAT_ID" label="Telegram chat ID" env={s.env} value={sec.vals.TELEGRAM_CHAT_ID ?? ''} onChange={sec.set('TELEGRAM_CHAT_ID')} placeholder="e.g. 123456789" />
        <Secret name="DISCORD_WEBHOOK_URL" label="Discord webhook URL" env={s.env} value={sec.vals.DISCORD_WEBHOOK_URL ?? ''} onChange={sec.set('DISCORD_WEBHOOK_URL')} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="primary" icon={Save} onClick={() => act(async () => { await sec.save(['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'DISCORD_WEBHOOK_URL']); toast('Alert settings saved.', 'ok'); reload(); })}>Save Alerts</Button>
        <Button icon={Bell} onClick={() => act(async () => { const r = await api<{results: Record<string, string>}>('/api/settings/test-notify', {method: 'POST'}); toast(`Test sent: ${Object.entries(r.results).map(([k, v]) => `${k} ${v}`).join(', ')}`, 'ok'); })}>Send Test Message</Button>
      </div>
    </Panel>
  );
}

function AnalyticsSection({s}: {s: SettingsData}) {
  const {act, toast} = useStudio();
  const [channel, setChannel] = useState(s.prefs.analytics?.channel_url ?? '');
  const [weekly, setWeekly] = useState(Boolean(s.prefs.analytics?.weekly));
  const id = useId();
  return (
    <Panel id="analytics" title="Analytics" description="Views and likes (via yt-dlp) feed the best hooks back into new ideas.">
      <Field label="YouTube channel URL" htmlFor={id} optional hint="Published videos are matched to projects by title.">
        <Input id={id} type="url" inputMode="url" spellCheck={false} value={channel} onChange={(e) => setChannel(e.target.value)} placeholder="https://www.youtube.com/@handle/shorts" />
      </Field>
      <Check label="Sync every Monday at 09:00" hint="Needs the scheduler daemon." checked={weekly} onChange={setWeekly} />
      <Button className="mt-2" icon={Save} onClick={() => act(async () => { await api('/api/settings/prefs', {method: 'PUT', body: {analytics: {channel_url: channel.trim(), weekly}}}); toast('Analytics settings saved.', 'ok'); })}>Save Analytics</Button>
    </Panel>
  );
}

function SystemSection() {
  const {act, watch, setOnboardingOpen, setEnginesOpen} = useStudio();
  return (
    <Panel id="system" title="System" description="Health checks and the way back to the old UI.">
      <div className="flex flex-wrap gap-2">
        <Button icon={Stethoscope} onClick={() => act(async () => watch(await api<Job>('/api/health', {method: 'POST'}), 'Health check (doctor.py)'))}>Run Health Check</Button>
        <Button icon={Film} onClick={() => act(async () => watch(await api<Job>('/api/smoke', {method: 'POST'}), 'Smoke test: a 5-second render'))}>Run Smoke Test</Button>
        <Button variant="ghost" onClick={() => setEnginesOpen(true)}>Stitched Engines</Button>
        <Button variant="ghost" icon={CircleQuestionMark} onClick={() => setOnboardingOpen(true)}>Setup Guide</Button>
        <LinkButton href="/classic" variant="ghost" icon={ExternalLink}>Classic UI</LinkButton>
      </div>
      <p className="mt-3 text-[0.8125rem] text-fog">Results open in Studio Activity. Keep this project outside OneDrive for reliable renders (see docs/DEBUGGING.md).</p>
    </Panel>
  );
}

export default function Settings() {
  const route = useRoute();
  const settings = useApi<SettingsData>('/api/settings');
  const opts = useApi<Options>('/api/options');
  const section = route.params.get('section') ?? '';
  useEffect(() => {
    if (section && settings.data) document.getElementById(section)?.scrollIntoView({block: 'start'});
  }, [section, settings.data]);
  if (settings.error) return <Notice tone="blood" title={settings.error.message}>{settings.error.hint}</Notice>;
  if (!settings.data) return <Skeleton className="h-[600px]" />;
  const s = settings.data;
  const reload = () => void settings.reload();
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[200px_minmax(0,1fr)]">
      <nav aria-label="Settings sections" className="flex gap-1 overflow-x-auto pb-1 lg:sticky lg:top-20 lg:flex-col lg:overflow-visible">
        {SECTIONS.map((x) => (
          <a key={x.id} href={href('settings', {section: x.id})} aria-current={section === x.id ? 'location' : undefined} className={cx('flex h-10 shrink-0 items-center gap-2 rounded-md border px-3 text-sm font-semibold whitespace-nowrap', section === x.id ? 'border-lab-500 bg-lab-800 text-bone' : 'border-transparent text-moss hover:bg-lab-850 hover:text-bone')}>
            <x.icon aria-hidden className={cx('size-4 shrink-0', section === x.id ? 'text-pumpkin' : 'text-fog')} />
            {x.label}
          </a>
        ))}
      </nav>
      <div className="flex min-w-0 flex-col gap-6 [&>section]:scroll-mt-24">
        <ModelSection s={s} reload={reload} />
        <DefaultsSection s={s} opts={opts.data} />
        <Panel id="accounts" title="Publishing accounts" description="Cookie Login signs in with a real browser and works today. The Official API needs app approval. Secrets stay in your local .env and config/; this page only shows them masked.">
          <div className="flex flex-col gap-3">{['youtube', 'instagram', 'tiktok'].map((p) => <PlatformCard key={p} platform={p} s={s} reload={reload} />)}</div>
        </Panel>
        <AlertsSection s={s} reload={reload} />
        <AnalyticsSection s={s} />
        <SystemSection />
      </div>
    </div>
  );
}
