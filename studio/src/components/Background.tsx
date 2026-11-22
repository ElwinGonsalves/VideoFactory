import React from 'react';
import {AbsoluteFill} from 'remotion';
import type {Brand} from '../types';
import type {Theme} from '../theme';

export const Background: React.FC<{theme: Theme; brand: Brand}> = ({theme, brand}) => {
  switch (theme.background) {
    case 'paper':
      return (
        <AbsoluteFill style={{backgroundColor: '#f1e9d6'}}>
          <svg width="100%" height="100%" style={{opacity: 0.35}}>
            <filter id="grain">
              <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="2" stitchTiles="stitch" />
              <feColorMatrix type="saturate" values="0" />
            </filter>
            <rect width="100%" height="100%" filter="url(#grain)" />
          </svg>
        </AbsoluteFill>
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
    default:
      return (
        <AbsoluteFill
          style={{
            background: `radial-gradient(circle at 30% 20%, ${brand.colors.primary}33 0%, ${brand.colors.bgDark} 55%)`,
            backgroundColor: brand.colors.bgDark,
          }}
        />
      );
  }
};
