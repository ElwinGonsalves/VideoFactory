import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {buildTheme} from '../theme';
import type {ThemeId, VideoProps} from '../types';
import {Background} from './Background';
import {Captions} from './Captions';
import {SafeZone} from './SafeZone';
import {SceneView} from './SceneView';

const FADE_FRAMES = 8;
/** Vertical band kept free of scene content so captions never overlap it. */
const CAPTION_BAND = 230;

const SceneFrame: React.FC<{children: React.ReactNode; frames: number}> = ({children, frames}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, FADE_FRAMES, frames - FADE_FRAMES, frames], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{opacity, justifyContent: 'center', alignItems: 'center'}}>{children}</AbsoluteFill>
  );
};

/** Shared renderer behind every composition; compositions differ only by `themeId`. */
export const ThemedVideo: React.FC<VideoProps & {themeId: ThemeId}> = (props) => {
  const {fps} = useVideoConfig();
  const {scenes, captions, captionStyle, brand, aspectRatio, audioSrc, showSafeZones, themeId} = props;
  const theme = buildTheme(themeId, brand);
  const dark = theme.background === 'gradient';
  const hasCaptions = captionStyle !== 'none' && captions.length > 0;

  return (
    <AbsoluteFill>
      <Background theme={theme} brand={brand} />
      <SafeZone ratio={aspectRatio} showOverlay={showSafeZones}>
        {/* position:relative so scene AbsoluteFills stay inside the safe-zone padding. */}
        <div style={{position: 'relative', width: '100%', height: hasCaptions ? `calc(100% - ${CAPTION_BAND}px)` : '100%'}}>
          {scenes.map((scene, i) => {
            const from = Math.round(scene.start * fps);
            const frames = Math.max(1, Math.round((scene.end - scene.start) * fps));
            return (
              <Sequence key={`${i}-${scene.start}`} from={from} durationInFrames={frames}>
                <SceneFrame frames={frames}>
                  <SceneView visual={scene.visual} theme={theme} brand={brand} ratio={aspectRatio} />
                </SceneFrame>
              </Sequence>
            );
          })}
        </div>
      </SafeZone>
      <Captions captions={captions} style={captionStyle} ratio={aspectRatio} brand={brand} dark={dark} />
      {audioSrc ? <Audio src={staticFile(audioSrc)} /> : null}
    </AbsoluteFill>
  );
};
