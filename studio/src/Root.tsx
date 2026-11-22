import React from 'react';
import {Composition} from 'remotion';
import type {CalculateMetadataFunction} from 'remotion';
import brand from '../brands/default/brand.json';
import {ConceptExplainer} from './compositions/ConceptExplainer';
import {Thumbnail} from './compositions/Thumbnail';
import {UniversalCustom} from './compositions/UniversalCustom';
import {VoxEditorial} from './compositions/VoxEditorial';
import {WhiteboardDraw} from './compositions/WhiteboardDraw';
import {defaultProps} from './defaults';
import {DIMENSIONS, FPS} from './format';
import type {ThumbnailProps, VideoProps} from './types';

/** Size and length come from the props: aspect ratio picks dimensions, audio length picks duration. */
const calculateMetadata: CalculateMetadataFunction<VideoProps> = ({props}) => {
  const {width, height} = DIMENSIONS[props.aspectRatio];
  return {width, height, fps: FPS, durationInFrames: Math.max(1, Math.ceil(props.durationSec * FPS))};
};

/** YouTube recommends 1280x720 for 16:9 thumbnails; vertical covers use the feed size. */
const thumbnailMetadata: CalculateMetadataFunction<ThumbnailProps> = ({props}) => {
  const size = props.aspectRatio === '16:9' ? {width: 1280, height: 720} : DIMENSIONS[props.aspectRatio];
  return {...size, fps: FPS, durationInFrames: 1};
};

const thumbnailDefaults: ThumbnailProps = {aspectRatio: '16:9', text: 'Why prices rise', subtext: 'A 60-second explainer', brand};

const compositions = {ConceptExplainer, VoxEditorial, WhiteboardDraw, UniversalCustom};

export const Root: React.FC = () => (
  <>
    {Object.entries(compositions).map(([id, component]) => (
      <Composition
        key={id}
        id={id}
        component={component}
        width={1080}
        height={1920}
        fps={FPS}
        durationInFrames={Math.ceil(defaultProps.durationSec * FPS)}
        defaultProps={defaultProps}
        calculateMetadata={calculateMetadata}
      />
    ))}
    <Composition
      id="Thumbnail"
      component={Thumbnail}
      width={1280}
      height={720}
      fps={FPS}
      durationInFrames={1}
      defaultProps={thumbnailDefaults}
      calculateMetadata={thumbnailMetadata}
    />
  </>
);
