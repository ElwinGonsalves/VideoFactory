import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {safeInsets} from '../format';
import type {AspectRatio, Brand, Caption, CaptionStyle} from '../types';

const MAX_WORDS = 4;

/** Groups words into short phrases, breaking on punctuation or MAX_WORDS. */
export const groupCaptions = (words: Caption[]): Caption[][] => {
  const groups: Caption[][] = [];
  let cur: Caption[] = [];
  for (const w of words) {
    cur.push(w);
    if (cur.length >= MAX_WORDS || /[.!?,;:]$/.test(w.word)) {
      groups.push(cur);
      cur = [];
    }
  }
  if (cur.length) groups.push(cur);
  return groups;
};

export const Captions: React.FC<{
  captions: Caption[];
  style: CaptionStyle;
  ratio: AspectRatio;
  brand: Brand;
  dark: boolean;
}> = ({captions, style, ratio, brand, dark}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const groups = React.useMemo(() => groupCaptions(captions), [captions]);
  if (style === 'none' || groups.length === 0) return null;

  const t = frame / fps;
  const group = groups.find((g, i) => {
    const end = groups[i + 1] ? groups[i + 1][0].start : g[g.length - 1].end + 0.3;
    return t >= g[0].start && t < end;
  });
  if (!group) return null;

  const ins = safeInsets(ratio);
  const fontSize = ratio === '16:9' ? 64 : 72;
  const textColor = dark ? '#ffffff' : '#111111';

  const box: React.CSSProperties =
    style === 'phrase_box'
      ? {background: 'rgba(0,0,0,0.72)', padding: '14px 28px', borderRadius: 16, color: '#fff'}
      : {color: textColor, textShadow: dark ? '0 3px 12px rgba(0,0,0,0.6)' : 'none'};

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-end',
        alignItems: 'center',
        paddingBottom: ins.bottom,
        paddingLeft: ins.left,
        paddingRight: ins.right,
        boxSizing: 'border-box',
      }}
    >
      <div
        style={{
          ...box,
          fontFamily: brand.fonts.primary,
          fontSize,
          fontWeight: style === 'minimal_editorial' ? 500 : 800,
          lineHeight: 1.2,
          maxWidth: '100%',
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          columnGap: '0.3em',
        }}
      >
        {group.map((w, i) => {
          const active = style === 'word_highlight' && t >= w.start && t < w.end;
          return (
            <span
              key={`${w.start}-${i}`}
              style={{
                color: active ? brand.colors.primaryLight : undefined,
                display: 'inline-block',
                transform: active ? 'scale(1.08)' : 'none',
              }}
            >
              {w.word}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
