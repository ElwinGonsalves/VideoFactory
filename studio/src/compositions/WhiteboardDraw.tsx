import React from 'react';
import {ThemedVideo} from '../components/ThemedVideo';
import type {VideoProps} from '../types';

/** Hand-drawn whiteboard: sketch borders and stroke-dashoffset pen reveals. */
export const WhiteboardDraw: React.FC<VideoProps> = (props) => <ThemedVideo {...props} themeId="whiteboard" />;
