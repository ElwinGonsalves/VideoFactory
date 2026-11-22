import type {AspectRatio} from './types';

export const FPS = 30;

export type Dimensions = {width: number; height: number};
export type Insets = {top: number; right: number; bottom: number; left: number};

export const DIMENSIONS: Record<AspectRatio, Dimensions> = {
  '9:16': {width: 1080, height: 1920},
  '16:9': {width: 1920, height: 1080},
  '1:1': {width: 1080, height: 1080},
};

/**
 * Safe-zone insets in pixels.
 * 9:16: keep content above the bottom 22% and left of the right 15% (Shorts/Reels/TikTok UI).
 * Other ratios: a plain 5% margin.
 */
export const safeInsets = (ratio: AspectRatio): Insets => {
  const {width, height} = DIMENSIONS[ratio];
  if (ratio === '9:16') {
    return {
      top: Math.round(height * 0.06),
      right: Math.round(width * 0.15),
      bottom: Math.round(height * 0.22),
      left: Math.round(width * 0.06),
    };
  }
  const m = Math.round(Math.min(width, height) * 0.05);
  return {top: m, right: m, bottom: m, left: m};
};

export const isPortrait = (ratio: AspectRatio): boolean => ratio === '9:16';
