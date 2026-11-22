import React from 'react';
import {AbsoluteFill, staticFile, useCurrentFrame} from 'remotion';
import type {Brand} from '../types';
import type {Theme} from '../theme';

/**
 * Theme backgrounds with a slow drift so long holds never look frozen.
 * Paper and board use the offline textures in studio/public/textures/ (made by
 * `media_pipeline/fetch_free_media.py --make-textures`); a missing file just falls back to the flat colour.
 */
export const Background: React.FC<{theme: Theme; brand: Brand}> = ({theme, brand}) => {
  const frame = useCurrentFrame();
  const drift = (frame * 0.15) % 1080;
  switch (theme.background) {
    case 'paper':
      return (
        <AbsoluteFill
          style={{
            backgroundColor: '#f1e9d6',
            backgroundImage: `url(${staticFile('textures/paper_grain.png')})`,
            backgroundSize: '1080px 1080px',
            backgroundPosition: `${drift}px ${drift * 0.4}px`,
          }}
        />
      );
    case 'board':
      return (
        <AbsoluteFill
          style={{
            backgroundColor: '#fbfbf8',
            backgroundImage:
              'linear-gradient(rgba(100,116,139,0.12) 1px, transparent 1px), linear-gradient(90deg, rgba(100,116,139,0.12) 1px, transparent 1px)',
            backgroundSize: '60px 60px',
          }}
        />
      );
    case 'plain':
      return <AbsoluteFill style={{backgroundColor: brand.colors.bgLight}} />;
    default: {
      // Concept theme: the accent glow orbits slowly.
      const x = 30 + Math.sin(frame / 90) * 12;
      const y = 20 + Math.cos(frame / 110) * 8;
      return (
        <AbsoluteFill
          style={{
            background: `radial-gradient(circle at ${x}% ${y}%, ${brand.colors.primary}33 0%, ${brand.colors.bgDark} 55%)`,
            backgroundColor: brand.colors.bgDark,
          }}
        />
      );
    }
  }
};
