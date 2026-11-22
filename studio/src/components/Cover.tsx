import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {isPortrait, safeInsets} from '../format';
import type {Theme} from '../theme';
import type {AspectRatio, Brand} from '../types';

/** Seconds the cover holds at full contrast before dissolving into scene 0. */
export const COVER_HOLD = 0.5;
const COVER_FADE = 0.25;

/**
 * High-contrast hook card for frame 0 (what feeds and thumbnails pick up).
 * Solid dark backdrop, huge white text on an accent block, inside the 9:16 safe zone.
 */
export const HookCard: React.FC<{text: string; theme: Theme; brand: Brand; ratio: AspectRatio; scale?: number}> = ({
  text,
  theme,
  brand,
  ratio,
  scale = 1,
}) => {
  const ins = safeInsets(ratio);
  const words = text.trim().split(/\s+/);
  const longest = Math.max(...words.map((w) => w.length));
  const base = isPortrait(ratio) ? 150 : 128;
  const fontSize = Math.round(Math.min(base, (base * 9) / Math.max(9, longest)) * scale);
  return (
    <AbsoluteFill
      style={{
        paddingTop: ins.top,
        paddingRight: ins.right,
        paddingBottom: ins.bottom,
        paddingLeft: ins.left,
        boxSizing: 'border-box',
        justifyContent: 'center',
        alignItems: 'flex-start',
      }}
    >
      <div
        style={{
          fontFamily: theme.headingFont,
          fontWeight: 900,
          fontSize,
          lineHeight: 1.05,
          color: '#ffffff',
          textTransform: 'uppercase',
          letterSpacing: -1,
          display: 'flex',
          flexWrap: 'wrap',
          gap: `${Math.round(fontSize * 0.12)}px ${Math.round(fontSize * 0.25)}px`,
        }}
      >
        {words.map((w, i) => (
          <span
            key={`${w}-${i}`}
            style={{
              background: i === words.length - 1 ? brand.colors.primary : 'transparent',
              padding: i === words.length - 1 ? '0 16px' : 0,
              textShadow: '0 6px 24px rgba(0,0,0,0.55)',
            }}
          >
            {w}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/** Frame 0 → 0.5 s: the cover at full contrast; then a quick dissolve to the first scene. */
export const Cover: React.FC<{text: string; theme: Theme; brand: Brand; ratio: AspectRatio}> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const opacity = interpolate(frame, [COVER_HOLD * fps, (COVER_HOLD + COVER_FADE) * fps], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  if (opacity <= 0) return null;
  return (
    <AbsoluteFill style={{opacity, background: 'linear-gradient(160deg, #0b0b12 0%, #151526 100%)'}}>
      <HookCard {...props} />
    </AbsoluteFill>
  );
};
