export type AspectRatio = '9:16' | '16:9' | '1:1';
export type CaptionStyle = 'word_highlight' | 'phrase_box' | 'minimal_editorial' | 'none';
export type ThemeId = 'concept' | 'vox' | 'whiteboard' | 'minimal';
/** Scene-to-scene transition; matches blueprint `pacing.transition_style`. */
export type TransitionStyle = 'hard_cut' | 'fade' | 'whip_pan' | 'paper_slide' | 'pen_draw';

export type Caption = {word: string; start: number; end: number};

export type ChartDatum = {label: string; value: number};

export type StickPose = 'idle' | 'point' | 'shrug' | 'run' | 'celebrate' | 'panic' | 'think';

export type TimelineEvent = {when: string; label: string};

export type Visual = {
  /**
   * Concrete visuals: stat, counter, chart, flow, diagram, sketch, cutout, timeline, stickman, image, map.
   * headline / bullets / quote are text-first types; the renderer always draws an illustration with them
   * (never plain text on an empty background).
   */
  type:
    | 'headline'
    | 'stat'
    | 'bullets'
    | 'chart'
    | 'image'
    | 'quote'
    | 'flow'
    | 'map'
    | 'diagram'
    | 'counter'
    | 'sketch'
    | 'cutout'
    | 'timeline'
    | 'stickman';
  heading?: string;
  text?: string;
  value?: string;
  label?: string;
  items?: string[];
  data?: ChartDatum[];
  /** Path relative to studio/public (e.g. assets/media/foo.jpg). */
  src?: string;
  credit?: string;
  /** map: ISO A3 codes to highlight, e.g. ["USA", "IND"]. */
  countries?: string[];
  /** Icon name from components/visuals/icons.tsx (sketch, cutout, diagram hub, headline art). */
  icon?: string;
  /** sketch: labels drawn one after another around the icon. */
  draw_cues?: string[];
  /** timeline: dated milestones, in order. */
  events?: TimelineEvent[];
  /** stickman: pose and speech-bubble line. */
  pose?: StickPose;
  bubble?: string;
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
  /** The style id (case_study, news_breakdown, ...): its own palette and background over the theme. */
  variant?: string;
  /** Frame-0 cover: 2-5 word hook shown full-contrast for the first 0.5 s. Empty = no cover. */
  coverText?: string;
  transition?: TransitionStyle;
  /** Visual QA: render background only, so a pixel diff isolates content. */
  qaHideContent?: boolean;
};

export type ThumbnailProps = {
  aspectRatio: AspectRatio;
  text: string;
  subtext?: string;
  /** Background frame, relative to studio/public. */
  bgSrc?: string;
  /** Blur in px; set for video frames (which contain text), 0 for photos. */
  bgBlur?: number;
  brand: Brand;
  theme?: ThemeId;
};
