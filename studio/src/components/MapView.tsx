import React from 'react';
import {continueRender, delayRender, staticFile} from 'remotion';
import {geoNaturalEarth1, geoPath} from 'd3-geo';
import type {Feature, FeatureCollection, Geometry} from 'geojson';
import type {Theme} from '../theme';
import type {Brand} from '../types';
import {Highlight, useProgress} from './primitives';

type Props = {iso: string; name: string};
type Countries = FeatureCollection<Geometry, Props>;

let cache: Countries | null = null;

/** Loads studio/public/geo/countries.geojson once per render process. */
const useCountries = (): Countries | null => {
  const [data, setData] = React.useState<Countries | null>(cache);
  const [handle] = React.useState(() => (cache ? null : delayRender('load countries.geojson')));
  React.useEffect(() => {
    if (cache || handle === null) return;
    fetch(staticFile('geo/countries.geojson'))
      .then((r) => r.json())
      .then((json: Countries) => {
        cache = json;
        setData(json);
        continueRender(handle);
      })
      .catch(() => continueRender(handle)); // missing file: render without the map instead of hanging
  }, [handle]);
  return data;
};

/** Vox-style editorial map: muted world, highlighted countries fill in one after another. */
export const MapView: React.FC<{
  countries: string[];
  heading?: string;
  label?: string;
  theme: Theme;
  brand: Brand;
  width: number;
}> = ({countries, heading, label, theme, brand, width}) => {
  const data = useCountries();
  const height = Math.round(width * 0.62);
  const focus = new Set(countries.map((c) => c.toUpperCase()));
  const focused = data?.features.filter((f) => focus.has(f.properties.iso)) ?? [];
  // Zoom to the highlighted countries when they are clustered; otherwise show the world.
  const target: FeatureCollection | Feature | null =
    focused.length > 0 && focused.length <= 4 ? {type: 'FeatureCollection', features: focused} : data;
  const projection = geoNaturalEarth1();
  if (target) projection.fitExtent([[24, 24], [width - 24, height - 24]], target);
  const path = geoPath(projection);
  const land = theme.dark ? 'rgba(255,255,255,0.14)' : 'rgba(40,40,40,0.16)';
  const border = theme.dark ? 'rgba(255,255,255,0.35)' : 'rgba(30,30,30,0.45)';
  const order = countries.map((c) => c.toUpperCase());

  return (
    <div style={{width: '100%'}}>
      {heading ? (
        <div style={{fontFamily: theme.headingFont, fontWeight: 800, fontSize: 60, color: theme.text, marginBottom: 20}}>
          <Highlight theme={theme}>{heading}</Highlight>
        </div>
      ) : null}
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{display: 'block', overflow: 'hidden'}}>
        {data?.features.map((f) => {
          const idx = order.indexOf(f.properties.iso);
          return idx >= 0 ? null : <path key={f.properties.iso + f.properties.name} d={path(f) ?? ''} fill={land} stroke={border} strokeWidth={1} />;
        })}
        {focused.map((f) => (
          <FocusCountry key={f.properties.iso} d={path(f) ?? ''} delay={8 + order.indexOf(f.properties.iso) * 10} color={brand.colors.primary} />
        ))}
      </svg>
      {label ? <div style={{fontFamily: theme.font, fontSize: 40, color: theme.muted, marginTop: 16}}>{label}</div> : null}
    </div>
  );
};

const FocusCountry: React.FC<{d: string; delay: number; color: string}> = ({d, delay, color}) => {
  const p = useProgress(delay, 14);
  return (
    <path
      d={d}
      fill={color}
      fillOpacity={0.15 + 0.75 * p}
      stroke={color}
      strokeWidth={3}
      pathLength={1}
      strokeDasharray={1}
      strokeDashoffset={1 - p}
    />
  );
};
