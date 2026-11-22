import React from 'react';
import {AbsoluteFill} from 'remotion';
import {DIMENSIONS, safeInsets} from '../format';
import type {AspectRatio} from '../types';

/** Pads children into the safe area and optionally draws the unsafe regions in red. */
export const SafeZone: React.FC<{
  ratio: AspectRatio;
  showOverlay?: boolean;
  children: React.ReactNode;
}> = ({ratio, showOverlay = false, children}) => {
  const ins = safeInsets(ratio);
  const {width, height} = DIMENSIONS[ratio];
  return (
    <>
      <AbsoluteFill
        style={{
          paddingTop: ins.top,
          paddingRight: ins.right,
          paddingBottom: ins.bottom,
          paddingLeft: ins.left,
          boxSizing: 'border-box',
        }}
      >
        {children}
      </AbsoluteFill>
      {showOverlay ? (
        <AbsoluteFill style={{pointerEvents: 'none'}}>
          <div style={{position: 'absolute', left: 0, top: 0, width, height: ins.top, background: 'rgba(255,0,0,0.25)'}} />
          <div style={{position: 'absolute', left: 0, bottom: 0, width, height: ins.bottom, background: 'rgba(255,0,0,0.25)'}} />
          <div style={{position: 'absolute', left: 0, top: 0, width: ins.left, height, background: 'rgba(255,0,0,0.25)'}} />
          <div style={{position: 'absolute', right: 0, top: 0, width: ins.right, height, background: 'rgba(255,0,0,0.25)'}} />
        </AbsoluteFill>
      ) : null}
    </>
  );
};
