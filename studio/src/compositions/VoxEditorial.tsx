import React from 'react';
import {ThemedVideo} from '../components/ThemedVideo';
import type {VideoProps} from '../types';

/** Vox-style editorial: paper grain, print-bordered photos, highlighter sweeps. */
export const VoxEditorial: React.FC<VideoProps> = (props) => <ThemedVideo {...props} themeId="vox" />;
