import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {HookCard} from '../components/Cover';
import {buildTheme} from '../theme';
import type {ThumbnailProps} from '../types';

/**
 * Code-rendered thumbnail (render with `remotion still`): darkened video/archive frame,
 * accent edge, and the hook text in the same HookCard as the frame-0 cover.
 * 16:9 renders at 1280x720 (YouTube's recommended size); 9:16 and 1:1 at feed size.
 */
export const Thumbnail: React.FC<ThumbnailProps> = ({aspectRatio, text, subtext, bgSrc, bgBlur, brand, theme}) => {
  const t = buildTheme(theme ?? 'concept', brand);
  return (
    <AbsoluteFill style={{backgroundColor: '#0b0b12'}}>
      {bgSrc ? (
        <Img
          src={staticFile(bgSrc)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            // Video frames carry their own text/captions: blur them so the hook text is the only thing to read.
            filter: `saturate(1.15) contrast(1.1) blur(${bgBlur ?? 0}px)`,
            transform: bgBlur ? 'scale(1.08)' : undefined, // hide blurred edges
          }}
        />
      ) : null}
      {/* Scrim keeps text readable over any frame. */}
      <AbsoluteFill
        style={{
          background:
            aspectRatio === '16:9'
              ? 'linear-gradient(90deg, rgba(5,5,12,0.92) 0%, rgba(5,5,12,0.65) 55%, rgba(5,5,12,0.2) 100%)'
              : 'linear-gradient(180deg, rgba(5,5,12,0.55) 0%, rgba(5,5,12,0.8) 45%, rgba(5,5,12,0.55) 100%)',
        }}
      />
      <AbsoluteFill style={{borderLeft: `18px solid ${brand.colors.primary}`}} />
      <HookCard text={text} theme={t} brand={brand} ratio={aspectRatio} scale={aspectRatio === '16:9' ? 0.95 : 1} />
      {subtext ? (
        <div
          style={{
            position: 'absolute',
            left: aspectRatio === '16:9' ? 70 : 80,
            bottom: aspectRatio === '9:16' ? '24%' : 48,
            fontFamily: t.font,
            fontSize: aspectRatio === '16:9' ? 40 : 52,
            fontWeight: 700,
            color: '#ffffffcc',
          }}
        >
          {subtext}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
