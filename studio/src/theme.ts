import type {Brand, ThemeId} from './types';

export type Background =
  | 'gradient' // concept: dark with an orbiting accent glow
  | 'paper' // vox: cream paper grain
  | 'board' // whiteboard: white with a light grid
  | 'plain' // minimal
  | 'dossier' // case study: navy blueprint grid, a file on a desk
  | 'kinetic' // kinetic type: black with one slow diagonal accent band
  | 'chapter' // long-form: charcoal with a wide cinematic vignette
  | 'atlas' // editorial map: pale sea-blue paper with latitude lines
  | 'newsroom' // news breakdown: off-white with a red masthead band
  | 'notebook' // hand-drawn: lined notebook paper with a red margin
  | 'graphite' // sketch: warm grey graph paper
  | 'stage'; // stickman: clean white with a floor line

export type Theme = {
  id: ThemeId;
  background: Background;
  card: 'glass' | 'paper' | 'sketch' | 'flat';
  /** Light text on a dark ground (captions and map land colours follow this). */
  dark: boolean;
  text: string;
  muted: string;
  accent: string;
  surface: string;
  font: string;
  headingFont: string;
};

const HAND = '"Comic Sans MS", "Segoe Print", "Bradley Hand", cursive'; // whiteboard marker (unchanged)
const INK = '"Segoe Print", "Bradley Hand", "Comic Sans MS", cursive'; // notebook pen
const PENCIL = '"Ink Free", "Segoe Print", "Comic Sans MS", cursive'; // graphite pencil
const IMPACT = '"Arial Black", Impact, "Helvetica Neue", sans-serif';
const SERIF = 'Georgia, "Times New Roman", serif';

const base = (id: ThemeId, brand: Brand): Theme => {
  const {colors, fonts} = brand;
  switch (id) {
    case 'vox':
      return {id, background: 'paper', card: 'paper', dark: false, text: '#1b1b1b', muted: '#5b5648', accent: '#f2c200', surface: '#fffdf6', font: fonts.primary, headingFont: SERIF};
    case 'whiteboard':
      return {id, background: 'board', card: 'sketch', dark: false, text: '#1f2937', muted: '#6b7280', accent: colors.primary, surface: '#ffffff', font: HAND, headingFont: HAND};
    case 'minimal':
      return {id, background: 'plain', card: 'flat', dark: false, text: colors.textDark, muted: colors.textLight, accent: colors.primary, surface: colors.bgLight, font: fonts.primary, headingFont: fonts.primary};
    default:
      return {id: 'concept', background: 'gradient', card: 'glass', dark: true, text: '#f8fafc', muted: '#cbd5e1', accent: colors.primary, surface: 'rgba(255,255,255,0.08)', font: fonts.primary, headingFont: fonts.primary};
  }
};

/**
 * Each style keeps its composition's layout but gets its own unmistakable look, so two styles that share
 * a composition (case study vs concept, news vs vox, notebook vs whiteboard) never render the same video.
 */
const VARIANTS: Record<string, Partial<Theme>> = {
  case_study: {background: 'dossier', accent: '#f5a524', muted: '#a9b8cc', text: '#f1f5f9', headingFont: SERIF},
  kinetic_type: {background: 'kinetic', accent: '#ffe14d', muted: '#d4d4d4', text: '#ffffff', headingFont: IMPACT, font: IMPACT},
  long_form: {background: 'chapter', accent: '#2dd4bf', muted: '#a7b3c2'},
  editorial_map: {background: 'atlas', accent: '#8cc8ff', text: '#14233a', muted: '#4b5d75', surface: '#f7fbff'},
  news_breakdown: {background: 'newsroom', accent: '#d92d20', text: '#111111', muted: '#4a4a4a', surface: '#ffffff', headingFont: IMPACT},
  hand_drawn: {background: 'notebook', accent: '#2563eb', text: '#1e3a8a', muted: '#475569', font: INK, headingFont: INK},
  sketch: {background: 'graphite', accent: '#c2410c', text: '#374151', muted: '#6b7280', font: PENCIL, headingFont: PENCIL},
  stickman: {background: 'stage', accent: '#ef4444'},
};

export const buildTheme = (id: ThemeId, brand: Brand, variant?: string): Theme => ({
  ...base(id, brand),
  ...(variant ? VARIANTS[variant] ?? {} : {}),
});
