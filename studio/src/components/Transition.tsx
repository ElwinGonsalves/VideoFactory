import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import type {TransitionStyle} from '../types';

const IN = 9;
const OUT = 7;

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

/**
 * Wraps one scene and animates its entrance/exit.
 * `enter=false` shows the scene fully from its first frame (used for scene 0 so frame 0 is a clean cover).
 */
export const Transition: React.FC<{
  style: TransitionStyle;
  frames: number;
  enter: boolean;
  children: React.ReactNode;
}> = ({style, frames, enter, children}) => {
  const frame = useCurrentFrame();
  const pIn = enter ? interpolate(frame, [0, IN], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)}) : 1;
  const pOut = interpolate(frame, [frames - OUT, frames], [0, 1], {...clamp, easing: Easing.in(Easing.cubic)});
  const base: React.CSSProperties = {justifyContent: 'center', alignItems: 'center'};

  switch (style) {
    case 'hard_cut':
      return <AbsoluteFill style={base}>{children}</AbsoluteFill>;
    case 'whip_pan': {
      const x = (1 - pIn) * 110 - pOut * 110;
      const blur = Math.abs(x) > 1 ? Math.min(18, Math.abs(x) / 4) : 0;
      return <AbsoluteFill style={{...base, transform: `translateX(${x}%)`, filter: `blur(${blur}px)`}}>{children}</AbsoluteFill>;
    }
    case 'paper_slide': {
      const y = (1 - pIn) * 60 - pOut * 40;
      const rot = (1 - pIn) * -3 + pOut * 2;
      return (
        <AbsoluteFill style={{...base, transform: `translateY(${y}%) rotate(${rot}deg)`, opacity: Math.min(pIn * 2, 1 - pOut)}}>
          {children}
        </AbsoluteFill>
      );
    }
    case 'pen_draw': {
      const reveal = pIn * 100;
      return (
        <AbsoluteFill style={{...base, clipPath: `inset(0 ${100 - reveal}% 0 0)`, opacity: 1 - pOut}}>{children}</AbsoluteFill>
      );
    }
    default:
      return <AbsoluteFill style={{...base, opacity: Math.min(pIn, 1 - pOut)}}>{children}</AbsoluteFill>;
  }
};
