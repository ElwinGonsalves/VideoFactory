import {
  BookOpen,
  Brain,
  Building2,
  Clock,
  Coins,
  Factory,
  Flame,
  Globe,
  Handshake,
  Heart,
  Lightbulb,
  Lock,
  Megaphone,
  Rocket,
  Scale,
  Search,
  Shield,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  Users,
  Wallet,
  Zap,
} from 'lucide-react';
import type {LucideIcon} from 'lucide-react';

/**
 * Icon names usable as `visual.icon`. Keep in sync with pipeline/visuals.py ICON_NAMES
 * (tests/test_visuals.py fails when they drift).
 */
export const ICONS: Record<string, LucideIcon> = {
  'book-open': BookOpen,
  brain: Brain,
  building: Building2,
  clock: Clock,
  coins: Coins,
  factory: Factory,
  flame: Flame,
  globe: Globe,
  handshake: Handshake,
  heart: Heart,
  lightbulb: Lightbulb,
  lock: Lock,
  megaphone: Megaphone,
  rocket: Rocket,
  scale: Scale,
  search: Search,
  shield: Shield,
  sparkles: Sparkles,
  target: Target,
  'trending-down': TrendingDown,
  'trending-up': TrendingUp,
  users: Users,
  wallet: Wallet,
  zap: Zap,
};

export const resolveIcon = (name?: string): LucideIcon => ICONS[(name ?? '').toLowerCase()] ?? Sparkles;