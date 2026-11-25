import React from 'react';
import {AbsoluteFill, staticFile, useCurrentFrame} from 'remotion';
import type {Brand} from '../types';
import type {Theme} from '../theme';

/**
 * Theme backgrounds with a slow drift so long holds never look frozen.
 * Paper uses the offline texture in studio/public/textures/ (made by
 * `media_pipeline/fetch_free_media.py --make-textures`); a missing file just falls back to the flat colour.
 * Every other ground is pure CSS, so no style depends on a file that might be missing.
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
    case 'dossier': {
      // a case file on a navy desk: blueprint grid, a warm lamp pool that wanders a little
      const x = 70 + Math.sin(frame / 120) * 6;
      return (
        <AbsoluteFill
          style={{
            backgroundColor: '#0b1726',
            backgroundImage: [
              `radial-gradient(circle at ${x}% 18%, rgba(245,165,36,0.18) 0%, transparent 45%)`,
              'radial-gradient(ellipse at 50% 120%, rgba(0,0,0,0.6) 0%, transparent 60%)',
              'linear-gradient(rgba(148,178,214,0.10) 1px, transparent 1px)',
              'linear-gradient(90deg, rgba(148,178,214,0.10) 1px, transparent 1px)',
              'linear-gradient(rgba(148,178,214,0.05) 1px, transparent 1px)',
              'linear-gradient(90deg, rgba(148,178,214,0.05) 1px, transparent 1px)',
            ].join(', '),
            backgroundSize: '100% 100%, 100% 100%, 120px 120px, 120px 120px, 24px 24px, 24px 24px',
            backgroundPosition: `0 0, 0 0, 0 ${drift * 0.2}px, 0 ${drift * 0.2}px, 0 ${drift * 0.2}px, 0 ${drift * 0.2}px`,
          }}
        />
      );
    }
    case 'kinetic': {
      // flat black, one wide accent band sweeping slowly: the type does all the talking
      const shift = (frame * 0.6) % 400;
      return (
        <AbsoluteFill
          style={{
            backgroundColor: '#060606',
            backgroundImage: `linear-gradient(115deg, transparent ${30 + shift / 40}%, ${theme.accent}14 ${36 + shift / 40}%, ${theme.accent}14 ${44 + shift / 40}%, transparent ${50 + shift / 40}%)`,
          }}
        />
      );
    }
    case 'chapter':
      return (
        <AbsoluteFill
          style={{
            backgroundColor: '#12151b',
            backgroundImage: [
              `radial-gradient(ellipse at 50% 40%, ${theme.accent}1f 0%, transparent 55%)`,
              'radial-gradient(ellipse at 50% 50%, transparent 55%, rgba(0,0,0,0.7) 100%)',
            ].join(', '),
          }}
        />
      );
    case 'atlas':
      return (
        <AbsoluteFill
          style={{
            backgroundColor: '#e7eef4',
            backgroundImage: [
              'radial-gradient(ellipse at 50% 50%, rgba(255,255,255,0.7) 0%, transparent 70%)',
              'repeating-linear-gradient(0deg, rgba(29,111,214,0.09) 0 1px, transparent 1px 90px)',
              'repeating-linear-gradient(90deg, rgba(29,111,214,0.06) 0 1px, transparent 1px 90px)',
            ].join(', '),
            backgroundPosition: `0 0, 0 ${drift * 0.1}px, ${drift * 0.1}px 0`,
          }}
        />
      );
    case 'newsroom':
      return (
        <AbsoluteFill style={{backgroundColor: '#f6f5f1'}}>
          <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 26, background: theme.accent}} />
          <div style={{position: 'absolute', top: 26, left: 0, right: 0, height: 4, background: '#111'}} />
          <div
            style={{
              position: 'absolute',
              inset: 0,
              backgroundImage: 'repeating-linear-gradient(90deg, rgba(0,0,0,0.035) 0 1px, transparent 1px 180px)',
            }}
          />
        </AbsoluteFill>
      );
    case 'notebook':
      return (
        <AbsoluteFill
          style={{
            backgroundColor: '#fdfcf7',
            backgroundImage: [
              'linear-gradient(90deg, transparent 118px, rgba(220,38,38,0.45) 118px, rgba(220,38,38,0.45) 121px, transparent 121px)',
              'repeating-linear-gradient(0deg, transparent 0 63px, rgba(37,99,235,0.22) 63px 65px)',
            ].join(', '),
            backgroundPosition: `0 0, 0 ${(drift * 0.08) % 65}px`,
          }}
        />
      );
    case 'graphite':
      return (
        <AbsoluteFill
          style={{
            backgroundColor: '#ecebe6',
            backgroundImage: [
              'radial-gradient(ellipse at 50% 50%, transparent 50%, rgba(55,65,81,0.12) 100%)',
              'linear-gradient(rgba(55,65,81,0.10) 1px, transparent 1px)',
              'linear-gradient(90deg, rgba(55,65,81,0.10) 1px, transparent 1px)',
            ].join(', '),
            backgroundSize: '100% 100%, 40px 40px, 40px 40px',
          }}
        />
      );
    case 'stage':
      return (
        <AbsoluteFill style={{backgroundColor: '#ffffff'}}>
          <div style={{position: 'absolute', left: '6%', right: '6%', bottom: '30%', height: 5, borderRadius: 3, background: 'rgba(31,41,55,0.18)'}} />
        </AbsoluteFill>
      );
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
