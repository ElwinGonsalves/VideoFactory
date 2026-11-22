import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';
import type {StickPose} from '../../types';
import {RoughDraw, shapes} from './Rough';
import {Lines, Stage, designSize, wrapLines} from './common';
import type {VisualProps} from './common';

/**
 * Limb angles in degrees measured from straight down; positive swings toward +x (the figure's right on screen).
 * [upper arm, forearm] per side and [thigh, shin] per side.
 */
type Limbs = {la: [number, number]; ra: [number, number]; ll: [number, number]; rl: [number, number]};
export const POSES: Record<StickPose, Limbs> = {
  idle: {la: [-14, -8], ra: [14, 8], ll: [-8, -4], rl: [8, 4]},
  point: {la: [-14, -8], ra: [100, 100], ll: [-8, -4], rl: [8, 4]},
  shrug: {la: [-55, -140], ra: [55, 140], ll: [-8, -4], rl: [8, 4]},
  run: {la: [50, 120], ra: [-50, -120], ll: [-45, -85], rl: [40, 5]},
  celebrate: {la: [-150, -170], ra: [150, 170], ll: [-24, -22], rl: [24, 22]},
  panic: {la: [-135, -95], ra: [135, 95], ll: [-12, -6], rl: [12, 6]},
  think: {la: [-14, -8], ra: [35, 165], ll: [-8, -4], rl: [8, 4]},
};

const mix = (a: [number, number], b: [number, number], t: number): [number, number] => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
const end = (x: number, y: number, len: number, deg: number): [number, number] => {
  const r = (deg * Math.PI) / 180;
  return [x + len * Math.sin(r), y + len * Math.cos(r)];
};

/** Hand-drawn stick figure with a pose and an optional speech bubble (visual.pose, visual.bubble). */
export const StickmanVisual: React.FC<VisualProps> = ({visual, theme, ratio}) => {
  const {W, H, portrait} = designSize(ratio);
  const frame = useCurrentFrame();
  const pose = POSES[visual.pose ?? 'idle'] ?? POSES.idle;
  const t = interpolate(frame, [0, 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const energy = visual.pose === 'panic' ? 5 : visual.pose === 'run' ? 8 : 2.5;
  const wob = Math.sin(frame / (visual.pose === 'panic' ? 1.6 : 4)) * energy;
  const bounce = visual.pose === 'celebrate' ? -Math.abs(Math.sin(frame / 5)) * 40 : visual.pose === 'run' ? Math.sin(frame / 3) * 10 : Math.sin(frame / 12) * 4;
  const s = portrait ? 1 : 0.78;
  const hip: [number, number] = [portrait ? W / 2 : W * 0.62, (portrait ? 880 : 640) + bounce * s];
  const torsoLen = 190 * s;
  const neck: [number, number] = [hip[0], hip[1] - torsoLen];
  const shoulder: [number, number] = [hip[0], neck[1] + 28 * s];
  const head: [number, number] = [neck[0] + (visual.pose === 'think' ? 10 : 0), neck[1] - 66 * s];
  const limb = (from: [number, number], ang: [number, number], l1: number, l2: number, lerpFrom: [number, number], sway = 0) => {
    const [a1, a2] = mix(lerpFrom, ang, t);
    const mid = end(from[0], from[1], l1 * s, a1 + sway);
    return [from, mid, end(mid[0], mid[1], l2 * s, a2 + sway)] as [number, number][];
  };
  const idle = POSES.idle;
  const la = limb(shoulder, pose.la, 95, 90, idle.la, wob);
  const ra = limb(shoulder, pose.ra, 95, 90, idle.ra, -wob);
  const ll = limb(hip, pose.ll, 110, 105, idle.ll, 0);
  const rl = limb(hip, pose.rl, 110, 105, idle.rl, 0);
  const groundY = (portrait ? 880 : 640) + (110 + 105) * s + 12;
  const draw = (pts: [number, number][], seed: number, delay: number) => (
    <RoughDraw
      key={seed}
      drawable={[
        shapes.line(pts[0][0], pts[0][1], pts[1][0], pts[1][1], {seed}),
        shapes.line(pts[1][0], pts[1][1], pts[2][0], pts[2][1], {seed: seed + 1}),
      ]}
      color={theme.text}
      width={12}
      delay={delay}
      duration={8}
    />
  );
  const bubble = visual.bubble ?? visual.text ?? '';
  const bw = portrait ? 800 : 700;
  const bx = portrait ? (W - bw) / 2 : 90;
  const by = portrait ? 70 : 90;
  const bh = portrait ? 260 : 300;
  const bLines = wrapLines(bubble, portrait ? 26 : 24, 3);
  return (
    <Stage ratio={ratio}>
      <RoughDraw drawable={shapes.line(portrait ? 120 : W * 0.4, groundY, portrait ? W - 120 : W * 0.88, groundY, {seed: 3})} color={theme.muted} width={6} delay={0} duration={14} />
      <RoughDraw drawable={shapes.circle(head[0], head[1], 132 * s, {seed: 14})} color={theme.text} width={12} delay={0} duration={10} />
      <circle cx={head[0] - 18 * s} cy={head[1] - 6 * s} r={7 * s} fill={theme.text} />
      <circle cx={head[0] + 18 * s} cy={head[1] - 6 * s} r={7 * s} fill={theme.text} />
      <path d={`M${head[0] - 20 * s} ${head[1] + 24 * s} Q${head[0]} ${head[1] + (visual.pose === 'panic' ? 8 : 40) * s} ${head[0] + 20 * s} ${head[1] + 24 * s}`} stroke={theme.text} strokeWidth={7} fill="none" strokeLinecap="round" />
      <RoughDraw drawable={shapes.line(neck[0], neck[1], hip[0], hip[1], {seed: 2})} color={theme.text} width={12} delay={4} duration={8} />
      {draw(la, 20, 6)}
      {draw(ra, 30, 8)}
      {draw(ll, 40, 10)}
      {draw(rl, 50, 12)}
      {bubble ? (
        <g>
          <RoughDraw drawable={shapes.rect(bx, by, bw, bh, {seed: 77})} color={theme.text} width={7} delay={14} duration={14} />
          <RoughDraw drawable={[shapes.line(bx + bw * 0.5, by + bh, head[0] + 20, head[1] - 90 * s, {seed: 78}), shapes.line(bx + bw * 0.5 + 60, by + bh, head[0] + 20, head[1] - 90 * s, {seed: 79})]}
            color={theme.text} width={7} delay={20} duration={8} />
          {frame >= 22 ? <Lines x={bx + bw / 2} y={by + bh / 2 - ((bLines.length - 1) * 56 * 1.15) / 2 + 18} lines={bLines} size={56} fill={theme.text} font={theme.font} weight={700} /> : null}
        </g>
      ) : null}
      {visual.heading ? (
        <Lines x={W / 2} y={H - 18} lines={[wrapLines(visual.heading, 40, 1)[0]]} size={34} fill={theme.muted} font={theme.font} weight={500} />
      ) : null}
    </Stage>
  );
};