import React from 'react';
import {Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {isPortrait} from '../format';
import type {Theme} from '../theme';
import type {AspectRatio, Brand, Visual} from '../types';
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

const Body: React.FC<{theme: Theme; brand: Brand; text: string}> = ({theme, brand, text}) => (
  <div style={{fontFamily: theme.font, fontSize: brand.typography.body.size, color: theme.muted, lineHeight: 1.3}}>
    {text}
  </div>
);

const Stat: React.FC<Props> = ({visual, theme, brand}) => {
  const s = useSpring();
  return (
    <Card theme={theme} style={{textAlign: 'center', transform: `scale(${0.85 + 0.15 * s})`, opacity: s}}>
      <div style={{fontFamily: theme.headingFont, fontWeight: 800, fontSize: 200, color: theme.accent, lineHeight: 1}}>
        {visual.value}
      </div>
      <div style={{fontFamily: theme.font, fontSize: brand.typography.h2.size * 0.65, color: theme.text, marginTop: 16}}>
        {visual.label}
      </div>
    </Card>
  );
};

const Bullets: React.FC<Props> = ({visual, theme, brand}) => {
  const frame = useCurrentFrame();
  return (
    <Card theme={theme}>
      {visual.heading ? <Heading theme={theme} brand={brand} text={visual.heading} size={64} /> : null}
      <ul style={{margin: '24px 0 0', padding: 0, listStyle: 'none'}}>
        {(visual.items ?? []).map((item, i) => {
          const o = interpolate(frame, [10 + i * 10, 22 + i * 10], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          });
          return (
            <li
              key={item}
              style={{
                fontFamily: theme.font,
                fontSize: brand.typography.body.size,
                color: theme.text,
                opacity: o,
                transform: `translateX(${(1 - o) * -40}px)`,
                margin: '14px 0',
              }}
            >
              <span style={{color: theme.accent, marginRight: 16}}>&#9679;</span>
              {item}
            </li>
          );
        })}
      </ul>
    </Card>
  );
};

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

const ImageView: React.FC<Props> = ({visual, theme, brand}) => {
  const s = useSpring();
  return (
    <Card theme={theme} style={{padding: theme.card === 'paper' ? 16 : 24, opacity: s}}>
      {visual.src ? (
        <Img src={staticFile(visual.src)} style={{width: '100%', maxHeight: 760, objectFit: 'cover', display: 'block'}} />
      ) : null}
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

export const SceneView: React.FC<Props> = (props) => {
  const {visual, theme, brand} = props;
  switch (visual.type) {
    case 'stat':
      return <Stat {...props} />;
    case 'bullets':
      return <Bullets {...props} />;
    case 'chart':
      return <Chart {...props} />;
    case 'image':
      return <ImageView {...props} />;
    case 'flow':
      return <Flow {...props} />;
    case 'quote':
      return (
        <Card theme={theme}>
          <div style={{fontFamily: theme.headingFont, fontSize: 64, fontStyle: 'italic', color: theme.text}}>
            &ldquo;{visual.text}&rdquo;
          </div>
          {visual.label ? <Body theme={theme} brand={brand} text={`- ${visual.label}`} /> : null}
        </Card>
      );
    default:
      return (
        <div>
          <Heading theme={theme} brand={brand} text={visual.heading ?? ''} />
          {visual.text ? (
            <div style={{marginTop: 28}}>
              <Body theme={theme} brand={brand} text={visual.text} />
            </div>
          ) : null}
        </div>
      );
  }
};
