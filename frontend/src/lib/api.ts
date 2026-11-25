// Typed fetch wrapper. Every failure becomes a sentence with a next step, never a bare "Failed to fetch".
declare global {
  interface Window {
    VF_TOKEN: string;
  }
}

export const TOKEN = typeof window !== 'undefined' ? window.VF_TOKEN : '';
const API_TIMEOUT_MS = 30_000;
const UPLOAD_TIMEOUT_MS = 120_000;

export class ApiError extends Error {
  hint: string;
  status: number;
  constructor(message: string, hint = '', status = 0) {
    super(message);
    this.hint = hint;
    this.status = status;
  }
}

type Opts = {method?: 'GET' | 'POST' | 'PUT' | 'DELETE'; body?: unknown; timeout?: number};

export async function api<T = unknown>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {'X-VF-Token': TOKEN};
  const init: RequestInit = {method: opts.method ?? 'GET', headers};
  const isForm = opts.body instanceof FormData;
  if (isForm) init.body = opts.body as FormData;
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(opts.body);
  }
  const ms = opts.timeout ?? (isForm ? UPLOAD_TIMEOUT_MS : API_TIMEOUT_MS);
  const ctl = new AbortController();
  init.signal = ctl.signal;
  const timer = setTimeout(() => ctl.abort(), ms);
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch (e) {
    if ((e as Error).name === 'AbortError')
      throw new ApiError(`The server did not answer within ${Math.round(ms / 1000)} s.`, 'It may be busy rendering. Retry in a moment and check Studio Activity.');
    throw new ApiError('Server not reachable.', 'Is `python ui/server.py` running? Start it again, then reload this page.');
  } finally {
    clearTimeout(timer);
  }
  const data = (await res.json().catch(() => ({}))) as {detail?: string; hint?: string};
  if (!res.ok) throw new ApiError(data.detail || `Request failed (HTTP ${res.status}).`, data.hint || '', res.status);
  return data as T;
}

/** URL for media and files behind the token (video tags cannot send headers). */
export const fileUrl = (rel: string) =>
  `/files/${rel.split('/').map(encodeURIComponent).join('/')}?t=${encodeURIComponent(TOKEN)}`;
export const withToken = (path: string) => `${path}${path.includes('?') ? '&' : '?'}t=${encodeURIComponent(TOKEN)}`;

// ------------------------------------------------------------------ shapes the UI reads
export type Job = {
  id: string;
  kind: string;
  title: string;
  status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled';
  created: number;
  started: number | null;
  ended: number | null;
  returncode: number | null;
  meta: Record<string, string>;
};

export type StudioJob = Job & {
  node: string | null;
  node_index: number | null;
  percent: number | null;
  done_nodes: string[];
  slug: string;
  style: string;
  aspect_ratio: string;
  elapsed_sec: number;
  pipeline: boolean;
  has_video?: boolean;
};

export type Slot = {job_id: string; title: string; platforms: string[]; kind: 'generate' | 'upload'; at: string; in_sec: number; held?: boolean};

export type Studio = {
  now: StudioJob | null;
  running: StudioJob[];
  queued: StudioJob[];
  upcoming: Slot[];
  scheduled: number;
  recent: StudioJob[];
  daemon: boolean;
  nodes: {id: string; label: string; engine: string}[];
};

export type Engine = {key: string; name: string; organ: string; role: string; ok: boolean; detail: string; required: boolean};
export type Engines = {engines: Engine[]; alive: number; total: number; required_ok: boolean};

export type Template = {family: string; label: string; default_aspect: string; beats: {id: string; label: string; visuals: string[]}[]};
export type Options = {
  styles: string[];
  aspects: string[];
  moods: string[];
  caption_styles: string[];
  platforms: string[];
  defaults: Record<string, string | number>;
  visual_types: string[];
  templates: Record<string, Template>;
  grounding: boolean;
  languages: Language[];
  voices: Voice[];
  style_narrators: Record<string, {voice: string; line: string}>;
  default_line: string;
  language_lines: Record<string, string>;
};
export type Language = {id: string; label: string; default_voice: string};
export type Voice = {id: string; name: string; engine: string; lang: string; about: string};

export type Onboarding = {
  provider: string;
  key_name: string | null;
  key_set: boolean;
  brains: Record<string, boolean>;
  voices: Record<string, boolean>;
  voice_engine: string;
  engines: {alive: number; total: number; required_ok: boolean};
  projects: number;
  rendered: number;
  demo: {sample_short: string | null; can_render_sample: boolean; sample_project: string | null; blueprint: Blueprint | null};
};

export type Blueprint = {
  style_name: string;
  aspect_ratio?: string;
  target_duration_sec?: number;
  hook_first_3s?: {visual_pattern?: string; verbal_pattern?: string};
  pacing?: {avg_shot_sec?: number; words_per_minute?: number; caption_style?: string; transition_style?: string};
  beat_template?: {beat: string; pct_duration: number; visual_role?: string}[];
};

export type ProjectRow = {slug: string; title: string; style: string; aspect_ratio: string; scenes: number; rendered: boolean; needs_approval: boolean; language: string; voice: string; duration_sec: number; mtime: number; published: boolean; stage: 'script' | 'rendered' | 'published'};

export type Scene = {beat?: string; narration: string; visual?: {type?: string; heading?: string; [k: string]: unknown}; [k: string]: unknown};
export type Claim = {text: string; verified: boolean; sources?: string[]};
export type Script = {
  title?: string;
  style?: string;
  aspect_ratio?: string;
  scenes: Scene[];
  claims?: Claim[];
  facts_to_verify?: string[];
  grounded?: boolean;
  sources?: {title: string; url: string}[];
  [k: string]: unknown;
};

export type LibraryRow = {slug: string; title: string; aspect_ratio: string; style: string; has_video: boolean; mtime: number; qa_ok: boolean | null; unverified: number};
export type LibraryPage = {items: LibraryRow[]; total: number; page: number; pages: number; styles: string[]};
export type QaFrame = {frame: string; ok: boolean; issues: string[]};
export type LibraryItem = LibraryRow & {
  meta: {title: string; description?: string; hashtags?: string[]; tags?: string[]; aspect_ratio?: string; visibility?: string};
  thumbnail: string | null;
  stream: string;
  download: string;
  qa: {ok: boolean; frames: QaFrame[]} | null;
  qa_frames: {name: string; src: string; overlay: string | null}[];
  claims: Claim[];
  grounded: boolean;
  sources: {title: string; url: string}[];
  facts_to_verify: string[];
  published_url: string;
  stats: {views: number | null; likes: number | null} | null;
};
