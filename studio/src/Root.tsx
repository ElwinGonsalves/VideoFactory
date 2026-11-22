import React from 'react';
import {Composition} from 'remotion';
import type {CalculateMetadataFunction} from 'remotion';
import {ConceptExplainer} from './compositions/ConceptExplainer';
import {UniversalCustom} from './compositions/UniversalCustom';
import {VoxEditorial} from './compositions/VoxEditorial';
import {WhiteboardDraw} from './compositions/WhiteboardDraw';
import {defaultProps} from './defaults';
import {DIMENSIONS, FPS} from './format';
import type {VideoProps} from './types';

/** Size and length come from the props: aspect ratio picks dimensions, audio length picks duration. */
const calculateMetadata: CalculateMetadataFunction<VideoProps> = ({props}) => {
  const {width, height} = DIMENSIONS[props.aspectRatio];
  return {width, height, fps: FPS, durationInFrames: Math.max(1, Math.ceil(props.durationSec * FPS))};
};

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
  </>
);
