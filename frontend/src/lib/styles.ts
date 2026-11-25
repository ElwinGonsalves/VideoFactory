// Every style the router knows (pipeline/router.py), described in plain words.
// Card images are real frames from the Remotion compositions, each in its style's own look
// (scripts/render_style_cards.py renders them with the style id as the theme variant).
export type StyleFamily = 'explain' | 'document' | 'draw' | 'engine';
export type StyleInfo = {name: string; blurb: string; bestFor: string; image: string; engine: string; family: StyleFamily; featured?: boolean};

export const FAMILIES: {id: StyleFamily; label: string; hint: string}[] = [
  {id: 'explain', label: 'Explainers', hint: 'Numbers, diagrams and bold type'},
  {id: 'document', label: 'Documentary', hint: 'Paper, maps and the newsroom'},
  {id: 'draw', label: 'Hand-drawn', hint: 'Markers, pens and pencils'},
  {id: 'engine', label: 'Specialist engines', hint: 'Manim, montage, clips and more'},
];

export const STYLE_INFO: Record<string, StyleInfo> = {
  concept_explainer: {name: 'Concept explainer', blurb: 'Counters, charts and diagrams on a dark glass stage.', bestFor: 'One big idea, explained', image: 'concept', engine: 'Remotion', family: 'explain', featured: true},
  case_study: {name: 'Case study', blurb: 'A navy case file: dated timeline, the move, the results.', bestFor: 'A real company or event', image: 'case_study', engine: 'Remotion', family: 'explain', featured: true},
  kinetic_type: {name: 'Kinetic type', blurb: 'Huge words slam in on black. The text is the picture.', bestFor: 'Punchy hot takes', image: 'kinetic', engine: 'Remotion', family: 'explain', featured: true},
  long_form: {name: 'Long-form 16:9', blurb: 'Chaptered YouTube video, 3 to 5 chapters, cinematic.', bestFor: 'Deep dives over 3 min', image: 'long_form', engine: 'Remotion', family: 'explain', featured: true},
  vox_documentary: {name: 'Vox documentary', blurb: 'Paper cut-outs, archive photos, editorial voice.', bestFor: 'History and turning points', image: 'vox', engine: 'Remotion', family: 'document', featured: true},
  editorial_map: {name: 'Editorial map', blurb: 'Sea-blue atlas; countries light up as the story moves.', bestFor: 'Anything about places', image: 'map', engine: 'Remotion + d3-geo', family: 'document', featured: true},
  news_breakdown: {name: 'News breakdown', blurb: 'Newsroom masthead, hard cuts, sourced figures.', bestFor: 'Today’s news, explained', image: 'news', engine: 'Remotion', family: 'document', featured: true},
  whiteboard: {name: 'Whiteboard', blurb: 'Marker sketches on a grid board, drawn as you speak.', bestFor: 'Step-by-step how-tos', image: 'whiteboard', engine: 'Remotion + Rough.js', family: 'draw', featured: true},
  hand_drawn: {name: 'Notebook', blurb: 'Blue pen on lined notebook paper with a red margin.', bestFor: 'Study notes, self-help', image: 'hand_drawn', engine: 'Remotion + Rough.js', family: 'draw', featured: true},
  sketch: {name: 'Graphite sketch', blurb: 'Pencil diagrams on warm grey graph paper.', bestFor: 'Science and processes', image: 'sketch', engine: 'Remotion + Rough.js', family: 'draw', featured: true},
  stickman: {name: 'Stickman', blurb: 'A stick figure reacts to every line. Comedy timing.', bestFor: 'Funny, relatable stories', image: 'stickman', engine: 'Remotion', family: 'draw', featured: true},
  ui_demo: {name: 'UI demo', blurb: 'Clean, flat product walkthrough look.', bestFor: 'Apps and tools', image: 'concept', engine: 'Remotion', family: 'engine'},
  hybrid_or_custom: {name: 'Hybrid / custom', blurb: 'Mix visual types freely on the concept stage.', bestFor: 'Anything else', image: 'concept', engine: 'Remotion', family: 'engine'},
  reference_blueprint: {name: 'From a Style Blueprint', blurb: 'Beats copied from a reference video you studied.', bestFor: 'Matching a channel you like', image: 'kinetic', engine: 'Remotion', family: 'engine'},
  openmontage: {name: 'OpenMontage', blurb: 'Archive-image documentary montage.', bestFor: 'Photo-led history', image: 'vox', engine: 'OpenMontage', family: 'engine'},
  explainroo: {name: 'Explainroo', blurb: 'Whiteboard engine by explainroo.', bestFor: 'Whiteboard, alternative engine', image: 'whiteboard', engine: 'Explainroo', family: 'engine'},
  handanim: {name: 'handanim', blurb: 'Hand-animation engine (MCP).', bestFor: 'Hand-animated scenes', image: 'hand_drawn', engine: 'handanim', family: 'engine'},
  math_science: {name: 'Math & science', blurb: '3Blue1Brown-style animation.', bestFor: 'Equations and proofs', image: 'long_form', engine: 'Manim', family: 'engine'},
  algorithm: {name: 'Algorithm', blurb: 'Step-through visual of an algorithm.', bestFor: 'Code and CS concepts', image: 'sketch', engine: 'Manim', family: 'engine'},
  clip_repurpose: {name: 'Clip repurpose', blurb: 'Cut a long video into Shorts.', bestFor: 'Turning a long video into Shorts', image: 'kinetic', engine: 'Clipper', family: 'engine'},
};
export const styleInfo = (id: string): StyleInfo =>
  STYLE_INFO[id] ?? {name: id.replace(/_/g, ' '), blurb: '', bestFor: '', image: 'concept', engine: 'Remotion', family: 'engine'};
export const styleImage = (id: string) => `/styles/${styleInfo(id).image}.webp`;
