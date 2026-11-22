import React from 'react';
import {ThemedVideo} from '../components/ThemedVideo';
import type {VideoProps} from '../types';

/** Any custom look: pick `props.theme` (concept | vox | whiteboard | minimal). */
export const UniversalCustom: React.FC<VideoProps> = (props) => (
  <ThemedVideo {...props} themeId={props.theme ?? 'minimal'} />
);
