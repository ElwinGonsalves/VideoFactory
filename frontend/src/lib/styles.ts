// Every style the router knows (pipeline/router.py), described in plain words.
// Card images are real frames from the Remotion compositions (scripts/render_style_cards.py).
export type StyleInfo = {name: string; blurb: string; image: string; engine: string; featured?: boolean};

export const STYLE_INFO: Record<string, StyleInfo> = {
  concept_explainer: {name: 'Concept explainer', blurb: 'Counters, charts and diagrams for one big idea.', image: 'concept', engine: 'Remotion', featured: true},
  case_study: {name: 'Case study', blurb: 'A real company told as a dated timeline.', image: 'case_study', engine: 'Remotion', featured: true},
  vox_documentary: {name: 'Vox documentary', blurb: 'Paper cut-outs, archive photos, editorial voice.', image: 'vox', engine: 'Remotion', featured: true},
  whiteboard: {name: 'Whiteboard', blurb: 'Hand-drawn sketches that draw on as you speak.', image: 'whiteboard', engine: 'Remotion + Rough.js', featured: true},
  stickman: {name: 'Stickman', blurb: 'A stick figure reacts to every line. Comedy timing.', image: 'stickman', engine: 'Remotion', featured: true},
  long_form: {name: 'Long-form 16:9', blurb: 'Chaptered YouTube video, 3 to 5 chapters.', image: 'long_form', engine: 'Remotion', featured: true},
  kinetic_type: {name: 'Kinetic type', blurb: 'Fast cuts and big words.', image: 'kinetic', engine: 'Remotion'},
  editorial_map: {name: 'Editorial map', blurb: 'Countries light up as the story moves.', image: 'map', engine: 'Remotion + d3-geo'},
  news_breakdown: {name: 'News breakdown', blurb: 'Hard cuts, sourced claims, Vox look.', image: 'vox', engine: 'Remotion'},
  hand_drawn: {name: 'Hand-drawn', blurb: 'Whiteboard with a looser pen.', image: 'whiteboard', engine: 'Remotion + Rough.js'},
  sketch: {name: 'Sketch', blurb: 'Pencil-style diagrams.', image: 'whiteboard', engine: 'Remotion + Rough.js'},
  ui_demo: {name: 'UI demo', blurb: 'Clean product walkthrough look.', image: 'kinetic', engine: 'Remotion'},
  hybrid_or_custom: {name: 'Hybrid / custom', blurb: 'Mix visual types freely.', image: 'concept', engine: 'Remotion'},
  reference_blueprint: {name: 'From a Style Blueprint', blurb: 'Beats copied from a reference video you studied.', image: 'kinetic', engine: 'Remotion'},
  openmontage: {name: 'OpenMontage', blurb: 'Archive-image documentary montage.', image: 'vox', engine: 'OpenMontage'},
  explainroo: {name: 'Explainroo', blurb: 'Whiteboard engine by explainroo.', image: 'whiteboard', engine: 'Explainroo'},
  handanim: {name: 'handanim', blurb: 'Hand-animation engine (MCP).', image: 'whiteboard', engine: 'handanim'},
  math_science: {name: 'Math & science', blurb: '3Blue1Brown-style animation.', image: 'long_form', engine: 'Manim'},
  algorithm: {name: 'Algorithm', blurb: 'Step-through visual of an algorithm.', image: 'long_form', engine: 'Manim'},
  clip_repurpose: {name: 'Clip repurpose', blurb: 'Cut a long video into Shorts.', image: 'kinetic', engine: 'Clipper'},
};

export const styleInfo = (id: string): StyleInfo =>
  STYLE_INFO[id] ?? {name: id.replace(/_/g, ' '), blurb: '', image: 'concept', engine: 'Remotion'};
export const styleImage = (id: string) => `/styles/${styleInfo(id).image}.webp`;
