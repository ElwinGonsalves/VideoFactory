import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Theme} from '../theme';

/** 0 -> 1 progress using a spring, starting after `delay` frames. */
export const useSpring = (delay = 0): number => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return spring({frame: frame - delay, fps, config: {damping: 200}});
};

/** Linear 0 -> 1 progress over `duration` frames after `delay`. */
export const useProgress = (delay: number, duration: number): number => {
  const frame = useCurrentFrame();
  return interpolate(frame, [delay, delay + duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
};

/** Surface for content; look depends on theme.card. */
export const Card: React.FC<{theme: Theme; children: React.ReactNode; style?: React.CSSProperties}> = ({
  theme,
  children,
  style,
}) => {
  const base: React.CSSProperties = {
    background: theme.surface,
    color: theme.text,
    padding: 48,
    boxSizing: 'border-box',
    width: '100%',
  };
  const byKind: Record<Theme['card'], React.CSSProperties> = {
    glass: {borderRadius: 28, border: '1px solid rgba(255,255,255,0.18)', backdropFilter: 'blur(8px)'},
    paper: {border: '10px solid #fff', boxShadow: '0 14px 30px rgba(0,0,0,0.25)', transform: 'rotate(-0.8deg)'},
    sketch: {border: `5px solid ${theme.text}`, borderRadius: '18px 40px 22px 36px'},
    flat: {borderRadius: 12, boxShadow: '0 6px 20px rgba(0,0,0,0.12)'},
  };
  return <div style={{...base, ...byKind[theme.card], ...style}}>{children}</div>;
};

/** Text with an accent sweep behind it (highlighter) or underline draw-on (whiteboard). */
export const Highlight: React.FC<{theme: Theme; delay?: number; children: React.ReactNode}> = ({
  theme,
  delay = 8,
  children,
}) => {
  const p = useProgress(delay, 18);
  const underline = theme.card === 'sketch';
  return (
    <span
      style={{
        backgroundImage: `linear-gradient(${theme.accent}, ${theme.accent})`,
        backgroundRepeat: 'no-repeat',
        backgroundPosition: underline ? '0 100%' : '0 60%',
        backgroundSize: `${p * 100}% ${underline ? '10%' : '55%'}`,
        color: theme.card === 'glass' ? '#fff' : theme.text,
        padding: '0 8px',
      }}
    >
      {children}
    </span>
  );
};

/** Stroke-dashoffset draw-on for any SVG path. Use inside an <svg>. */
export const DrawPath: React.FC<{
  d: string;
  color: string;
  delay?: number;
  duration?: number;
  width?: number;
}> = ({d, color, delay = 0, duration = 20, width = 6}) => {
  const p = useProgress(delay, duration);
  return (
    <path
      d={d}
      pathLength={1}
      fill="none"
      stroke={color}
      strokeWidth={width}
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeDasharray={1}
      strokeDashoffset={1 - p}
    />
  );
};
