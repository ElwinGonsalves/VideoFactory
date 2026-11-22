import React from 'react';
import {Easing, interpolate, useCurrentFrame} from 'remotion';
import {RoughDraw, shapes} from './Rough';
import {Lines, Stage, designSize, wrapLines} from './common';
import type {VisualProps} from './common';

/** "7M+", "$1.5", "3x", "45%", "1,200" -> prefix, number, suffix. Non-numeric values are shown as-is. */
export const parseValue = (raw: string): {prefix: string; n: number; suffix: string; decimals: number; commas: boolean} | null => {
  const m = /^([^\d-]*)(-?\d[\d,]*(?:\.\d+)?)(.*)$/.exec(raw.trim());
  if (!m) return null;
  const n = parseFloat(m[2].replace(/,/g, ''));
  if (!Number.isFinite(n)) return null;
  return {prefix: m[1], n, suffix: m[3], decimals: (m[2].split('.')[1] ?? '').length, commas: m[2].includes(',')};
};

export const formatCount = (v: ReturnType<typeof parseValue>, p: number): string => {
  if (!v) return '';
  const x = v.n * p;
  const body = v.decimals ? x.toFixed(v.decimals) : Math.round(x).toString();
  return `${v.prefix}${v.commas ? Number(body).toLocaleString('en-US', {maximumFractionDigits: v.decimals}) : body}${v.suffix}`;
};

/** Counting-up number inside a drawing ring, with optional mini bars underneath (visual.data). Used for stat and counter. */
export const CounterVisual: React.FC<VisualProps> = ({visual, theme, ratio}) => {
  const {W, H, portrait} = designSize(ratio);
  const frame = useCurrentFrame();
  const p = interpolate(frame, [4, 40], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const raw = String(visual.value ?? '');
  const parsed = parseValue(raw);
  const text = parsed ? formatCount(parsed, p) : raw;
  const bars = (visual.data ?? []).slice(0, 5);
  const max = Math.max(1, ...bars.map((d) => d.value));
  const cx = portrait ? W / 2 : bars.length ? 520 : W / 2;
  const cy = portrait ? (bars.length ? 470 : 560) : H / 2;
  const r = portrait ? 330 : 330;
  const size = Math.min(230, (r * 1.7) / Math.max(2.4, text.length * 0.62));
  const ring = parsed && /%/.test(parsed.suffix) ? Math.min(1, parsed.n / 100) : 1;
  const label = visual.label ?? visual.heading ?? '';
  return (
    <Stage ratio={ratio}>
      <RoughDraw drawable={shapes.circle(cx, cy, r * 2, {seed: 8})} color={theme.text} width={7} delay={0} duration={24} />
      <circle cx={cx} cy={cy} r={r - 34} fill="none" stroke={theme.accent} strokeWidth={26} strokeLinecap="round"
        pathLength={1} strokeDasharray={1} strokeDashoffset={1 - ring * p} transform={`rotate(-90 ${cx} ${cy})`} opacity={0.9} />
      <text x={cx} y={cy + size * 0.34} textAnchor="middle" fontFamily={theme.headingFont} fontWeight={800} fontSize={size} fill={theme.text}>
        {text}
      </text>
      {label ? (
        <Lines x={cx} y={cy + r + 80} lines={wrapLines(label, portrait ? 26 : 30, 2)} size={portrait ? 54 : 50} fill={theme.text} font={theme.font} weight={600} />
      ) : null}
      {bars.length ? (
        <g>
          {bars.map((d, i) => {
            const bw = portrait ? 130 : 110;
            const gap = portrait ? 34 : 40;
            const total = bars.length * bw + (bars.length - 1) * gap;
            const x0 = portrait ? (W - total) / 2 : 1000;
            const x = portrait ? x0 + i * (bw + gap) : x0 + i * (bw + gap) * 0.9;
            const base = portrait ? 1130 : 780;
            const hMax = portrait ? 200 : 360;
            const h = (d.value / max) * hMax * interpolate(frame, [10 + i * 5, 34 + i * 5], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
            return (
              <g key={`${d.label}-${i}`}>
                <rect x={x} y={base - h} width={bw} height={h} rx={10} fill={i % 2 ? theme.accent : theme.text} opacity={0.9} />
                <text x={x + bw / 2} y={base + 40} textAnchor="middle" fontFamily={theme.font} fontSize={30} fill={theme.text}>{d.label}</text>
              </g>
            );
          })}
        </g>
      ) : null}
    </Stage>
  );
};