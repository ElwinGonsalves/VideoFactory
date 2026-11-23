import {createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode} from 'react';
import {ApiError, api, type Engines, type Job, type Studio} from './api';
import {useLocalFlag, usePoll} from './hooks';

type ToastKind = 'ok' | 'err' | 'info';
export type Toast = {id: number; kind: ToastKind; text: string; hint?: string};
type Done = (status: Job['status']) => void;

type Ctx = {
  studio: Studio | null;
  offline: ApiError | null;
  engines: Engines | null;
  refreshEngines: (force?: boolean) => Promise<void>;
  refresh: () => Promise<void>;
  /** Register a job; `then` runs once when it finishes. Opens nothing by itself. */
  watch: (job: Job, label: string, then?: Done) => void;
  toasts: Toast[];
  toast: (text: string, kind?: ToastKind, hint?: string) => void;
  dismissToast: (id: number) => void;
  /** Wrap an action: errors become toasts with their hint. */
  act: <T>(fn: () => Promise<T>) => Promise<T | undefined>;
  drawerOpen: boolean;
  setDrawerOpen: (v: boolean) => void;
  enginesOpen: boolean;
  setEnginesOpen: (v: boolean) => void;
  onboardingOpen: boolean;
  setOnboardingOpen: (v: boolean) => void;
  demo: boolean;
  setDemo: (v: boolean) => void;
  focusJob: string | null;
};

const StudioCtx = createContext<Ctx | null>(null);

export function StudioProvider({children}: {children: ReactNode}) {
  const [studio, setStudio] = useState<Studio | null>(null);
  const [offline, setOffline] = useState<ApiError | null>(null);
  const [engines, setEngines] = useState<Engines | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [enginesOpen, setEnginesOpen] = useState(false);
  const [onboarded] = useLocalFlag('vf-onboarded');
  const [onboardingOpen, setOnboardingOpen] = useState(!onboarded);
  const [demo, setDemo] = useLocalFlag('vf-demo');
  const [focusJob, setFocusJob] = useState<string | null>(null);
  const waiters = useRef(new Map<string, Done>());
  const seq = useRef(0);

  const dismissToast = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const toast = useCallback(
    (text: string, kind: ToastKind = 'ok', hint?: string) => {
      const id = ++seq.current;
      setToasts((t) => [...t.slice(-3), {id, kind, text, hint}]);
      window.setTimeout(() => dismissToast(id), kind === 'err' ? 10_000 : 5_000);
    },
    [dismissToast],
  );
  const act = useCallback(
    async <T,>(fn: () => Promise<T>) => {
      try {
        return await fn();
      } catch (e) {
        const err = e as ApiError;
        toast(err.message || String(e), 'err', err.hint);
        return undefined;
      }
    },
    [toast],
  );

  const refresh = useCallback(async () => {
    try {
      const s = await api<Studio>('/api/studio');
      setStudio(s);
      setOffline(null);
      const all = [...s.recent, ...s.running, ...s.queued];
      for (const [id, cb] of waiters.current) {
        const j = all.find((x) => x.id === id);
        if (j && ['done', 'failed', 'cancelled'].includes(j.status)) {
          waiters.current.delete(id);
          cb(j.status);
        }
      }
    } catch (e) {
      setOffline(e as ApiError);
    }
  }, []);
  const busy = Boolean(studio && (studio.running.length || studio.queued.length));
  usePoll(refresh, busy || waiters.current.size ? 1500 : 5000);

  const refreshEngines = useCallback(async (force = false) => {
    try {
      setEngines(await api<Engines>(`/api/engines${force ? '?refresh=true' : ''}`));
    } catch {
      /* the badge shows "checking" until the server answers */
    }
  }, []);
  usePoll(() => refreshEngines(false), 60_000);

  const watch = useCallback(
    (job: Job, label: string, then?: Done) => {
      if (then) waiters.current.set(job.id, then);
      setFocusJob(job.id);
      toast(`${label} started. Follow it in Studio Activity.`, 'info');
      void refresh();
    },
    [refresh, toast],
  );

  const value = useMemo<Ctx>(
    () => ({studio, offline, engines, refreshEngines, refresh, watch, toasts, toast, dismissToast, act, drawerOpen, setDrawerOpen,
      enginesOpen, setEnginesOpen, onboardingOpen, setOnboardingOpen, demo, setDemo, focusJob}),
    [studio, offline, engines, refreshEngines, refresh, watch, toasts, toast, dismissToast, act, drawerOpen, enginesOpen, onboardingOpen, demo, setDemo, focusJob],
  );
  return <StudioCtx.Provider value={value}>{children}</StudioCtx.Provider>;
}

export function useStudio() {
  const c = useContext(StudioCtx);
  if (!c) throw new Error('useStudio outside StudioProvider');
  return c;
}

/** Read a finished job's log and pull the project slug it wrote (write-script and approve jobs print it). */
export async function slugFromJobLog(jobId: string): Promise<string | null> {
  const r = await api<{text: string}>(`/api/jobs/${jobId}/log?offset=0`);
  const m = r.text.match(/SCRIPT .*[\\/]projects[\\/]([^\\/]+)[\\/]script\.json/) || r.text.match(/"projects\/([^"]+)"/);
  return m ? m[1] : null;
}
