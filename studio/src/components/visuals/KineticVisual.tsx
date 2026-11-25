import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {isPortrait} from '../../format';
import type {VisualProps} from './common';

/**
 * Kinetic type: the words ARE the picture. Each word slams in on its own beat, the key word (the longest
 * one, or a number) takes the accent colour, and a bar sweeps under the line. Fills the frame centre so
 * visual QA sees real content, not an empty scene.
 */
export const KineticVisual: React.FC<VisualProps> = ({visual, theme, ratio}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const portrait = isPortrait(ratio);
  const text = String(visual.heading ?? visual.text ?? visual.label ?? visual.items?.join(' ') ?? '').trim();
  const words = text.split(/\s+/).filter(Boolean).slice(0, 9);
  const key = words.reduce((best, w, i) => (/\d/.test(w) || w.length > (words[best]?.length ?? 0) ? i : best), 0);
  const {width} = useVideoConfig();
  const base = portrait ? (words.length <= 3 ? 190 : words.length <= 6 ? 150 : 118) : words.length <= 4 ? 170 : 128;
  // the longest word must fit on one line: heavy uppercase runs about 0.68 em per character
  const longest = Math.max(1, ...words.map((w) => w.length));
  const size = Math.min(base, Math.floor((width * (portrait ? 0.74 : 0.8)) / (longest * 0.68)));
  const bar = interpolate(frame, [words.length * 5 + 4, words.length * 5 + 22], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{width: '100%', minHeight: portrait ? 1100 : 640, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'flex-start', padding: portrait ? '0 8px' : '0 40px'}}>
      <div style={{display: 'flex', flexWrap: 'wrap', gap: `${size * 0.06}px ${size * 0.22}px`, alignItems: 'baseline'}}>
        {words.map((w, i) => {
          const s = spring({frame: frame - i * 5, fps, config: {damping: 13, stiffness: 180, mass: 0.6}});
          return (
            <span
              key={`${w}-${i}`}
              style={{
                display: 'inline-block',
                fontFamily: theme.headingFont,
                fontWeight: 900,
                fontSize: size,
                lineHeight: 0.95,
                letterSpacing: '-0.02em',
                textTransform: 'uppercase',
                color: i === key ? theme.accent : theme.text,
                opacity: Math.min(1, s * 1.4),
                transform: `translateY(${(1 - s) * 60}px) scale(${1.35 - 0.35 * s})`,
                transformOrigin: 'left bottom',
              }}
            >
              {w}
            </span>
          );
        })}
      </div>
      <div style={{marginTop: size * 0.25, height: size * 0.12, width: `${bar * (portrait ? 80 : 50)}%`, background: theme.accent}} />
    </div>
  );
};
