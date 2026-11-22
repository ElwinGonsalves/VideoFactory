import type {Brand, ThemeId} from './types';

export type Theme = {
  id: ThemeId;
  background: 'gradient' | 'paper' | 'board' | 'plain';
  card: 'glass' | 'paper' | 'sketch' | 'flat';
  text: string;
  muted: string;
  accent: string;
  surface: string;
  font: string;
  headingFont: string;
};

export const buildTheme = (id: ThemeId, brand: Brand): Theme => {
  const {colors, fonts} = brand;
  switch (id) {
    case 'vox':
      return {
        id,
        background: 'paper',
        card: 'paper',
        text: '#1b1b1b',
        muted: '#5b5648',
        accent: '#f2c200',
        surface: '#fffdf6',
        font: fonts.primary,
        headingFont: 'Georgia, "Times New Roman", serif',
      };
    case 'whiteboard':
      return {
        id,
        background: 'board',
        card: 'sketch',
        text: '#1f2937',
        muted: '#6b7280',
        accent: colors.primary,
        surface: '#ffffff',
        font: '"Comic Sans MS", "Segoe Print", "Bradley Hand", cursive',
        headingFont: '"Comic Sans MS", "Segoe Print", "Bradley Hand", cursive',
      };
    case 'minimal':
      return {
        id,
        background: 'plain',
        card: 'flat',
        text: colors.textDark,
        muted: colors.textLight,
        accent: colors.primary,
        surface: colors.bgLight,
        font: fonts.primary,
        headingFont: fonts.primary,
      };
    default:
      return {
        id: 'concept',
        background: 'gradient',
        card: 'glass',
        text: '#f8fafc',
        muted: '#cbd5e1',
        accent: colors.primary,
        surface: 'rgba(255,255,255,0.08)',
        font: fonts.primary,
        headingFont: fonts.primary,
      };
  }
};
