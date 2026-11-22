import brand from '../brands/default/brand.json';
import type {VideoProps} from './types';

export const defaultProps: VideoProps = {
  aspectRatio: '9:16',
  title: 'Sample',
  durationSec: 6,
  captionStyle: 'word_highlight',
  showSafeZones: false,
  brand,
  scenes: [
    {start: 0, end: 3, visual: {type: 'headline', heading: 'Why prices rise', text: 'A one-minute explainer'}},
    {start: 3, end: 6, visual: {type: 'stat', value: '3x', label: 'in ten years'}},
  ],
  captions: [
    {word: 'Why', start: 0.2, end: 0.5},
    {word: 'prices', start: 0.5, end: 0.9},
    {word: 'rise', start: 0.9, end: 1.3},
  ],
};
