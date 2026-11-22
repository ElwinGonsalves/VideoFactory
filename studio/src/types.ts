export type AspectRatio = '9:16' | '16:9' | '1:1';
export type CaptionStyle = 'word_highlight' | 'phrase_box' | 'minimal_editorial' | 'none';
export type ThemeId = 'concept' | 'vox' | 'whiteboard' | 'minimal';

export type Caption = {word: string; start: number; end: number};

export type ChartDatum = {label: string; value: number};

export type Visual = {
  type: 'headline' | 'stat' | 'bullets' | 'chart' | 'image' | 'quote' | 'flow';
  heading?: string;
  text?: string;
  value?: string;
  label?: string;
  items?: string[];
  data?: ChartDatum[];
  /** Path relative to studio/public (e.g. assets/media/foo.jpg). */
  src?: string;
  credit?: string;
};

export type Scene = {
  start: number;
  end: number;
  visual: Visual;
};

export type Brand = {
  name: string;
  colors: {
    primary: string;
    primaryLight: string;
    textDark: string;
    textLight: string;
    bgLight: string;
    bgDark: string;
  };
  fonts: {primary: string; mono: string};
  typography: {
    h1: {size: number; weight: number};
    h2: {size: number; weight: number};
    body: {size: number; weight: number};
  };
};

export type VideoProps = {
  aspectRatio: AspectRatio;
  title: string;
  durationSec: number;
  scenes: Scene[];
  captions: Caption[];
  captionStyle: CaptionStyle;
  brand: Brand;
  /** Path relative to studio/public, e.g. assets/mixed_master.wav. */
  audioSrc?: string;
  showSafeZones: boolean;
  /** Only used by UniversalCustom. */
  theme?: ThemeId;
};
