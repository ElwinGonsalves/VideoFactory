import React from 'react';
import {spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveIcon} from './icons';
import {RoughDraw, shapes} from './Rough';
import {IconAt, Lines, Stage, designSize, wrapLines} from './common';
import type {VisualProps} from './common';

/**
 * Whiteboard / headline art: a big hand-drawn icon in a rough circle, a title, and up to 4 labels
 * that draw on one after another (visual.draw_cues or visual.items).
 */
export const SketchVisual: React.FC<VisualProps> = ({visual, theme, ratio}) => {
  const {W, H, portrait} = designSize(ratio);
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const Icon = resolveIcon(visual.icon);
  const labels = (visual.draw_cues ?? visual.items ?? []).slice(0, 4);
  const title = visual.heading ?? visual.text ?? '';
  const pop = spring({frame: frame - 6, fps, config: {damping: 14}});
  const circleD = labels.length ? (portrait ? 400 : 440) : portrait ? 560 : 600;
  const cx = portrait ? W / 2 : labels.length ? 460 : W / 2;
  const cy = portrait ? (labels.length ? 500 : 640) : H / 2 + 20;
  const titleLines = wrapLines(title, portrait ? 20 : 30, 2);
  return (
    <Stage ratio={ratio}>
      {titleLines.length ? (
        <Lines x={portrait ? W / 2 : cx} y={portrait ? 100 : 110} lines={titleLines} size={portrait ? 68 : 64}
          fill={theme.text} font={theme.headingFont} anchor="middle" />
      ) : null}
      <RoughDraw drawable={shapes.circle(cx, cy, circleD, {strokeWidth: 6})} color={theme.text} width={7} delay={2} duration={26} />
      <RoughDraw drawable={shapes.circle(cx, cy, circleD - 34, {seed: 21, roughness: 2})} color={theme.accent} width={5} delay={10} duration={26} />
      <g transform={`translate(${cx} ${cy}) scale(${0.6 + 0.4 * pop}) translate(${-cx} ${-cy})`} opacity={pop}>
        <IconAt Icon={Icon} cx={cx} cy={cy} size={circleD * 0.5} color={theme.text} strokeWidth={1.5} />
      </g>
      <RoughDraw drawable={shapes.line(cx - circleD * 0.45, cy + circleD / 2 + 30, cx + circleD * 0.45, cy + circleD / 2 + 30, {seed: 9})}
        color={theme.accent} width={8} delay={24} duration={16} />
      {labels.map((label, i) => {
        const delay = 30 + i * 16;
        const boxW = portrait ? 780 : 640;
        const boxH = 92;
        const x = portrait ? (W - boxW) / 2 : 900;
        const y = portrait ? 790 + i * 110 : 190 + i * 150;
        const shown = frame >= delay + 8;
        return (
          <g key={`${label}-${i}`}>
            <RoughDraw drawable={shapes.rect(x, y, boxW, boxH, {seed: 13 + i})} color={theme.text} width={5} delay={delay} duration={18} />
            <RoughDraw drawable={shapes.arrow(x - 56, y + boxH / 2, x - 8, y + boxH / 2, {seed: 30 + i})}
              color={theme.accent} width={6} delay={delay + 6} duration={10} />
            {shown ? (
              <Lines x={x + boxW / 2} y={y + boxH / 2 + 15} lines={[wrapLines(label, 30, 1)[0]]} size={44}
                fill={theme.text} font={theme.font} weight={600} />
            ) : null}
          </g>
        );
      })}
    </Stage>
  );
};