import React from 'react';
import {useCurrentFrame} from 'remotion';
import {RoughDraw, shapes} from './Rough';
import {Lines, Stage, designSize, wrapLines} from './common';
import type {VisualProps} from './common';
import type {TimelineEvent} from '../../types';

/** "2007: Streaming launches" -> {when: "2007", label: "Streaming launches"}. */
export const eventsOf = (v: VisualProps['visual']): TimelineEvent[] => {
  if (v.events?.length) return v.events.slice(0, 5);
  return (v.items ?? []).slice(0, 5).map((it, i) => {
    const m = /^\s*([^:]{1,12}):\s*(.+)$/.exec(it);
    return m ? {when: m[1], label: m[2]} : {when: String(i + 1), label: it};
  });
};

/** Dated milestones along a hand-drawn line (vertical in 9:16, horizontal otherwise). */
export const TimelineVisual: React.FC<VisualProps> = ({visual, theme, ratio}) => {
  const {W, H, portrait} = designSize(ratio);
  const frame = useCurrentFrame();
  const events = eventsOf(visual);
  const n = Math.max(1, events.length);
  const title = visual.heading ?? '';
  return (
    <Stage ratio={ratio}>
      {title ? <Lines x={W / 2} y={portrait ? 100 : 80} lines={wrapLines(title, portrait ? 22 : 44, 2)} size={portrait ? 64 : 58} fill={theme.text} font={theme.headingFont} /> : null}
      <RoughDraw
        drawable={portrait ? shapes.line(260, 230, 260, H - 70, {seed: 2}) : shapes.line(120, H / 2 + 20, W - 120, H / 2 + 20, {seed: 2})}
        color={theme.text} width={8} delay={0} duration={28}
      />
      {events.map((e, i) => {
        const t = n === 1 ? 0.5 : i / (n - 1);
        const x = portrait ? 260 : 220 + t * (W - 440);
        const y = portrait ? 290 + t * (H - 440) : H / 2 + 20;
        const delay = 12 + i * 14;
        const up = i % 2 === 0;
        return (
          <g key={`${e.when}-${i}`}>
            <RoughDraw drawable={shapes.circle(x, y, 64, {seed: 70 + i, fill: theme.accent, fillStyle: 'solid'})} color={theme.accent} width={4} delay={delay} duration={10} />
            {frame >= delay + 6 ? (
              portrait ? (
                <g>
                  <text x={x + 70} y={y - 6} fontFamily={theme.headingFont} fontSize={64} fontWeight={800} fill={theme.accent}>{e.when}</text>
                  <Lines x={x + 70} y={y + 50} lines={wrapLines(e.label, 24, 2)} size={42} fill={theme.text} font={theme.font} weight={600} anchor="start" />
                </g>
              ) : (
                <g>
                  <text x={x} y={up ? y - 70 : y + 105} textAnchor="middle" fontFamily={theme.headingFont} fontSize={64} fontWeight={800} fill={theme.accent}>{e.when}</text>
                  <Lines x={x} y={up ? y - 160 : y + 160} lines={wrapLines(e.label, 18, 2)} size={38} fill={theme.text} font={theme.font} weight={600} />
                </g>
              )
            ) : null}
          </g>
        );
      })}
    </Stage>
  );
};