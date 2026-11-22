import React from 'react';
import type {LucideIcon} from 'lucide-react';
import {isPortrait} from '../../format';
import type {Theme} from '../../theme';
import type {AspectRatio, Brand, Visual} from '../../types';

export type VisualProps = {visual: Visual; theme: Theme; brand: Brand; ratio: AspectRatio};

/** Design size of every concrete visual: tall for 9:16, wide otherwise. Scaled to fill the scene area. */
export const designSize = (ratio: AspectRatio): {W: number; H: number; portrait: boolean} =>
  isPortrait(ratio) ? {W: 1000, H: 1200, portrait: true} : {W: 1600, H: 900, portrait: false};

/** Full-height SVG stage: the visual always fills the scene area, never a small card in empty space. */
export const Stage: React.FC<{ratio: AspectRatio; children: React.ReactNode}> = ({ratio, children}) => {
  const {W, H} = designSize(ratio);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" style={{display: 'block'}}>
      {children}
    </svg>
  );
};

export const wrapLines = (text: string, maxChars: number, maxLines = 3): string[] => {
  const words = text.trim().split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let line = '';
  for (const w of words) {
    if (line && (line + ' ' + w).length > maxChars) {
      lines.push(line);
      line = w;
    } else {
      line = line ? `${line} ${w}` : w;
    }
  }
  if (line) lines.push(line);
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines);
    kept[maxLines - 1] = kept[maxLines - 1].replace(/\s*\S*$/, '') + '…';
    return kept;
  }
  return lines;
};

export const Lines: React.FC<{
  x: number;
  y: number;
  lines: string[];
  size: number;
  fill: string;
  font: string;
  weight?: number;
  anchor?: 'start' | 'middle' | 'end';
  lineHeight?: number;
  opacity?: number;
  italic?: boolean;
}> = ({x, y, lines, size, fill, font, weight = 700, anchor = 'middle', lineHeight = 1.15, opacity = 1, italic}) => (
  <text
    x={x}
    y={y}
    textAnchor={anchor}
    fontFamily={font}
    fontSize={size}
    fontWeight={weight}
    fontStyle={italic ? 'italic' : 'normal'}
    fill={fill}
    opacity={opacity}
  >
    {lines.map((l, i) => (
      <tspan key={i} x={x} dy={i === 0 ? 0 : size * lineHeight}>
        {l}
      </tspan>
    ))}
  </text>
);

/** A lucide icon placed inside the SVG at a centre point. */
export const IconAt: React.FC<{
  Icon: LucideIcon;
  cx: number;
  cy: number;
  size: number;
  color: string;
  strokeWidth?: number;
}> = ({Icon, cx, cy, size, color, strokeWidth = 1.6}) => (
  <Icon x={cx - size / 2} y={cy - size / 2} size={size} color={color} strokeWidth={strokeWidth} />
);