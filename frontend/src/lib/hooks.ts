import {useCallback, useEffect, useRef, useState, useSyncExternalStore} from 'react';
import {ApiError, api} from './api';

// ------------------------------------------------------------------ hash routing: #/library?item=x
export type Route = {page: string; sub: string; params: URLSearchParams};
export const PAGES = ['create', 'ideas', 'batch', 'library', 'schedule', 'settings'] as const;
export type Page = (typeof PAGES)[number];

function parse(): Route {
  const raw = window.location.hash.replace(/^#\/?/, '');
  const [path, query = ''] = raw.split('?');
  const [page = 'create', sub = ''] = path.split('/');
  return {page: (PAGES as readonly string[]).includes(page) ? page : 'create', sub, params: new URLSearchParams(query)};
}
const subscribe = (cb: () => void) => {
  window.addEventListener('hashchange', cb);
  return () => window.removeEventListener('hashchange', cb);
};
let cache = {hash: '', route: parse()};
const snapshot = () => {
  if (cache.hash !== window.location.hash) cache = {hash: window.location.hash, route: parse()};
  return cache.route;
};
export const useRoute = () => useSyncExternalStore(subscribe, snapshot);
export function navigate(page: string, params?: Record<string, string>, sub = '') {
  const q = params ? new URLSearchParams(params).toString() : '';
  window.location.hash = `/${page}${sub ? `/${sub}` : ''}${q ? `?${q}` : ''}`;
}
export const href = (page: string, params?: Record<string, string>) =>
  `#/${page}${params ? `?${new URLSearchParams(params).toString()}` : ''}`;

// ------------------------------------------------------------------ data
export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(Boolean(path));
  const reload = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    try {
      setData(await api<T>(path));
      setError(null);
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(() => {
    void reload();
  }, [reload]);
  return {data, error, loading, reload, setData};
}

/** Poll while the tab is visible; pauses in background tabs to stay light. */
export function usePoll(fn: () => void | Promise<void>, ms: number, enabled = true) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    if (!enabled) return;
    let stop = false;
    let timer: number | undefined;
    const tick = async () => {
      if (!document.hidden) await Promise.resolve(ref.current()).catch(() => undefined);
      if (!stop) timer = window.setTimeout(tick, ms);
    };
    void tick();
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, [ms, enabled]);
}

export function useLocalFlag(key: string): [boolean, (v: boolean) => void] {
  const [v, setV] = useState(() => localStorage.getItem(key) === '1');
  const set = useCallback(
    (next: boolean) => {
      if (next) localStorage.setItem(key, '1');
      else localStorage.removeItem(key);
      setV(next);
      window.dispatchEvent(new CustomEvent('vf-flag', {detail: key}));
    },
    [key],
  );
  useEffect(() => {
    const on = (e: Event) => {
      if ((e as CustomEvent).detail === key) setV(localStorage.getItem(key) === '1');
    };
    window.addEventListener('vf-flag', on);
    return () => window.removeEventListener('vf-flag', on);
  }, [key]);
  return [v, set];
}

export function useMedia(query: string) {
  const [m, setM] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setM(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, [query]);
  return m;
}

export const useReducedMotion = () => useMedia('(prefers-reduced-motion: reduce)');

/** Ticks every second so countdowns stay live. */
export function useNow(ms = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(id);
  }, [ms]);
  return now;
}
