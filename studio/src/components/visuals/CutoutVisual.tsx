import React from 'react';
import {Img, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {resolveIcon} from './icons';
import {IconAt, Lines, Stage, designSize, wrapLines} from './common';
import type {VisualProps} from './common';

/** Torn-edge polygon points for a w x h sheet (deterministic jitter). */
const torn = (w: number, h: number): string => {
  const pts: string[] = [];
  const j = (i: number) => ((i * 37) % 11) - 5;
  for (let x = 0; x <= w; x += 40) pts.push(`${x},${j(x / 40)}`);
  for (let y = 40; y <= h; y += 40) pts.push(`${w + j(y / 40 + 3)},${y}`);
  for (let x = w; x >= 0; x -= 40) pts.push(`${x},${h + j(x / 40 + 7)}`);
  for (let y = h - 40; y > 0; y -= 40) pts.push(`${j(y / 40 + 5)},${y}`);
  return pts.join(' ');
};

/** Vox-style paper cutout: a taped, slightly rotated sheet with a print photo or big icon and a serif caption. */
export const CutoutVisual: React.FC<VisualProps> = ({visual, theme, ratio}) => {
  const {W, H, portrait} = designSize(ratio);
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame, fps, config: {damping: 16}});
  const sheetW = portrait ? 820 : 1100;
  const sheetH = portrait ? 980 : 720;
  const x = (W - sheetW) / 2;
  const y = (H - sheetH) / 2 + (portrait ? 10 : 0);
  const Icon = resolveIcon(visual.icon);
  const caption = visual.heading ?? visual.text ?? '';
  const photoH = portrait ? 560 : 470;
  const rot = -2.2 + (1 - s) * -6;
  return (
    <Stage ratio={ratio}>
      <g transform={`translate(${W / 2} ${H / 2}) rotate(${rot}) scale(${0.85 + 0.15 * s}) translate(${-W / 2} ${-H / 2})`} opacity={Math.min(1, s * 1.6)}>
        <polygon points={torn(sheetW, sheetH)} transform={`translate(${x + 14} ${y + 18})`} fill="rgba(0,0,0,0.22)" />
        <polygon points={torn(sheetW, sheetH)} transform={`translate(${x} ${y})`} fill="#fffdf6" />
        {visual.src ? (
          <foreignObject x={x + 40} y={y + 50} width={sheetW - 80} height={photoH}>
            <Img src={staticFile(visual.src)} style={{width: '100%', height: '100%', objectFit: 'cover', display: 'block', border: '8px solid #fff', boxSizing: 'border-box'}} />
          </foreignObject>
        ) : (
          <g>
            <ellipse cx={W / 2} cy={y + 50 + photoH / 2} rx={sheetW * 0.3} ry={photoH * 0.42} fill={theme.accent} opacity={0.85} transform={`rotate(-4 ${W / 2} ${y + 50 + photoH / 2})`} />
            <IconAt Icon={Icon} cx={W / 2} cy={y + 50 + photoH / 2} size={photoH * 0.62} color="#1b1b1b" strokeWidth={1.4} />
          </g>
        )}
        <Lines x={W / 2} y={y + photoH + 150} lines={wrapLines(caption, portrait ? 22 : 34, 3)} size={portrait ? 64 : 56}
          fill="#1b1b1b" font={theme.headingFont} weight={700} />
        {visual.label ? (
          <Lines x={W / 2} y={y + sheetH - 40} lines={[wrapLines(visual.label, 36, 1)[0]]} size={30} fill="#5b5648" font={theme.font} weight={500} />
        ) : null}
        <rect x={W / 2 - 110} y={y - 28} width={220} height={56} fill="rgba(242,194,0,0.75)" transform={`rotate(-3 ${W / 2} ${y})`} />
      </g>
    </Stage>
  );
};