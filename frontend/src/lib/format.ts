// Locale-aware formatting (Intl), never hand-rolled date strings.
const timeFmt = new Intl.DateTimeFormat(undefined, {hour: 'numeric', minute: '2-digit'});
const dayFmt = new Intl.DateTimeFormat(undefined, {weekday: 'short', day: 'numeric', month: 'short'});
const dateFmt = new Intl.DateTimeFormat(undefined, {day: 'numeric', month: 'short', year: 'numeric'});
const num = new Intl.NumberFormat();

export const fmtNumber = (n: number | null | undefined) => (n == null ? '–' : num.format(n));
export const fmtDate = (ms: number) => dateFmt.format(new Date(ms));

/** "Today 11:45 PM", "Tomorrow 8:00 AM", "Mon 30 Nov 6:00 PM". */
export function humanTime(iso: string | Date, now = new Date()): string {
  const d = typeof iso === 'string' ? new Date(iso) : iso;
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((startOf(d) - startOf(now)) / 86_400_000);
  const t = timeFmt.format(d);
  if (days === 0) return `Today ${t}`;
  if (days === 1) return `Tomorrow ${t}`;
  if (days === -1) return `Yesterday ${t}`;
  return `${dayFmt.format(d)} ${t}`;
}

/** "45m", "2h 10m", "3d"; negative means overdue. */
export function countdown(sec: number): string {
  const s = Math.abs(Math.round(sec));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h${m % 60 ? ` ${m % 60}m` : ''}`;
  return `${Math.floor(h / 24)}d`;
}

export const elapsed = (sec: number) => {
  const s = Math.max(0, Math.round(sec));
  const m = Math.floor(s / 60);
  return m ? `${m}m ${String(s % 60).padStart(2, '0')}s` : `${s}s`;
};

/** concept_explainer -> Concept explainer */
export const titleCase = (id: string) => (id ? id.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) : '');

const PLATFORM_NAMES: Record<string, string> = {youtube: 'YouTube', instagram: 'Instagram', tiktok: 'TikTok'};
export const platformName = (p: string) => PLATFORM_NAMES[p] ?? titleCase(p);

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
