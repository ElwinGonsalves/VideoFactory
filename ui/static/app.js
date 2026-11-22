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
$$('#i-mode-tabs button').forEach((b) => (b.onclick = () => {
  $$('#i-mode-tabs button').forEach((x) => x.classList.toggle('active', x === b));
  $('#i-brainstorm').hidden = b.dataset.imode !== 'brainstorm'; $('#i-reference').hidden = b.dataset.imode !== 'reference';
}));
const ideaCard = (r, i) => `
  <div class="idea ${i.dismissed ? 'dismissed' : ''}" data-run="${esc(r.run)}" data-n="${i.n}">
    <label>Title</label><input data-f="title" value="${esc(i.title)}">
    <label>Opening hook</label>
    <div class="s"><b>Says:</b> <input data-f="hook" value="${esc(i.hook)}"></div>
    <div class="s"><b>Shows:</b> <input data-f="hook_visual" value="${esc(i.hook_visual || '')}" placeholder="what the first 3 seconds show"></div>
    <label>Core concept &amp; case study</label>
    <textarea data-f="angle" rows="2">${esc(i.angle)}</textarea>
    <textarea data-f="case_study" rows="2">${esc(i.case_study)}</textarea>
    <div class="s"><span class="badge">${esc(i.style)}</span> <span class="badge">${esc(i.aspect_ratio || '9:16')}</span>
      <span class="badge">${esc(i.duration_sec || 50)} s</span> <span class="badge">${esc(i.music_mood)}</span></div>
    <div class="s muted">Why it works: ${esc(i.why_it_works)}</div>
    <div class="actions">
      <button class="primary small" data-act="approve">Approve &amp; Generate</button>
      <button class="small" data-act="edit">Edit Script</button>
      <button class="small" data-act="schedule">Add to Schedule</button>
      <button class="small" data-act="dismiss">${i.dismissed ? 'Restore' : 'Dismiss'}</button>
    </div></div>`;
loaders.ideas = async () => {
  const [runs, bps, an] = await Promise.all([api('/api/ideas'), api('/api/blueprints'), api('/api/analytics')]);
  opts($('#i-bp'), ['(none)', ...bps.map((b) => b.name)], '(none)');
  $('#i-blueprints').innerHTML = bps.length ? bps.map((b) => `<span class="badge">${esc(b.name)} · ${esc(b.aspect_ratio)} · ${esc(b.target_duration_sec)} s</span>`).join(' ') : 'none yet: analyze a reference video to save one.';
  $('#i-top').innerHTML = an.top.length ? `<b>Top by views:</b> ${an.top.map((t) => `${esc(t.title)} (${t.views})`).join(' · ')}` : 'No analytics yet. Paste published URLs in the Library, then Sync Analytics.';
  $('#runs').innerHTML = runs.map((r) => {
    const bp = r.blueprint || {}; const h = bp.hook_first_3s || {}; const p = bp.pacing || {};
    const cards = (r.ideas || []).map((i) => ideaCard(r, i)).join('');
    const title = r.mode === 'brainstorm' ? `Brainstorm: ${r.topic}` : (bp.style_name || r.run);
    return `<div class="card" data-runcard="${esc(r.run)}">
      <div class="row between"><h2>${esc(title)}</h2><span class="badge ${r.status === 'approved' ? 'ok' : 'warn'}">${esc(r.status)}</span></div>
      ${r.mode === 'brainstorm' ? '' : `<div class="s muted">${r.sources.map(esc).join(' · ')}</div>
      <div class="sheets">${r.sheets.map((s) => `<img src="${file(s)}" data-zoom>`).join('')}</div>
      <div class="s"><b>Says:</b> ${esc(h.verbal_pattern)}<br><b>Shows:</b> ${esc(h.visual_pattern)}<br>
        <b>Pacing:</b> ${esc(p.avg_shot_sec)} s/shot · ${esc(p.words_per_minute)} wpm · captions ${esc(p.caption_style)} · ${esc(p.transition_style)}</div>`}
      <div class="ideas">${cards || '<p class="muted">No ideas yet.</p>'}</div>
      <div class="actions"><button data-propose="${esc(r.run)}">${cards ? 'Regenerate ideas' : 'Generate 5 ideas'}</button></div>
      ${r.projects.length ? `<div class="s muted">Projects: ${r.projects.map(esc).join(', ')}</div>` : ''}
    </div>`;
  }).join('') || '<div class="card muted">No idea runs yet. Brainstorm a topic or analyze reference links above.</div>';
  $$('[data-zoom]').forEach((i) => (i.onclick = () => zoom(i.src)));
  $$('[data-propose]').forEach((b) => (b.onclick = () => act(async () => {
    const job = await api(`/api/ideas/${encodeURIComponent(b.dataset.propose)}/propose`, {method: 'POST', body: {topic: $('#i-topic').value || $('#i-btopic').value}});
    watch(job, 'Generating ideas', () => loaders.ideas());
  })));
  $$('.idea').forEach((card) => {
    const run = card.dataset.run, n = +card.dataset.n;
    const saveEdits = async (extra = {}) => {
      const body = {...extra}; $$('[data-f]', card).forEach((el) => (body[el.dataset.f] = el.value));
      await api(`/api/ideas/${encodeURIComponent(run)}/${n}`, {method: 'PUT', body});
    };
    $$('[data-act]', card).forEach((btn) => (btn.onclick = () => act(async () => {
      const what = btn.dataset.act;
      if (what === 'dismiss') { await saveEdits({dismissed: !card.classList.contains('dismissed')}); return loaders.ideas(); }
      await saveEdits();
      const job = await api(`/api/ideas/${encodeURIComponent(run)}/approve`, {method: 'POST', body: {ideas: [n], render_after: what === 'approve'}});
      watch(job, what === 'approve' ? 'Approving and generating' : 'Writing script', async () => {
        await loaders.ideas(); await loaders.create();
        const projects = (await api(`/api/ideas`)).find((x) => x.run === run)?.projects || [];
        const slug = (projects[projects.length - 1] || '').split('/').pop();
        if (what === 'edit' && slug) { showTab('create'); openProject(slug); }
        if (what === 'schedule' && slug) { showTab('schedule'); }
      });
    })));
  });
};
$('#i-brainstorm-go').onclick = () => act(async () => {
  const topic = $('#i-btopic').value.trim(); if (!topic) throw new Error('Type a topic or niche first');
  const bp = $('#i-bp').value; const job = await api('/api/ideas/brainstorm', {method: 'POST', body: {topic, blueprint: bp === '(none)' ? '' : bp}});
  watch(job, 'Brainstorming ideas', () => loaders.ideas());
});
$('#i-analyze').onclick = () => act(async () => {
  const urls = $('#i-urls').value.split(/\s+/).filter(Boolean); if (!urls.length) throw new Error('Paste at least one link');
  const body = {urls, style: $('#i-style').value.trim() || 'my_style', depth: $('#i-depth').value, topic: $('#i-topic').value, confirm_large: $('#i-large').checked};
  const job = await api('/api/analyze', {method: 'POST', body});
  watch(job, 'Analyzing references', () => loaders.ideas());
});
$('#i-sync').onclick = () => act(async () => watch(await api('/api/analytics/sync', {method: 'POST'}), 'Syncing analytics', () => loaders.ideas()));

// ---------------------------------------------------------------- BATCH
let batchRaw = null;
loaders.batch = async () => { $('#b-sample').href = `/api/batch/sample?t=${encodeURIComponent(T)}`; };
function showBatch(res) {
  batchRaw = res.raw;
  const bad = res.results.filter((r) => !r.ok).length;
  $('#b-table').innerHTML = `<table class="tbl"><thead><tr><th>#</th><th>status</th>${res.columns.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${
    res.results.map((r) => `<tr class="${r.ok ? '' : 'badrow'}"><td>${r.row}</td><td>${r.ok ? '<span class="badge ok">ok</span>' : `<span class="badge bad" title="${esc(r.errors.join('; '))}">error</span>`}</td>${
      res.columns.map((c) => `<td>${esc(String(r.data?.[c] ?? '').slice(0, 60))}</td>`).join('')}</tr>${r.ok ? '' : `<tr class="badrow"><td></td><td colspan="${res.columns.length + 1}">${esc(r.errors.join(' · '))}</td></tr>`}`).join('')}</tbody></table>`;
  $('#b-summary').textContent = `${res.results.length} row(s), ${bad} with errors.`;
  $('#b-run').disabled = bad > 0 || !res.results.length;
}
$('#b-interval').onchange = () => { $('#b-custom-wrap').hidden = $('#b-interval').value !== 'custom'; };
$('#b-file').onchange = () => act(async () => {
  const f = $('#b-file').files[0]; if (!f) return;
  const fd = new FormData(); fd.append('file', f); showBatch(await api('/api/batch/preview-file', {method: 'POST', body: fd}));
});
$('#b-load-url').onclick = () => act(async () => {
  const url = $('#b-url').value.trim(); if (!url) throw new Error('Paste a Google Sheets link first');
  showBatch(await api('/api/batch/preview-url', {method: 'POST', body: {url}}));
});
$('#b-run').onclick = () => act(async () => {
  const sel = $('#b-interval').value; const interval = sel === 'custom' ? $('#b-custom').value.trim() : sel;
  const start = $('#b-start').value ? `${$('#b-start').value}:00` : '';
  const job = await api('/api/batch/run', {method: 'POST', body: {raw: batchRaw, interval, start}});
  watch(job, 'Batch started: one video at a time', () => toast('Batch finished: see Library'));
});

// ---------------------------------------------------------------- LIBRARY (master-detail)
const lib = {q: '', style: '', aspect: '', page: 1, selected: null};
let libTimer = null;
async function loadLibraryList() {
  const qs = new URLSearchParams({q: lib.q, style: lib.style, aspect: lib.aspect, page: lib.page, per_page: 12});
  const r = await api(`/api/library?${qs}`);
  lib.page = r.page;
  opts($('#l-style'), ['', ...r.styles], lib.style);
  $('#l-list').innerHTML = r.items.map((v) => `
    <div class="item lib-item ${v.slug === lib.selected ? 'sel' : ''}" data-pick="${esc(v.slug)}">
      <div><div class="t">${esc(v.title)}</div><div class="s muted">${esc(v.style || '-')} · ${esc(v.aspect_ratio)} · ${new Date(v.mtime * 1000).toLocaleDateString()}</div></div>
      <div>${v.unverified ? `<span class="badge warn" title="unverified facts">${v.unverified} to verify</span>` : ''}
        <span class="badge ${v.qa_ok === false ? 'bad' : v.qa_ok ? 'ok' : ''}">QA ${v.qa_ok == null ? 'n/a' : v.qa_ok ? 'pass' : 'issues'}</span></div></div>`).join('') || '<p class="muted">Nothing matches.</p>';
  $('#l-page').textContent = `${r.total} video(s) · page ${r.page}/${r.pages}`;
  $('#l-prev').disabled = r.page <= 1; $('#l-next').disabled = r.page >= r.pages;
  $$('#l-list [data-pick]').forEach((el) => (el.onclick = () => act(() => openInspector(el.dataset.pick))));
  if (!lib.selected && r.items[0]) await openInspector(r.items[0].slug);
}
loaders.library = async () => { await loadLibraryList(); };
$('#l-q').oninput = (e) => { clearTimeout(libTimer); libTimer = setTimeout(() => { lib.q = e.target.value; lib.page = 1; act(loadLibraryList); }, 250); };
$('#l-style').onchange = (e) => { lib.style = e.target.value; lib.page = 1; act(loadLibraryList); };
$('#l-aspect').onchange = (e) => { lib.aspect = e.target.value; lib.page = 1; act(loadLibraryList); };
$('#l-prev').onclick = () => { lib.page -= 1; act(loadLibraryList); };
$('#l-next').onclick = () => { lib.page += 1; act(loadLibraryList); };
async function openInspector(slug) {
  lib.selected = slug;
  $$('#l-list [data-pick]').forEach((el) => el.classList.toggle('sel', el.dataset.pick === slug));
  const v = await api(`/api/library/${encodeURIComponent(slug)}`);
  const m = v.meta; const qa = v.qa;
  const frames = v.qa_frames.map((f) => {
    const r = qa?.frames?.find((x) => x.frame === f.name); const cls = r ? (r.ok ? 'ok' : 'bad') : '';
    return `<figure><img class="${cls}" loading="lazy" src="${file(f.src)}" data-zoom-src="${file(r && !r.ok && f.overlay ? f.overlay : f.src)}" title="${esc((r?.issues || []).join('; ') || 'ok')}"><figcaption>${esc(f.name)}${r && !r.ok ? ' ⚠' : ''}</figcaption></figure>`;
  }).join('');
  const issues = (qa?.frames || []).flatMap((f) => f.issues.map((i) => `${f.frame}: ${i}`));
  const open = (v.claims || []).filter((c) => !c.verified).map((c) => c.text);
  const facts = v.claims?.length ? open : (v.facts_to_verify || []);
  const aspect = m.aspect_ratio;
  $('#inspector').innerHTML = `
    ${v.has_video !== false ? `<video id="player" controls preload="metadata" playsinline src="${v.stream}?t=${encodeURIComponent(T)}" class="${aspect === '16:9' ? 'wide' : ''}"></video>` : '<p class="muted">no video file</p>'}
    <div class="row between"><h2>${esc(m.title)}</h2><span class="badge ${qa ? (qa.ok ? 'ok' : 'bad') : ''}">QA ${qa ? (qa.ok ? 'pass' : 'issues') : 'n/a'}</span></div>
    ${qa ? `<div class="qa">${frames}</div>` : ''}
    ${issues.length ? `<div class="warn">${issues.map(esc).join('<br>')}</div>` : ''}
    ${facts.length ? `<div class="warn"><b>Fact check:</b> ${v.grounded ? 'checked against web sources, these are still unverified' : 'not web-checked'}. Verify before posting:<ul>${facts.map((f) => `<li>${esc(f)}</li>`).join('')}</ul></div>`
      : (v.claims?.length ? '<div class="okbox">All numeric claims were verified against cited sources.</div>' : '')}
    ${(v.sources || []).length ? `<div class="s muted">Sources: ${v.sources.map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a>`).join(' · ')}</div>` : ''}
    <label>Title</label><input data-m="title" value="${esc(m.title)}">
    <label>Description</label><textarea data-m="description" rows="4">${esc(m.description)}</textarea>
    <div class="row"><div><label>Hashtags</label><input data-m="hashtags" value="${esc((m.hashtags || []).join(' '))}"></div>
      <div><label>Hashtags / tags (comma)</label><input data-m="tags" value="${esc((m.tags || []).join(', '))}"></div></div>
    <div class="actions"><button data-save>Save metadata</button><button data-regen>Regenerate with AI</button>
      <a href="${v.download}?t=${encodeURIComponent(T)}" download><button class="primary" type="button">Download MP4</button></a></div>
    <h3>Re-render</h3>
    <div class="actions"><button data-rerender="16:9" ${aspect === '16:9' ? 'disabled' : ''}>Re-render 16:9</button><button data-rerender="9:16" ${aspect === '9:16' ? 'disabled' : ''}>Re-render 9:16</button>
      <span class="s muted">replaces the current file</span></div>
    <h3>Publish</h3>
    <div class="row"><div><label>Published link (for analytics)</label><input data-pub-url value="${esc(v.published_url || '')}" placeholder="https://youtube.com/shorts/..."></div>
      <div style="align-self:end"><button data-save-url>Save link</button></div></div>
    ${v.stats ? `<div class="s muted">${v.stats.views ?? '?'} views · ${v.stats.likes ?? '?'} likes</div>` : ''}
    <div class="actions">
      <select data-p="platform" style="width:auto">${['youtube', 'instagram', 'tiktok'].map((p) => `<option>${p}</option>`).join('')}</select>
      <select data-p="visibility" style="width:auto"><option value="">YouTube: default (${esc(m.visibility || 'unlisted')})</option><option>unlisted</option><option>private</option><option>public</option></select>
      <label class="inline"><input type="checkbox" data-p="headed"> show browser</label>
      <button class="primary" data-publish>Publish Now</button><button data-schedule>Add to Schedule</button></div>`;
  const box = $('#inspector');
  $$('[data-zoom-src]', box).forEach((i) => (i.onclick = () => zoom(i.dataset.zoomSrc)));
  const val = (k) => $(`[data-m=${k}]`, box).value;
  $('[data-save]', box).onclick = () => act(async () => {
    await api(`/api/library/${encodeURIComponent(slug)}/meta`, {method: 'PUT', body: {title: val('title'), description: val('description'),
      hashtags: val('hashtags').split(/[\s,]+/).filter(Boolean), tags: val('tags').split(',').map((s) => s.trim()).filter(Boolean)}});
    toast('Metadata saved (kept on re-render)'); loadLibraryList();
  });
  $('[data-regen]', box).onclick = () => act(async () => watch(await api(`/api/library/${encodeURIComponent(slug)}/metadata`, {method: 'POST'}), 'AI metadata', () => openInspector(slug)));
  $('[data-save-url]', box).onclick = () => act(async () => { await api(`/api/projects/${encodeURIComponent(slug)}/published`, {method: 'PUT', body: {url: $('[data-pub-url]', box).value}}); toast('Link saved'); });
  $$('[data-rerender]', box).forEach((b) => (b.onclick = () => act(async () => {
    if (!confirm(`Re-render "${m.title}" as ${b.dataset.rerender}? The current video file is replaced.`)) return;
    const job = await api(`/api/projects/${encodeURIComponent(slug)}/render`, {method: 'POST', body: {aspect: b.dataset.rerender}});
    watch(job, `Re-rendering ${b.dataset.rerender}`, () => openInspector(slug));
  })));
  $('[data-schedule]', box).onclick = () => { pendingSchedule = [slug]; showTab('schedule'); };
  $('[data-publish]', box).onclick = () => act(async () => {
    const platform = $('[data-p=platform]', box).value;
    if (facts.length && !confirm('This video has unverified facts. Publish anyway?')) return;
    if (!confirm(`Upload "${m.title}" to ${platform} now?`)) return;
    const body = {platform, visibility: $('[data-p=visibility]', box).value, headed: $('[data-p=headed]', box).checked};
    watch(await api(`/api/library/${encodeURIComponent(slug)}/publish`, {method: 'POST', body}), `Uploading to ${platform}`);
  });
}
let pendingSchedule = null;

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
