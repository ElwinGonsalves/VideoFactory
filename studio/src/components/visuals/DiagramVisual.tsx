import React from 'react';
import {resolveIcon} from './icons';
import {RoughDraw, shapes} from './Rough';
import {IconAt, Lines, Stage, designSize, wrapLines} from './common';
import type {VisualProps} from './common';
import {useCurrentFrame} from 'remotion';

/** Hub-and-spoke diagram: the idea in the middle, 2-6 labelled nodes drawn around it, one after another. */
export const DiagramVisual: React.FC<VisualProps> = ({visual, theme, ratio}) => {
  const {W, H, portrait} = designSize(ratio);
  const frame = useCurrentFrame();
  const items = (visual.items?.length ? visual.items : [visual.label ?? visual.text ?? '']).filter(Boolean).slice(0, 6);
  const n = Math.max(1, items.length);
  const hub = {x: W / 2, y: portrait ? 640 : H / 2 + 30, r: portrait ? 150 : 140};
  const rx = portrait ? 340 : 600;
  const ry = portrait ? 400 : 290;
  const HubIcon = resolveIcon(visual.icon);
  const title = visual.heading ?? '';
  return (
    <Stage ratio={ratio}>
      {title ? (
        <Lines x={W / 2} y={portrait ? 100 : 80} lines={wrapLines(title, portrait ? 22 : 40, 2)} size={portrait ? 66 : 60}
          fill={theme.text} font={theme.headingFont} />
      ) : null}
      {items.map((label, i) => {
        const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
        const nx = hub.x + rx * Math.cos(a);
        const ny = hub.y + ry * Math.sin(a);
        const delay = 8 + i * 14;
        const nodeR = portrait ? 84 : 78;
        const lx = nx;
        const below = Math.sin(a) >= -0.2;
        const ly = below ? ny + nodeR + 50 : ny - nodeR - 34 - (wrapLines(label, 14, 2).length - 1) * 42;
        return (
          <g key={`${label}-${i}`}>
            <RoughDraw drawable={shapes.line(hub.x + Math.cos(a) * hub.r, hub.y + Math.sin(a) * hub.r, nx - Math.cos(a) * nodeR, ny - Math.sin(a) * nodeR, {seed: 40 + i})}
              color={theme.accent} width={7} delay={delay} duration={14} />
            <RoughDraw drawable={shapes.circle(nx, ny, nodeR * 2, {seed: 50 + i})} color={theme.text} width={6} delay={delay + 8} duration={16} />
            {frame >= delay + 14 ? (
              <>
                <text x={nx} y={ny + 22} textAnchor="middle" fontFamily={theme.headingFont} fontSize={64} fontWeight={800} fill={theme.accent}>
                  {i + 1}
                </text>
                <Lines x={lx} y={ly} lines={wrapLines(label, 14, 2)} size={40} fill={theme.text} font={theme.font} weight={600} />
              </>
            ) : null}
          </g>
        );
      })}
      <RoughDraw drawable={shapes.circle(hub.x, hub.y, hub.r * 2, {seed: 61})} color={theme.text} width={8} delay={0} duration={20} />
      <IconAt Icon={HubIcon} cx={hub.x} cy={hub.y} size={hub.r * 1.1} color={theme.text} strokeWidth={1.6} />
    </Stage>
  );
};