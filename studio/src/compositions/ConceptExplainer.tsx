import React from 'react';
import {ThemedVideo} from '../components/ThemedVideo';
import type {VideoProps} from '../types';

/** Concept explainers and case studies: dark gradient, glass cards, animated charts. */
export const ConceptExplainer: React.FC<VideoProps> = (props) => <ThemedVideo {...props} themeId="concept" />;
