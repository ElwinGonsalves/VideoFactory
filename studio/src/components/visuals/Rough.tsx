import React from 'react';
import rough from 'roughjs';
import type {Drawable, Options} from 'roughjs/bin/core';
import {useProgress} from '../primitives';

const gen = rough.generator();

/** Deterministic hand-drawn shapes (fixed seed) so every frame of a scene draws the same wobble. */
export const shapes = {
  rect: (x: number, y: number, w: number, h: number, o: Options = {}): Drawable =>
    gen.rectangle(x, y, w, h, {seed: 7, roughness: 1.5, bowing: 1.2, ...o}),
  circle: (x: number, y: number, d: number, o: Options = {}): Drawable =>
    gen.circle(x, y, d, {seed: 11, roughness: 1.4, ...o}),
  line: (x1: number, y1: number, x2: number, y2: number, o: Options = {}): Drawable =>
    gen.line(x1, y1, x2, y2, {seed: 5, roughness: 1.3, ...o}),
  arrow: (x1: number, y1: number, x2: number, y2: number, o: Options = {}): Drawable[] => {
    const a = Math.atan2(y2 - y1, x2 - x1);
    const h = 34;
    return [
      gen.line(x1, y1, x2, y2, {seed: 3, roughness: 1.2, ...o}),
      gen.line(x2, y2, x2 - h * Math.cos(a - 0.45), y2 - h * Math.sin(a - 0.45), {seed: 4, ...o}),
      gen.line(x2, y2, x2 - h * Math.cos(a + 0.45), y2 - h * Math.sin(a + 0.45), {seed: 6, ...o}),
    ];
  },
};

/** Animated pen reveal of a rough.js drawable (stroke-dashoffset). Use inside an <svg>. */
export const RoughDraw: React.FC<{
  drawable: Drawable | Drawable[];
  color: string;
  width?: number;
  delay?: number;
  duration?: number;
}> = ({drawable, color, width = 6, delay = 0, duration = 22}) => {
  const p = useProgress(delay, duration);
  const list = Array.isArray(drawable) ? drawable : [drawable];
  return (
    <g>
      {list.flatMap((d, i) =>
        gen.toPaths(d).map((info, j) => (
          <path
            key={`${i}-${j}`}
            d={info.d}
            pathLength={1}
            fill="none"
            stroke={color}
            strokeWidth={width}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={1}
            strokeDashoffset={1 - p}
          />
        )),
      )}
    </g>
  );
};