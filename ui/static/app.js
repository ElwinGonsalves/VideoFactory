// video-factory UI. Vanilla JS, no build step. All untrusted text goes through esc().
'use strict';
const T = window.VF_TOKEN;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const file = (rel) => `/files/${rel.split('/').map(encodeURIComponent).join('/')}?t=${encodeURIComponent(T)}&v=${Date.now() % 1e6}`;
let OPTS = null;

const API_TIMEOUT_MS = 30000;      // normal calls; jobs run in the background, so nothing legitimate is slower
const UPLOAD_TIMEOUT_MS = 120000;  // file uploads (OAuth JSON, spreadsheets)
class ApiError extends Error {
  constructor(message, hint = '') { super(message); this.hint = hint; }
}
/** Turn any fetch failure into a sentence that says what to do. Never the browser's bare "Failed to fetch". */
function explainFetchError(e, ms) {
  if (e.name === 'AbortError') return new ApiError(`The server did not answer within ${Math.round(ms / 1000)} s.`, 'It may be busy rendering. Wait a moment and retry; check the log panel.');
  return new ApiError('Server not reachable.', 'Is `python ui/server.py` running? Start it again, then reload this page.');
}
async function api(path, opts = {}) {
  const init = {method: opts.method || 'GET', headers: {'X-VF-Token': T}};
  if (opts.body instanceof FormData) init.body = opts.body;
  else if (opts.body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(opts.body); }
  const ms = opts.timeout ?? (opts.body instanceof FormData ? UPLOAD_TIMEOUT_MS : API_TIMEOUT_MS);
  const ctl = new AbortController(); init.signal = ctl.signal;
  const timer = setTimeout(() => ctl.abort(), ms);
  let res;
  try { res = await fetch(path, init); } catch (e) { throw explainFetchError(e, ms); } finally { clearTimeout(timer); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(data.detail || `Request failed (HTTP ${res.status}).`, data.hint || '');
  return data;
}
function toast(msg, err = false, hint = '') {
  const t = $('#toast'); t.textContent = hint ? `${msg} ${hint}` : msg; t.className = 'show' + (err ? ' err' : '');
  clearTimeout(toast.h); toast.h = setTimeout(() => (t.className = ''), err ? 9000 : 4500);
}
async function act(fn) { try { return await fn(); } catch (e) { toast(e.message || String(e), true, e.hint || ''); } }
function opts(sel, values, current) { sel.innerHTML = values.map((v) => `<option ${v === current ? 'selected' : ''}>${esc(v)}</option>`).join(''); }
function checks(el, values, checked = []) {
  el.innerHTML = values.map((v) => `<label class="inline"><input type="checkbox" value="${esc(v)}" ${checked.includes(v) ? 'checked' : ''}> ${esc(v)}</label>`).join('');
}
const checked = (el) => $$('input:checked', el).map((i) => i.value);
function zoom(src) { const z = document.createElement('div'); z.className = 'zoom'; z.innerHTML = `<img src="${src}">`; z.onclick = () => z.remove(); document.body.append(z); }

// ---------------------------------------------------------------- tabs
const loaders = {};
$$('#tabs button').forEach((b) => (b.onclick = () => showTab(b.dataset.tab)));
function showTab(name) {
  $$('#tabs button').forEach((b) => b.classList.toggle('active', b.dataset.tab === name));
  $$('.tab').forEach((t) => t.classList.toggle('active', t.id === `tab-${name}`));
  location.hash = name;
  loaders[name] && act(loaders[name]);
}

// ---------------------------------------------------------------- jobs + log panel
let logJob = null, logOffset = 0, knownJobs = [];
const onJobDone = {};
function watch(job, title, then) {
  logJob = job.id; logOffset = 0; $('#log').textContent = '';
  $('#log-panel').classList.remove('collapsed'); $('#log-toggle').textContent = '▼';
  if (then) onJobDone[job.id] = then;
  toast(`Started: ${title || job.title}`);
  refreshJobs();
}
async function refreshJobs() {
  knownJobs = await api('/api/jobs').catch(() => knownJobs);
  const running = knownJobs.filter((j) => j.status === 'running' || j.status === 'queued').length;
  const pill = $('#jobs-pill'); pill.textContent = `${running} running`; pill.classList.toggle('busy', running > 0);
  const sel = $('#log-job');
  sel.innerHTML = knownJobs.map((j) => `<option value="${j.id}" ${j.id === logJob ? 'selected' : ''}>${esc(j.status)} · ${esc(j.title)}</option>`).join('') || '<option>no jobs yet</option>';
}
async function pollLog() {
  if (logJob) {
    const r = await api(`/api/jobs/${logJob}/log?offset=${logOffset}`).catch(() => null);
    if (r) {
      if (r.text) {
        const pre = $('#log'); const atEnd = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
        pre.textContent += r.text; logOffset = r.offset;
        if (pre.textContent.length > 400000) pre.textContent = pre.textContent.slice(-300000);
        if (atEnd) pre.scrollTop = pre.scrollHeight;
      }
      $('#log-title').textContent = `${r.job.title} — ${r.status}`;
      if (['done', 'failed', 'cancelled'].includes(r.status) && onJobDone[logJob]) {
        const cb = onJobDone[logJob]; delete onJobDone[logJob]; refreshJobs(); cb(r.status);
      }
    }
  }
  setTimeout(pollLog, 1000);
}
$('#log-job').onchange = (e) => { logJob = e.target.value; logOffset = 0; $('#log').textContent = ''; };
$('#log-toggle').onclick = () => { const p = $('#log-panel'); p.classList.toggle('collapsed'); $('#log-toggle').textContent = p.classList.contains('collapsed') ? '▲' : '▼'; };
$('#log-cancel').onclick = () => logJob && act(async () => { await api(`/api/jobs/${logJob}/cancel`, {method: 'POST'}); toast('Cancelled'); });
$('#jobs-pill').onclick = () => $('#log-toggle').click();
setInterval(refreshJobs, 4000);

// ---------------------------------------------------------------- CREATE
let current = null; // {slug, script}
let createMode = 'idea';
function setMode(mode) {
  createMode = mode;
  $$('#c-mode button').forEach((b) => b.classList.toggle('active', b.dataset.mode === mode));
  $('#c-idea-box').hidden = mode !== 'idea'; $('#c-script-box').hidden = mode !== 'script';
  $('#c-duration').closest('div').hidden = mode === 'script';
  $('#c-write').textContent = mode === 'script' ? 'Split into scenes' : 'Write script';
}
$$('#c-mode button').forEach((b) => (b.onclick = () => setMode(b.dataset.mode)));
function showTemplate() {
  const t = OPTS?.templates?.[$('#c-style').value];
  $('#c-template').textContent = t ? `Beats: ${t.beats.map((b) => b.label || b.id).join(' → ')}` : '';
  const forced = t && t.family === 'long_form' ? t.default_aspect : null;
  if (forced) $('#c-aspect').value = forced;
}
loaders.create = async () => {
  OPTS = OPTS || (await api('/api/options'));
  const d = OPTS.defaults;
  if (!$('#c-style').options.length) {
    opts($('#c-style'), OPTS.styles, d.style); opts($('#c-aspect'), OPTS.aspects, d.aspect_ratio); opts($('#c-mood'), OPTS.moods, d.music_mood);
    checks($('#c-platforms'), OPTS.platforms, ['youtube']); $('#c-duration').value = d.target_duration_sec;
    $('#c-ground').checked = OPTS.grounding !== false; $('#c-style').onchange = showTemplate; showTemplate();
  }
  const list = await api('/api/projects');
  $('#projects').innerHTML = list.map((p) => `
    <div class="item"><div><div class="t">${esc(p.title || p.slug)}</div>
      <div class="s">${esc(p.slug)} · ${esc(p.style)} · ${esc(p.aspect_ratio)} · ${p.scenes} scenes</div></div>
      <div>${p.needs_approval ? '<span class="badge warn">needs approval</span>' : ''}${p.rendered ? '<span class="badge ok">rendered</span>' : ''}
      <button class="small" data-open="${esc(p.slug)}">Open</button></div></div>`).join('') || '<p class="muted">No projects yet.</p>';
  $$('[data-open]').forEach((b) => (b.onclick = () => act(() => openProject(b.dataset.open))));
};
$('#c-write').onclick = () => act(async () => {
  const body = {mode: createMode, title: $('#c-title').value.trim(), style: $('#c-style').value, aspect: $('#c-aspect').value, mood: $('#c-mood').value,
    duration: +$('#c-duration').value, platforms: checked($('#c-platforms')), overwrite: $('#c-overwrite').checked, grounding: $('#c-ground').checked};
  if (createMode === 'script') {
    body.script = $('#c-script').value.trim(); if (!body.script) throw new Error('Paste your script first');
  } else {
    body.prompt = $('#c-prompt').value.trim(); if (!body.prompt) throw new Error('Write a prompt first');
  }
  const job = await api('/api/projects/write', {method: 'POST', body});
  watch(job, createMode === 'script' ? 'Splitting your script' : 'Writing script', async (status) => {
    if (status !== 'done') return toast('Script writing failed: see log', true);
    const text = $('#log').textContent; const m = text.match(/SCRIPT .*[\\/]projects[\\/]([^\\/]+)[\\/]script\.json/);
    await loaders.create(); if (m) openProject(m[1]);
  });
});
const grow = (ta) => { ta.style.height = 'auto'; ta.style.height = `${ta.scrollHeight + 2}px`; };
function renderEditor() {
  const script = current.script;
  const claims = script.claims || [];
  const open = claims.filter((c) => !c.verified).map((c) => c.text);
  const facts = claims.length ? open : (script.facts_to_verify || []);
  $('#facts').hidden = !facts.length;
  $('#facts').innerHTML = facts.length ? `<b>Unverified facts (${script.grounded ? 'checked with Google Search' : 'not checked: no web grounding'}). Videos with unverified facts are held as “needs review” by the Safe-Publish Gate:</b><ul>${facts.map((f) => `<li>${esc(f)}</li>`).join('')}</ul>` : '';
  const src = script.sources || [];
  $('#sources').hidden = !src.length;
  $('#sources').innerHTML = src.length ? `Sources: ${src.map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a>`).join(' · ')}` : '';
  const types = OPTS.visual_types || [];
  $('#scenes').innerHTML = (script.scenes || []).map((s, i) => `
    <div class="scene" data-scene="${i}">
      <div class="row between"><div class="k">${i + 1}. ${esc(s.beat || '')}</div>
        <div class="actions"><select data-i="${i}" data-f="type" style="width:auto">${types.map((t) => `<option ${t === (s.visual?.type || 'headline') ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select>
          <button class="small" data-up="${i}" ${i === 0 ? 'disabled' : ''} title="Move up">↑</button>
          <button class="small" data-down="${i}" ${i === script.scenes.length - 1 ? 'disabled' : ''} title="Move down">↓</button>
          <button class="small" data-delete="${i}" title="Delete scene">Delete</button></div></div>
      <textarea class="auto" data-i="${i}" data-f="narration" rows="2">${esc(s.narration)}</textarea>
      <input data-i="${i}" data-f="heading" value="${esc(s.visual?.heading || '')}" placeholder="on-screen heading"></div>`).join('');
  $('#e-json').value = JSON.stringify(script, null, 2);
  $$('#scenes textarea.auto').forEach(grow);
  $$('#scenes [data-i]').forEach((el) => {
    const edit = () => {
      const sc = current.script.scenes[+el.dataset.i];
      if (el.dataset.f === 'narration') { sc.narration = el.value; grow(el); }
      else if (el.dataset.f === 'type') { sc.visual = {...(sc.visual || {}), type: el.value}; }
      else { sc.visual = sc.visual || {type: 'headline'}; sc.visual.heading = el.value; }
      $('#e-json').value = JSON.stringify(current.script, null, 2);
    };
    el.oninput = edit; if (el.tagName === 'SELECT') el.onchange = edit;
  });
  const move = (i, j) => { const a = current.script.scenes; [a[i], a[j]] = [a[j], a[i]]; renderEditor(); };
  $$('[data-up]').forEach((b) => (b.onclick = () => move(+b.dataset.up, +b.dataset.up - 1)));
  $$('[data-down]').forEach((b) => (b.onclick = () => move(+b.dataset.down, +b.dataset.down + 1)));
  $$('[data-delete]').forEach((b) => (b.onclick = () => {
    if (current.script.scenes.length <= 1) return toast('A video needs at least one scene.', true);
    current.script.scenes.splice(+b.dataset.delete, 1); renderEditor();
  }));
}
$('#e-add').onclick = () => { if (!current) return; current.script.scenes.push({beat: 'other', narration: '', visual: {type: 'headline', heading: ''}}); renderEditor(); };
async function openProject(slug) {
  OPTS = OPTS || (await api('/api/options'));
  const script = await api(`/api/projects/${encodeURIComponent(slug)}`);
  current = {slug, script};
  $('#editor-card').hidden = false; $('#editor-title').textContent = `Script: ${script.title || slug}`;
  renderEditor();
  $('#editor-card').scrollIntoView({behavior: 'smooth'});
}
$('#e-json').oninput = () => { try { current.script = JSON.parse($('#e-json').value); } catch { /* keep typing */ } };
async function saveProject() {
  const empty = current.script.scenes.findIndex((s) => !String(s.narration || '').trim());
  if (empty >= 0) throw new Error(`Scene ${empty + 1} has no narration. Write it or delete the scene.`);
  await api(`/api/projects/${encodeURIComponent(current.slug)}`, {method: 'PUT', body: current.script});
}
$('#e-save').onclick = () => act(async () => { await saveProject(); toast('Saved'); loaders.create(); });
$('#e-render').onclick = () => act(async () => {
  await saveProject();
  const job = await api(`/api/projects/${encodeURIComponent(current.slug)}/render`, {method: 'POST', body: {safe_zones: $('#e-safe').checked, strict_qa: $('#e-strict').checked}});
  watch(job, `Rendering ${current.slug}`, (s) => { toast(s === 'done' ? 'Render finished: see Library' : 'Render failed: see log', s !== 'done'); if (s === 'done') showTab('library'); });
});
// ---------------------------------------------------------------- IDEAS
loaders.ideas = async () => {
  const runs = await api('/api/ideas');
  $('#runs').innerHTML = runs.map((r) => {
    const bp = r.blueprint || {}; const h = bp.hook_first_3s || {}; const p = bp.pacing || {};
    const ideas = (r.ideas || []).map((i) => `
      <div class="idea" data-run="${esc(r.run)}" data-n="${i.n}">
        <label class="inline"><input type="checkbox" value="${i.n}" ${r.approved.includes(i.n) ? 'checked disabled' : ''}> <b>${i.n}. ${esc(i.title)}</b></label>
        <div class="hook">“${esc(i.hook)}”</div><div>${esc(i.angle)}</div>
        <div class="s muted">Case study: ${esc(i.case_study)}</div>
        <div class="s"><span class="badge">${esc(i.style)}</span> <span class="badge">${esc(i.music_mood)}</span></div>
        <div class="s muted">${esc(i.why_it_works)}</div></div>`).join('');
    return `<div class="card">
      <div class="row between"><h2>${esc(bp.style_name || r.run)}</h2><span class="badge ${r.status === 'approved' ? 'ok' : 'warn'}">${esc(r.status)}</span></div>
      <div class="s muted">${r.sources.map(esc).join(' · ')}</div>
      <div class="sheets">${r.sheets.map((s) => `<img src="${file(s)}" data-zoom>`).join('')}</div>
      <div class="s"><b>Says:</b> ${esc(h.verbal_pattern)}<br><b>Shows:</b> ${esc(h.visual_pattern)}<br>
        <b>Pacing:</b> ${esc(p.avg_shot_sec)} s/shot · ${esc(p.words_per_minute)} wpm · captions ${esc(p.caption_style)} · ${esc(p.transition_style)}
        · ${esc(bp.aspect_ratio)} · ~${esc(bp.target_duration_sec)} s</div>
      ${ideas ? `<div class="ideas">${ideas}</div>` : '<p class="muted">No ideas yet.</p>'}
      <div class="actions">
        <button data-propose="${esc(r.run)}">${ideas ? 'Regenerate ideas' : 'Generate 5 ideas'}</button>
        ${ideas ? `<button class="primary" data-approve="${esc(r.run)}">Approve selected</button>
        <label class="inline"><input type="checkbox" id="ra-${esc(r.run)}" checked> render after approval</label>` : ''}
      </div>
      ${r.projects.length ? `<div class="s muted">Projects: ${r.projects.map(esc).join(', ')}</div>` : ''}
    </div>`;
  }).join('') || '<div class="card muted">No analyses yet. Paste reference links above.</div>';
  $$('[data-zoom]').forEach((i) => (i.onclick = () => zoom(i.src)));
  $$('[data-propose]').forEach((b) => (b.onclick = () => act(async () => {
    const job = await api(`/api/ideas/${encodeURIComponent(b.dataset.propose)}/propose`, {method: 'POST', body: {topic: $('#i-topic').value}});
    watch(job, 'Generating ideas', () => loaders.ideas());
  })));
  $$('[data-approve]').forEach((b) => (b.onclick = () => act(async () => {
    const run = b.dataset.approve; const card = b.closest('.card');
    const ideas = $$('.idea input:checked:not(:disabled)', card).map((i) => +i.value);
    if (!ideas.length) throw new Error('Tick at least one idea');
    const job = await api(`/api/ideas/${encodeURIComponent(run)}/approve`, {method: 'POST', body: {ideas, render_after: $(`#ra-${CSS.escape(run)}`).checked}});
    watch(job, `Approving ideas ${ideas.join(', ')}`, () => { loaders.ideas(); loaders.create(); });
  })));
};
$('#i-analyze').onclick = () => act(async () => {
  const urls = $('#i-urls').value.split(/\s+/).filter(Boolean); if (!urls.length) throw new Error('Paste at least one link');
  const body = {urls, style: $('#i-style').value.trim() || 'my_style', mode: $('#i-mode').value, topic: $('#i-topic').value, confirm_large: $('#i-large').checked};
  const job = await api('/api/analyze', {method: 'POST', body});
  watch(job, 'Analyzing references', () => loaders.ideas());
});

// ---------------------------------------------------------------- LIBRARY
loaders.library = async () => {
  const items = await api('/api/library');
  $('#library').innerHTML = items.map((v) => {
    const m = v.meta; const qa = v.qa;
    const frames = v.qa_frames.map((f) => {
      const r = qa?.frames?.find((x) => x.frame === f.name); const cls = r ? (r.ok ? 'ok' : 'bad') : '';
      return `<figure><img class="${cls}" src="${file(f.src)}" data-zoom-src="${file(r && !r.ok && f.overlay ? f.overlay : f.src)}" title="${esc((r?.issues || []).join('; ') || 'ok')}">
        <figcaption>${esc(f.name)}${r && !r.ok ? ' ⚠' : ''}</figcaption></figure>`;
    }).join('');
    const issues = (qa?.frames || []).flatMap((f) => f.issues.map((i) => `${f.frame}: ${i}`));
    const facts = m.facts_to_verify || [];
    return `<div class="card video-card" data-slug="${esc(v.slug)}">
      <div>${v.video ? `<video controls preload="metadata" src="${file(v.video)}" poster="${v.thumbnail ? file(v.thumbnail) : ''}"></video>` : '<p class="muted">no video file</p>'}
        ${v.thumbnail ? `<img class="thumb" src="${file(v.thumbnail)}" data-zoom-src="${file(v.thumbnail)}" title="thumbnail">` : ''}
        <div class="actions">${v.video ? `<a href="${file(v.video)}" download><button class="small">Download MP4</button></a>` : ''}
          ${v.thumbnail ? `<a href="${file(v.thumbnail)}" download><button class="small">Thumbnail</button></a>` : ''}</div></div>
      <div>
        <div class="row between"><h2>${esc(m.title)}</h2>
          <span class="badge ${qa ? (qa.ok ? 'ok' : 'bad') : ''}">QA ${qa ? (qa.ok ? 'pass' : 'issues') : 'n/a'}</span></div>
        <div class="qa">${frames}</div>
        ${issues.length ? `<div class="warn">${issues.map(esc).join('<br>')}</div>` : ''}
        ${facts.length ? `<div class="warn"><b>Verify before posting:</b> ${facts.map(esc).join(' · ')}</div>` : ''}
        <label>Title ${m.title_variants?.length > 1 ? '(variants: ' + m.title_variants.map((t, i) => `<a href="#" data-title="${i}">${i + 1}</a>`).join(' ') + ')' : ''}</label>
        <input data-m="title" value="${esc(m.title)}">
        <label>Description</label><textarea data-m="description" rows="4">${esc(m.description)}</textarea>
        <div class="row"><div><label>Hashtags</label><input data-m="hashtags" value="${esc((m.hashtags || []).join(' '))}"></div>
          <div><label>Tags (comma)</label><input data-m="tags" value="${esc((m.tags || []).join(', '))}"></div></div>
        ${m.hook_variants?.length ? `<div class="s muted">Alternative hooks: ${m.hook_variants.map(esc).join(' · ')}</div>` : ''}
        <div class="s muted">Metadata: ${esc(m.metadata_source || 'script')} · ${esc(m.music_attribution)}</div>
        <div class="actions"><button data-save>Save metadata</button><button data-regen>Regenerate with AI</button></div>
        <h3>Publish</h3>
        <div class="actions">
          <select data-p="platform" style="width:auto">${['youtube', 'instagram', 'tiktok'].map((p) => `<option>${p}</option>`).join('')}</select>
          <select data-p="visibility" style="width:auto"><option value="">YouTube: default (${esc(m.visibility || 'unlisted')})</option><option>unlisted</option><option>private</option><option>public</option></select>
          <label class="inline"><input type="checkbox" data-p="headed"> show browser</label>
          <button class="primary" data-publish>Upload</button>
        </div>
      </div></div>`;
  }).join('') || '<div class="card muted">Nothing rendered yet. Create a video first.</div>';
  $$('#library [data-zoom-src]').forEach((i) => (i.onclick = () => zoom(i.dataset.zoomSrc)));
  $$('#library .video-card').forEach((card) => {
    const slug = card.dataset.slug; const item = items.find((x) => x.slug === slug);
    $$('[data-title]', card).forEach((a) => (a.onclick = (e) => { e.preventDefault(); $('[data-m=title]', card).value = item.meta.title_variants[+a.dataset.title]; }));
    $('[data-save]', card).onclick = () => act(async () => {
      const body = {title: $('[data-m=title]', card).value, description: $('[data-m=description]', card).value,
        hashtags: $('[data-m=hashtags]', card).value.split(/[\s,]+/).filter(Boolean), tags: $('[data-m=tags]', card).value.split(',').map((s) => s.trim()).filter(Boolean)};
      await api(`/api/library/${encodeURIComponent(slug)}/meta`, {method: 'PUT', body}); toast('Metadata saved (kept on re-render)');
    });
    $('[data-regen]', card).onclick = () => act(async () => watch(await api(`/api/library/${encodeURIComponent(slug)}/metadata`, {method: 'POST'}), 'AI metadata', () => loaders.library()));
    $('[data-publish]', card).onclick = () => act(async () => {
      const platform = $('[data-p=platform]', card).value;
      if (!confirm(`Upload "${item.meta.title}" to ${platform}?`)) return;
      const body = {platform, visibility: $('[data-p=visibility]', card).value, headed: $('[data-p=headed]', card).checked};
      watch(await api(`/api/library/${encodeURIComponent(slug)}/publish`, {method: 'POST', body}), `Uploading to ${platform}`);
    });
  });
};

// ---------------------------------------------------------------- SCHEDULE
const toLocal = (v) => (v ? String(v).slice(0, 16) : '');
const fromLocal = (v) => (v ? `${v}:00` : null); // naive time = schedule timezone
loaders.schedule = async () => {
  OPTS = OPTS || (await api('/api/options'));
  const [s, projects] = await Promise.all([api('/api/schedule'), api('/api/projects')]);
  $('#s-daemon').checked = s.daemon;
  $('#caps').innerHTML = Object.entries(s.caps).map(([p, c]) => `<div class="cap">${esc(p)}: <b>${c.used}/${c.cap}</b> today</div>`).join('');
  opts($('#s-project'), projects.map((p) => p.slug));
  if (!$('#s-platforms').children.length) checks($('#s-platforms'), OPTS.platforms, ['youtube']);
  $('#s-tz').value = s.defaults.timezone; $('#s-capig').value = s.defaults.instagram_daily_cap; $('#s-capyt').value = s.defaults.youtube_daily_cap; $('#s-captt').value = s.defaults.tiktok_daily_cap;
  $('#s-jobs').innerHTML = s.jobs.map((j) => {
    const st = j.state?.gen_status || (j.enabled === false ? 'paused' : 'pending');
    const ups = (j.uploads || []).map((u) => `<span class="badge ${u.status === 'done' ? 'ok' : u.status === 'failed' ? 'bad' : ''}">${esc(u.platform)}: ${esc(u.status)}</span>`).join(' ');
    return `<div class="item"><div><div class="t">${esc(j.id)} <span class="badge">${esc(j.type)}</span></div>
      <div class="s">gen ${esc(toLocal(j.generate_at) || 'asap')} → up ${esc(toLocal(j.upload_at) || 'asap')} · ${esc((j.platforms || []).join(', '))}</div>
      <div class="s"><span class="badge ${st === 'done' ? 'ok' : st === 'failed' ? 'bad' : ''}">${esc(st)}</span> ${ups}</div>
      ${j.state?.last_error ? `<div class="s" style="color:var(--bad)">${esc(j.state.last_error.split('\n')[0])}</div>` : ''}</div>
      <div class="actions"><label class="inline"><input type="checkbox" data-en="${esc(j.id)}" ${j.enabled === false ? '' : 'checked'}> on</label>
        <button class="small" data-run="${esc(j.id)}">Run now</button><button class="small" data-retry="${esc(j.id)}">Retry</button>
        <button class="small" data-del="${esc(j.id)}">✕</button></div></div>`;
  }).join('') || '<p class="muted">No scheduled jobs.</p>';
  $('#s-events').textContent = s.events.map((e) => `${e.at.slice(0, 19)}  ${e.job_id || '-'}  ${e.kind}  ${e.detail || ''}`).join('\n');
  $$('[data-en]').forEach((c) => (c.onchange = () => act(async () => { await api(`/api/schedule/jobs/${encodeURIComponent(c.dataset.en)}`, {method: 'PUT', body: {enabled: c.checked}}); loaders.schedule(); })));
  $$('[data-run]').forEach((b) => (b.onclick = () => act(async () => watch(await api(`/api/schedule/run/${encodeURIComponent(b.dataset.run)}`, {method: 'POST'}), 'Run now', () => loaders.schedule()))));
  $$('[data-retry]').forEach((b) => (b.onclick = () => act(async () => watch(await api(`/api/schedule/retry/${encodeURIComponent(b.dataset.retry)}`, {method: 'POST'}), 'Retry', () => loaders.schedule()))));
  $$('[data-del]').forEach((b) => (b.onclick = () => act(async () => { if (!confirm(`Delete job ${b.dataset.del}?`)) return; await api(`/api/schedule/jobs/${encodeURIComponent(b.dataset.del)}`, {method: 'DELETE'}); loaders.schedule(); })));
};
$('#s-add').onclick = () => act(async () => {
  const project = $('#s-project').value; if (!project) throw new Error('Create a project first');
  const body = {id: `${project}-${Date.now().toString(36)}`, project, type: $('#s-type').value, generate_at: fromLocal($('#s-gen').value), upload_at: fromLocal($('#s-up').value),
    platforms: checked($('#s-platforms')), visibility: $('#s-vis').value};
  await api('/api/schedule/jobs', {method: 'POST', body}); toast('Scheduled'); loaders.schedule();
});
$('#s-save-defaults').onclick = () => act(async () => {
  await api('/api/schedule/defaults', {method: 'PUT', body: {timezone: $('#s-tz').value, instagram_daily_cap: +$('#s-capig').value, youtube_daily_cap: +$('#s-capyt').value, tiktok_daily_cap: +$('#s-captt').value}});
  toast('Defaults saved'); loaders.schedule();
});
$('#s-daemon').onchange = (e) => act(async () => { await api('/api/schedule/daemon', {method: 'POST', body: {run: e.target.checked}}); toast(e.target.checked ? 'Scheduler daemon started' : 'Daemon stopped'); });

// ---------------------------------------------------------------- SETTINGS
let SETTINGS = null;
loaders.settings = async () => {
  OPTS = OPTS || (await api('/api/options'));
  SETTINGS = await api('/api/settings');
  const p = SETTINGS.prefs, env = SETTINGS.env;
  $('#l-provider').value = p.llm.provider; $('#l-gemini-model').value = p.llm.gemini_model; $('#l-ollama-model').value = p.llm.ollama_model; $('#l-openai-model').value = p.llm.openai_model;
  for (const k of Object.keys(env)) { const el = $(`#k-${k}`); if (el) { el.value = ''; el.placeholder = env[k].set ? (env[k].value || 'set') : 'not set'; } }
  const d = p.defaults;
  ['niche', 'language', 'voice', 'rate', 'target_duration_sec'].forEach((k) => ($(`#d-${k}`).value = d[k] ?? ''));
  $('#d-voice_engine').value = d.voice_engine;
  opts($('#d-style'), OPTS.styles, d.style); opts($('#d-aspect_ratio'), OPTS.aspects, d.aspect_ratio); opts($('#d-music_mood'), OPTS.moods, d.music_mood);
  $('#d-tracking').checked = !!p.clipper.speaker_tracking;
  const cookies = SETTINGS.cookie_accounts;
  $('#pub').innerHTML = ['youtube', 'instagram', 'tiktok'].map((pl) => {
    const c = p.publish[pl]; const has = cookies.includes(`${pl}_${c.account}`);
    return `<div class="pub-row"><b>${pl}</b>
      <select data-pm="${pl}"><option ${c.method === 'cookie' ? 'selected' : ''}>cookie</option><option ${c.method === 'api' ? 'selected' : ''}>api</option></select>
      <input data-pa="${pl}" value="${esc(c.account)}" title="cookie account name">
      <span class="badge ${has ? 'ok' : 'warn'}">${has ? 'cookie saved' : 'not logged in'}</span>
      <span><button class="small" data-login="${pl}">Login</button> <button class="small" data-check="${pl}">Check</button></span></div>`;
  }).join('') + `<div class="actions"><button id="pub-save">Save publishing settings</button></div>`;
  $('#api-status').textContent = JSON.stringify(SETTINGS.api_status);
  $$('[data-login]').forEach((b) => (b.onclick = () => act(async () => watch(await api('/api/settings/login', {method: 'POST', body: {platform: b.dataset.login, account: $(`[data-pa=${b.dataset.login}]`).value}}), 'Login: a browser window opens; sign in, then close it', () => loaders.settings()))));
  $$('[data-check]').forEach((b) => (b.onclick = () => act(async () => watch(await api('/api/settings/check', {method: 'POST', body: {platform: b.dataset.check, account: $(`[data-pa=${b.dataset.check}]`).value}}), 'Cookie check'))));
  $('#pub-save').onclick = () => act(async () => {
    const publish = {};
    ['youtube', 'instagram', 'tiktok'].forEach((pl) => (publish[pl] = {method: $(`[data-pm=${pl}]`).value, account: $(`[data-pa=${pl}]`).value.trim() || 'main'}));
    await api('/api/settings/prefs', {method: 'PUT', body: {publish}}); toast('Publishing settings saved'); loaders.settings();
  });
};
async function saveSecrets(keys) {
  const body = {}; keys.forEach((k) => { const v = $(`#k-${k}`).value.trim(); if (v) body[k] = v; });
  if (Object.keys(body).length) await api('/api/settings/secrets', {method: 'PUT', body});
}
$('#l-save').onclick = () => act(async () => {
  await api('/api/settings/prefs', {method: 'PUT', body: {llm: {provider: $('#l-provider').value, gemini_model: $('#l-gemini-model').value.trim(), ollama_model: $('#l-ollama-model').value.trim(), openai_model: $('#l-openai-model').value.trim()}}});
  await saveSecrets(['GEMINI_API_KEY', 'OLLAMA_HOST', 'OPENAI_BASE_URL', 'OPENAI_API_KEY']);
  toast('Saved (keys stored in local .env)'); loaders.settings();
});
$('#l-test').onclick = () => act(async () => watch(await api('/api/settings/test-llm', {method: 'POST'}), 'Testing language model'));
$('#l-models').onclick = () => act(async () => watch(await api('/api/settings/gemini-models', {method: 'POST'}), 'Gemini models'));
$('#d-save').onclick = () => act(async () => {
  const defaults = {}; ['niche', 'language', 'voice', 'rate'].forEach((k) => (defaults[k] = $(`#d-${k}`).value.trim()));
  Object.assign(defaults, {voice_engine: $('#d-voice_engine').value, style: $('#d-style').value, aspect_ratio: $('#d-aspect_ratio').value, music_mood: $('#d-music_mood').value, target_duration_sec: +$('#d-target_duration_sec').value || 50});
  await api('/api/settings/prefs', {method: 'PUT', body: {defaults, clipper: {speaker_tracking: $('#d-tracking').checked}}});
  OPTS = null; toast('Defaults saved');
});
$('#api-save').onclick = () => act(async () => { await saveSecrets(['INSTAGRAM_USER_ID', 'INSTAGRAM_ACCESS_TOKEN', 'TIKTOK_ACCESS_TOKEN']); toast('API credentials saved'); loaders.settings(); });
$('#yt-upload').onclick = () => act(async () => {
  const f = $('#yt-file').files[0]; if (!f) throw new Error('Choose the client JSON first');
  const fd = new FormData(); fd.append('file', f); await api('/api/settings/youtube-client', {method: 'POST', body: fd}); toast('Client file saved'); loaders.settings();
});
$('#yt-connect').onclick = () => act(async () => watch(await api('/api/settings/youtube-connect', {method: 'POST'}), 'YouTube consent: a browser opens', () => loaders.settings()));
$('#h-doctor').onclick = () => act(async () => watch(await api('/api/health', {method: 'POST'}), 'System health'));
$('#h-smoke').onclick = () => act(async () => watch(await api('/api/smoke', {method: 'POST'}), 'Smoke test (about 2 minutes)'));

// ---------------------------------------------------------------- boot
showTab((location.hash || '#create').slice(1));
refreshJobs(); pollLog();
