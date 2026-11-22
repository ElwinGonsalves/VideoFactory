import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig} from 'remotion';
import {buildTheme} from '../theme';
import type {ThemeId, VideoProps} from '../types';
import {Background} from './Background';
import {Captions} from './Captions';
import {Cover} from './Cover';
import {SafeZone} from './SafeZone';
import {SceneView} from './SceneView';
import {Transition} from './Transition';

/** Vertical band kept free of scene content so captions never overlap it. */
const CAPTION_BAND = 230;

/** Shared renderer behind every composition; compositions differ only by `themeId`. */
export const ThemedVideo: React.FC<VideoProps & {themeId: ThemeId}> = (props) => {
  const {fps} = useVideoConfig();
  const {scenes, captions, captionStyle, brand, aspectRatio, audioSrc, showSafeZones, themeId} = props;
  const theme = buildTheme(themeId, brand);
  const dark = theme.background === 'gradient';
  const hasCaptions = captionStyle !== 'none' && captions.length > 0;
  const transition = props.transition ?? 'fade';
  const hide = props.qaHideContent === true;

  return (
    <AbsoluteFill>
      <Background theme={theme} brand={brand} />
      <SafeZone ratio={aspectRatio} showOverlay={showSafeZones && !hide}>
        {/* position:relative so scene AbsoluteFills stay inside the safe-zone padding. */}
        <div style={{position: 'relative', width: '100%', height: hasCaptions ? `calc(100% - ${CAPTION_BAND}px)` : '100%'}}>
          {hide
            ? null
            : scenes.map((scene, i) => {
                const from = Math.round(scene.start * fps);
                const frames = Math.max(1, Math.round((scene.end - scene.start) * fps));
                return (
                  <Sequence key={`${i}-${scene.start}`} from={from} durationInFrames={frames}>
                    {/* Scene 0 never fades in, so frame 0 is a finished, high-contrast image. */}
                    <Transition style={transition} frames={frames} enter={i > 0}>
                      <SceneView visual={scene.visual} theme={theme} brand={brand} ratio={aspectRatio} />
                    </Transition>
                  </Sequence>
                );
              })}
        </div>
      </SafeZone>
      {hide ? null : <Captions captions={captions} style={captionStyle} ratio={aspectRatio} brand={brand} dark={dark} />}
      {props.coverText && !hide ? <Cover text={props.coverText} theme={theme} brand={brand} ratio={aspectRatio} /> : null}
      {audioSrc ? <Audio src={staticFile(audioSrc)} /> : null}
    </AbsoluteFill>
  );
};
