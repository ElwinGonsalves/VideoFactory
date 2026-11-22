import React from 'react';
import {Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {isPortrait} from '../format';
import type {Theme} from '../theme';
import type {AspectRatio, Brand, Visual} from '../types';
import {MapView} from './MapView';
import {CounterVisual} from './visuals/CounterVisual';
import {CutoutVisual} from './visuals/CutoutVisual';
import {DiagramVisual} from './visuals/DiagramVisual';
import {SketchVisual} from './visuals/SketchVisual';
import {StickmanVisual} from './visuals/StickmanVisual';
import {TimelineVisual} from './visuals/TimelineVisual';
import {Card, DrawPath, Highlight, useProgress, useSpring} from './primitives';

type Props = {visual: Visual; theme: Theme; brand: Brand; ratio: AspectRatio};

const Heading: React.FC<{theme: Theme; brand: Brand; text: string; size?: number}> = ({theme, brand, text, size}) => (
  <div
    style={{
      fontFamily: theme.headingFont,
      fontWeight: brand.typography.h1.weight,
      fontSize: size ?? brand.typography.h1.size,
      lineHeight: 1.1,
      color: theme.text,
    }}
  >
    <Highlight theme={theme}>{text}</Highlight>
  </div>
);

const Chart: React.FC<Props> = ({visual, theme, brand}) => {
  const data = visual.data ?? [];
  const max = Math.max(1, ...data.map((d) => d.value));
  const p = useProgress(6, 30);
  return (
    <Card theme={theme}>
      {visual.heading ? <Heading theme={theme} brand={brand} text={visual.heading} size={56} /> : null}
      <div style={{display: 'flex', alignItems: 'flex-end', gap: 24, height: 480, marginTop: 32}}>
        {data.map((d, i) => (
          <div key={d.label} style={{flex: 1, textAlign: 'center', fontFamily: theme.font, color: theme.text}}>
            <div style={{fontSize: 36, marginBottom: 8}}>{d.value}</div>
            <div
              style={{
                height: (d.value / max) * 380 * p,
                background: i % 2 ? theme.accent : brand.colors.primaryLight,
                borderRadius: theme.card === 'sketch' ? '12px 18px 4px 6px' : 10,
                border: theme.card === 'sketch' ? `4px solid ${theme.text}` : 'none',
              }}
            />
            <div style={{fontSize: 30, marginTop: 10}}>{d.label}</div>
          </div>
        ))}
      </div>
    </Card>
  );
};

/** Archive/Wikimedia photo with a slow Ken Burns push so a still never sits frozen. */
const ImageView: React.FC<Props> = ({visual, theme, brand}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const s = useSpring();
  const t = interpolate(frame, [0, Math.max(1, durationInFrames)], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const scale = 1.04 + 0.12 * t;
  const panX = (t - 0.5) * -3.2; // percent
  const panY = (t - 0.5) * -2.2;
  return (
    <Card theme={theme} style={{padding: theme.card === 'paper' ? 16 : 24, opacity: s}}>
      <div style={{width: '100%', height: 820, overflow: 'hidden', position: 'relative'}}>
        {visual.src ? (
          <Img
            src={staticFile(visual.src)}
            style={{width: '100%', height: '100%', objectFit: 'cover', display: 'block', transform: `scale(${scale}) translate(${panX}%, ${panY}%)`}}
          />
        ) : null}
      </div>
      {visual.heading ? (
        <div style={{marginTop: 20}}>
          <Heading theme={theme} brand={brand} text={visual.heading} size={52} />
        </div>
      ) : null}
      {visual.credit ? (
        <div style={{fontFamily: theme.font, fontSize: 24, color: theme.muted, marginTop: 8}}>{visual.credit}</div>
      ) : null}
    </Card>
  );
};
/** Boxes connected by arrows that draw on one after another. */
const Flow: React.FC<Props> = ({visual, theme, brand, ratio}) => {
  const items = visual.items ?? [];
  const portrait = isPortrait(ratio);
  const box = {w: portrait ? 700 : 360, h: 150, gap: portrait ? 70 : 90};
  const vw = portrait ? box.w + 20 : items.length * (box.w + box.gap);
  const vh = portrait ? items.length * (box.h + box.gap) : box.h + 20;
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  return (
    <div style={{width: '100%'}}>
      {visual.heading ? <Heading theme={theme} brand={brand} text={visual.heading} size={60} /> : null}
      <svg viewBox={`0 0 ${vw} ${vh}`} width="100%" style={{maxHeight: Math.min(width, height) * 1.1, marginTop: 24}}>
        {items.map((label, i) => {
          const x = portrait ? 10 : i * (box.w + box.gap) + 10;
          const y = portrait ? i * (box.h + box.gap) : 10;
          const delay = i * 18;
          const shown = frame >= delay;
          const r = `M${x} ${y} h${box.w} v${box.h} h${-box.w} z`;
          const arrow = portrait
            ? `M${x + box.w / 2} ${y + box.h} v${box.gap}`
            : `M${x + box.w} ${y + box.h / 2} h${box.gap}`;
          return (
            <g key={label}>
              <DrawPath d={r} color={theme.text} delay={delay} width={6} />
              {i < items.length - 1 ? <DrawPath d={arrow} color={theme.accent} delay={delay + 14} width={8} /> : null}
              {shown ? (
                <text
                  x={x + box.w / 2}
                  y={y + box.h / 2 + 14}
                  textAnchor="middle"
                  fontFamily={theme.font}
                  fontSize={44}
                  fill={theme.text}
                >
                  {label}
                </text>
              ) : null}
            </g>
          );
        })}
      </svg>
    </div>
  );
};

const MapPanel: React.FC<Props> = ({visual, theme, brand, ratio}) => {
  const {width} = useVideoConfig();
  const inner = Math.round(width * (isPortrait(ratio) ? 0.79 : 0.9));
  return (
    <MapView
      countries={visual.countries ?? []}
      heading={visual.heading}
      label={visual.label}
      theme={theme}
      brand={brand}
      width={inner}
    />
  );
};

/**
 * Every visual type draws something concrete. The text-first types (headline, quote, bullets) are rendered
 * as an illustration that carries the text, so no scene is ever plain text on an empty background.
 */
export const SceneView: React.FC<Props> = (props) => {
  const {visual} = props;
  switch (visual.type) {
    case 'stat':
    case 'counter':
      return <CounterVisual {...props} />;
    case 'chart':
      return <Chart {...props} />;
    case 'image':
      return <ImageView {...props} />;
    case 'flow':
      return <Flow {...props} />;
    case 'map':
      return <MapPanel {...props} />;
    case 'diagram':
      return <DiagramVisual {...props} />;
    case 'bullets':
      return <DiagramVisual {...props} />;
    case 'cutout':
      return <CutoutVisual {...props} />;
    case 'quote':
      return <CutoutVisual {...props} visual={{...visual, heading: `\u201C${visual.text ?? visual.heading ?? ''}\u201D`, icon: visual.icon ?? 'megaphone'}} />;
    case 'timeline':
      return <TimelineVisual {...props} />;
    case 'stickman':
      return <StickmanVisual {...props} />;
    default:
      // sketch and headline
      return <SketchVisual {...props} />;
  }
};