// =============================================================================
// app.js — page wiring: hero, Form Lab UI, program, guided sessions, fuel
// calculator, V-taper tool, field notes and the progress tracker.
// =============================================================================
import { Stage } from './stage.js';
import { EXERCISES, EX_BY_ID } from './exercises.js';
import { MUSCLE_LABEL } from './rig.js';
import { loadAnatomyAssets, chooseLOD } from './anatomy.js';
import {
  PRINCIPLES, SESSIONS, PHASES, DAY_INFO, PROGRESSION_RULES, FIELD_NOTES,
} from './program.js';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const h = (tag, attrs = {}, html = '') => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  }
  if (html) el.innerHTML = html;
  return el;
};
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const store = {
  get(k, d) { try { const v = localStorage.getItem('forge:' + k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem('forge:' + k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
};

function webglOK() {
  try {
    const c = document.createElement('canvas');
    return !!(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl')));
  } catch { return false; }
}

// -----------------------------------------------------------------------------
// Principles
// -----------------------------------------------------------------------------
$('#principles').append(...PRINCIPLES.map((p) => h('article', { class: 'card principle reveal' },
  `<div class="k">${p.k}</div><h3>${esc(p.title)}</h3><p>${esc(p.body)}</p>`)));

// -----------------------------------------------------------------------------
// Hero stage — cycles through signature movements
// -----------------------------------------------------------------------------
const HERO_SEQ = ['pullup', 'pushup', 'swing', 'bss', 'dip', 'pike'];
let hero = null;
if (webglOK()) {
  try {
    hero = new Stage($('#heroCanvas'), { hero: true, pixelRatio: 1.5 });
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
    const applyMotion = () => { hero.controls.autoRotate = !reduce.matches; hero.playing = !reduce.matches; };
    reduce.addEventListener?.('change', applyMotion);
    let hi = 0;
    let reps = 0;
    const heroSet = (i) => {
      const ex = EX_BY_ID[HERO_SEQ[i]];
      hero.setExercise(ex, { transition: true });
      hero.speed = 0.9;
      $('#heroTag').textContent = ex.name;
    };
    heroSet(0);
    applyMotion();
    let lastRep = 0;
    hero.on(({ rep }) => {
      if (rep !== lastRep) {
        lastRep = rep;
        if (++reps >= 2) { reps = 0; hi = (hi + 1) % HERO_SEQ.length; heroSet(hi); lastRep = 0; }
      }
    });
  } catch (e) { console.warn('Hero 3D disabled', e); }
}

// -----------------------------------------------------------------------------
// Form Lab
// -----------------------------------------------------------------------------
const GROUPS = [
  ['Anatomy demo', ['elbow']],
  ['Push', ['pushup', 'pike', 'dip']],
  ['Pull', ['pullup', 'row']],
  ['Legs & hips', ['bss', 'rdl', 'bridge']],
  ['Shoulders & core', ['lateral', 'legraise', 'hollow']],
  ['Conditioning', ['swing']],
];
const exList = $('#exList');
for (const [g, ids] of GROUPS) {
  exList.append(h('div', { class: 'ex-group' }, g));
  for (const id of ids) {
    exList.append(h('button', { class: 'ex-btn', 'data-id': id, onclick: () => selectExercise(id) }, esc(EX_BY_ID[id].name)));
  }
}

let lab = null;
if (webglOK()) {
  try {
    lab = new Stage($('#labCanvas'));
    $('#labLoading').remove();
    // On touch screens let vertical swipes scroll the page; horizontal drags orbit.
    if (window.matchMedia('(pointer: coarse)').matches) lab.renderer.domElement.style.touchAction = 'pan-y';
    loadAnatomy();
  } catch (e) {
    console.warn(e);
    $('#labLoading').textContent = '3D unavailable on this device — the form cues on the right still apply.';
  }
} else {
  $('#labLoading').textContent = 'WebGL is not available in this browser — the form cues on the right still apply.';
}

let current = null;
let activeTab = 'cues';

function selectExercise(id, { scroll = false } = {}) {
  const ex = EX_BY_ID[id];
  current = ex;
  $$('.ex-btn').forEach((b) => { b.classList.toggle('on', b.dataset.id === id); b.setAttribute('aria-pressed', String(b.dataset.id === id)); });
  const onBtn = exList.querySelector(`.ex-btn[data-id="${id}"]`);
  if (onBtn && exList.scrollWidth > exList.clientWidth) {
    exList.scrollTo({ left: onBtn.offsetLeft - exList.clientWidth / 2 + onBtn.offsetWidth / 2, behavior: 'smooth' });
  }
  $('#hudName').textContent = ex.name;
  $('#hudPattern').textContent = ex.pattern;
  $('#legend').innerHTML = [
    ...ex.primary.map((m) => `<span class="mchip p"><i></i>${MUSCLE_LABEL[m]}</span>`),
    ...ex.secondary.map((m) => `<span class="mchip s"><i></i>${MUSCLE_LABEL[m]}</span>`),
  ].join('');
  $('#presc').innerHTML = `
    <div><small>Sets × reps</small><strong>${esc(ex.prescription)}</strong></div>
    <div><small>Tempo</small><strong>${esc(ex.tempoCode)}</strong></div>
    <div><small>Rest</small><strong>${esc(ex.rest)}</strong></div>`;
  $('#insight').innerHTML = `<b>Why it’s in FORGE</b>${esc(ex.insight)}`;
  renderTab();

  const total = ex.tempo.reduce((s, t) => s + t.dur, 0);
  $('#tlSegs').innerHTML = ex.tempo.map((t, i) =>
    `<div class="tl-seg ${t.from === t.to ? 'hold' : ''}" data-i="${i}" style="width:${(t.dur / total) * 100}%"><span>${esc(t.label)} · ${t.dur}s</span></div>`).join('');

  const fb = $('#faultBanner');
  fb.textContent = '✕ ' + (ex.fault?.label || '');
  fb.hidden = !(lab?.toggles.fault && ex.fault);

  if (lab) {
    lab.setExercise(ex);
    $$('#viewBtns button').forEach((b) => b.classList.toggle('on', b.dataset.view === lab.view));
  }
  if (scroll) $('#lab').scrollIntoView({ behavior: 'smooth' });
}

function renderTab() {
  const ex = current;
  const body = $('#tabBody');
  if (activeTab === 'cues') body.innerHTML = `<ol>${ex.cues.map((c) => `<li>${esc(c)}</li>`).join('')}</ol>`;
  if (activeTab === 'mistakes') body.innerHTML = `<ul>${ex.mistakes.map((c) => `<li>${esc(c)}</li>`).join('')}</ul><p style="margin-top:10px;color:var(--dim);font-size:13px">Turn on <b style="color:var(--bad)">Mistake mode</b> to see the main fault animated in red.</p>`;
  if (activeTab === 'breathing') body.innerHTML = `<p>${esc(ex.breathing)}</p><p style="margin-top:12px;color:var(--dim);font-size:13px">Tempo <b style="color:var(--text)">${esc(ex.tempoCode)}</b> = seconds lowering · pause in the stretch · lifting · pause at the top.</p>`;
  if (activeTab === 'progressions') body.innerHTML = `<ol class="ladder">${ex.progressions.map((c) => `<li>${esc(c)}</li>`).join('')}</ol><p style="margin-top:10px;color:var(--dim);font-size:13px">Move up one step when you hit the top of the rep range on every set with clean tempo.</p>`;
}

$('#tabs').addEventListener('click', (e) => {
  const t = e.target.closest('.tab');
  if (!t) return;
  activeTab = t.dataset.tab;
  $$('.tab').forEach((x) => { x.classList.toggle('on', x === t); x.setAttribute('aria-selected', String(x === t)); });
  renderTab();
});

if (lab) {
  const pill = $('#phasePill');
  const tlEl = $('#timeline');
  tlEl.addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault();
    const now = (+tlEl.getAttribute('aria-valuenow') || 0) / 100;
    lab.playing = false;
    $('#playBtn').textContent = '▶';
    lab.seek(Math.min(0.999, Math.max(0, now + (e.key === 'ArrowRight' ? 0.05 : -0.05))));
  });
  let lastSeg = null;
  lab.on(({ seg, index, cycleT, rep }) => {
    $('#tlHead').style.left = `calc(${(cycleT * 100).toFixed(2)}% - 1px)`;
    tlEl.setAttribute('aria-valuenow', String(Math.round(cycleT * 100)));
    if (seg !== lastSeg) {
      lastSeg = seg;
      $('#phaseName').textContent = seg.label;
      pill.classList.toggle('hold', seg.from === seg.to);
      $$('.tl-seg').forEach((s, i) => s.classList.toggle('on', i === index));
    }
    $('#repCount').textContent = rep;
  });

  $('#playBtn').addEventListener('click', () => {
    lab.playing = !lab.playing;
    $('#playBtn').textContent = lab.playing ? '❚❚' : '▶';
    $('#playBtn').setAttribute('aria-label', lab.playing ? 'Pause' : 'Play');
  });
  $('#speed').addEventListener('change', (e) => (lab.speed = +e.target.value));

  const tl = $('#timeline');
  let dragging = false;
  const seekAt = (e) => {
    const r = tl.getBoundingClientRect();
    lab.seek(Math.min(0.999, Math.max(0, (e.clientX - r.left) / r.width)));
  };
  tl.addEventListener('pointerdown', (e) => { dragging = true; tl.setPointerCapture(e.pointerId); seekAt(e); });
  tl.addEventListener('pointermove', (e) => dragging && seekAt(e));
  tl.addEventListener('pointerup', () => (dragging = false));

  $('#toggles').addEventListener('click', (e) => {
    const c = e.target.closest('.chip');
    if (!c) return;
    const k = c.dataset.t;
    const v = !lab.toggles[k];
    lab.setToggle(k, v);
    c.classList.toggle('on', v);
    c.setAttribute('aria-pressed', String(v));
    if (k === 'fault') $('#faultBanner').hidden = !(v && current?.fault);
  });

  $('#layerSeg').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    lab.setLayer(b.dataset.layer);
    $$('#layerSeg button').forEach((x) => { x.classList.toggle('on', x === b); x.setAttribute('aria-checked', String(x === b)); });
  });

  $('#viewBtns').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    lab.setView(b.dataset.view);
    $$('#viewBtns button').forEach((x) => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', String(x === b)); });
  });
}
selectExercise('pushup');

// -----------------------------------------------------------------------------
// Anatomical model: load, swap in, inspect
// -----------------------------------------------------------------------------
// Handles for debugging / automated checks.
window.__forge = { get lab() { return lab; }, get hero() { return hero; } };

async function loadAnatomy() {
  const status = $('#anatStatus');
  const lod = new URLSearchParams(location.search).get('quality') || chooseLOD();
  status.textContent = `Loading anatomical model (${lod === 'standard' ? 'high detail, ~12 MB' : 'mobile detail, ~5 MB'})…`;
  try {
    const assets = await loadAnatomyAssets('assets/anatomy', lod);
    lab.useAnatomy(assets);
    if (current) selectExercise(current.id);
    hero?.useAnatomy(assets);
    status.textContent = '';
  } catch (e) {
    console.warn('anatomy model failed to load', e);
    status.textContent = 'The anatomical model could not be loaded; showing the simplified figure.';
  }
}

function showInspect(sid) {
  const card = $('#inspectCard');
  if (sid == null || !lab?.rig?.meta) { card.hidden = true; $('#inspectHint').hidden = false; return; }
  const st = lab.rig.meta.structures[sid];
  const clean = (t) => (t || '').replace(/[()]/g, '');
  $('#inspName').textContent = clean(st.name) + (st.side ? (st.side === 'L' ? ' (left)' : ' (right)') : '');
  $('#inspLatin').textContent = clean(st.latin);
  const region = (st.parent || '').split('.').pop().replace(/_[lr]$/, '').replace(/_/g, ' ');
  const kind = { muscle: 'Muscle', fascia: 'Fascia / aponeurosis', bone: 'Bone', eye: 'Eye', skin: 'Skin' }[st.type] || st.type;
  $('#inspMeta').textContent = `${kind}${region ? ' · ' + region : ''}${st.group && MUSCLE_LABEL[st.group] ? ' · trained as ' + MUSCLE_LABEL[st.group] : ''}`;
  card.hidden = false;
  $('#inspectHint').hidden = true;
  $('#inspIsolate').classList.toggle('on', lab.rig.isolated === sid);
  $('#inspIsolate').setAttribute('aria-pressed', String(lab.rig.isolated === sid));
}

if (lab) {
  const cv = lab.renderer.domElement;
  let down = null;
  cv.addEventListener('pointerdown', (e) => { down = [e.clientX, e.clientY]; });
  cv.addEventListener('pointerup', (e) => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5 || !lab.rig.isAnatomy) return;
    const sid = lab.pick(e.clientX, e.clientY);
    if (lab.rig.isolated != null && sid !== lab.rig.isolated) return; // keep isolation stable
    lab.select(sid);
    showInspect(sid);
  });
  $('#inspClear').addEventListener('click', () => {
    if (lab.rig.isolated != null) lab.rig.isolate(false);
    lab.select(null);
    showInspect(null);
  });
  $('#inspIsolate').addEventListener('click', () => {
    if (!lab.rig.isAnatomy || lab.selected == null) return;
    lab.rig.isolate(lab.rig.isolated == null);
    showInspect(lab.selected);
  });
}

// -----------------------------------------------------------------------------
// Program
// -----------------------------------------------------------------------------
let phaseIdx = 0;
let altWeek = false;
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function renderPhase() {
  const p = PHASES[phaseIdx];
  $('#phaseTabs').innerHTML = PHASES.map((x, i) =>
    `<button class="phase-tab ${i === phaseIdx ? 'on' : ''}" data-i="${i}"><small>${x.weeks}</small><strong>Phase ${x.id} · ${x.name}</strong></button>`).join('');
  $('#phaseCard').innerHTML = `
    <div><small>Goal</small><strong>${esc(p.goal)}</strong><ul>${p.extras.map((e) => `<li>${esc(e)}</li>`).join('')}</ul></div>
    <div><small>Effort</small>${esc(p.rir)}</div>
    <div><small>Volume</small>${esc(p.sets)}</div>
    <div><small>Calories</small>${esc(p.deficit)}</div>
    <div><small>Steps</small>${esc(p.steps)}</div>`;
  const week = altWeek ? p.alt : p.week;
  $('#week').innerHTML = week.map((d, i) => {
    const train = /^[ABF]/.test(d);
    const info = train
      ? d.split(' + ').map((k) => SESSIONS[k.trim()]?.focus).filter(Boolean).join(' + ')
      : DAY_INFO[d];
    return `<div class="day ${train ? 'train' : ''}"><small>${DAYS[i]}</small><strong>${esc(train ? 'Session ' + d : d)}</strong><p>${esc(info || '')}</p></div>`;
  }).join('') + `<div class="week-toggle"><button class="chip ${altWeek ? '' : 'on'}" data-w="0">Odd weeks (A·B·A)</button><button class="chip ${altWeek ? 'on' : ''}" data-w="1">Even weeks (B·A·B)</button></div>`;
}
$('#phaseTabs').addEventListener('click', (e) => {
  const b = e.target.closest('.phase-tab');
  if (b) { phaseIdx = +b.dataset.i; renderPhase(); }
});
$('#week').addEventListener('click', (e) => {
  const b = e.target.closest('[data-w]');
  if (b) { altWeek = b.dataset.w === '1'; renderPhase(); }
});
renderPhase();

$('#sessions').append(...Object.entries(SESSIONS).map(([key, s]) => {
  const card = h('article', { class: 'card session reveal' });
  card.innerHTML = `<h3>${esc(s.name)}</h3><p class="focus">${esc(s.focus)}</p>` +
    s.items.map(([id, sr, tempo, rest, note]) => `
      <div class="ex-row">
        <button data-ex="${id}">${esc(EX_BY_ID[id].name)}</button>
        <span class="sr">${esc(sr)}</span>
        <span class="meta">Tempo ${esc(tempo)} · Rest ${esc(rest)} · ${esc(note)}</span>
      </div>`).join('');
  card.append(h('button', { class: key === 'F' ? 'btn btn-ghost' : 'btn', onclick: () => startSession(key) },
    key === 'F' ? 'Start finisher' : `Start ${key === 'A' ? 'Session A' : 'Session B'}`));
  card.addEventListener('click', (e) => {
    const b = e.target.closest('[data-ex]');
    if (b) selectExercise(b.dataset.ex, { scroll: true });
  });
  return card;
}));

$('#rules').append(...PROGRESSION_RULES.map(([t, b]) => h('div', { class: 'card rule reveal' }, `<strong>${esc(t)}</strong><p>${esc(b)}</p>`)));

// -----------------------------------------------------------------------------
// Guided session mode (lives inside the Form Lab viewer)
// -----------------------------------------------------------------------------
let session = null;
let restTimer = null;
const hud = $('#sessionHud');

function parseSets(sr) { const m = /^(\d+)\s*×/.exec(sr); return m ? +m[1] : 1; }
function parseRest(r) {
  const m = /(\d+)\s*(s|min)/.exec(r);
  if (!m) return 45;
  return m[2] === 'min' ? +m[1] * 60 : +m[1];
}
function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.18, 0.36].forEach((t, i) => {
      const o = ctx.createOscillator(); const g = ctx.createGain();
      o.frequency.value = i === 2 ? 1046 : 784;
      g.gain.setValueAtTime(0.0001, ctx.currentTime + t);
      g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + t + 0.15);
      o.connect(g).connect(ctx.destination);
      o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 0.16);
    });
  } catch { /* audio unavailable */ }
}

function startSession(key) {
  const s = SESSIONS[key];
  document.body.classList.add('in-session');
  session = { key, s, i: 0, set: 1, resting: false };
  showSessionExercise();
  $('#lab').scrollIntoView({ behavior: 'smooth' });
}
function showSessionExercise() {
  const [id] = session.s.items[session.i];
  selectExercise(id);
  renderHud();
}
function renderHud() {
  if (!session) { hud.hidden = true; return; }
  const [id, sr, tempo, rest, note] = session.s.items[session.i];
  const sets = parseSets(sr);
  const dots = session.s.items.map((_, i) => `<i class="${i < session.i ? 'done' : ''}"></i>`).join('');
  hud.hidden = false;
  if (session.resting) {
    hud.innerHTML = `<h4>Rest · breathe</h4><div class="rest-timer" id="restLeft" role="timer" aria-live="off">${fmt(session.restLeft)}</div>
      <div class="meta" style="text-align:center">Next: set ${session.set} of ${sets} · ${esc(EX_BY_ID[id].name)}</div>
      <div class="row"><button class="btn btn-ghost btn-sm" data-a="skip">Skip rest</button><button class="btn btn-ghost btn-sm" data-a="add">+15 s</button></div>
      <div class="dots">${dots}</div>`;
  } else {
    hud.innerHTML = `<h4>${esc(session.s.name.split('—')[0])}· ${session.i + 1}/${session.s.items.length}</h4>
      <div class="big">${esc(EX_BY_ID[id].name)}</div>
      <div class="meta">Set <b style="color:var(--text)">${session.set} / ${sets}</b> · ${esc(sr.replace(/^\d+\s*×\s*/, ''))}</div>
      <div class="meta">Tempo ${esc(tempo)} · ${esc(note)}</div>
      <div class="row"><button class="btn btn-sm" data-a="done">Set done ✓</button><button class="btn btn-ghost btn-sm" data-a="end">End</button></div>
      <div class="dots">${dots}</div>`;
  }
}
const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.max(0, s % 60)).padStart(2, '0')}`;

hud.addEventListener('click', (e) => {
  const a = e.target.closest('[data-a]')?.dataset.a;
  if (!a || !session) return;
  const [, sr, , rest] = session.s.items[session.i];
  const sets = parseSets(sr);
  if (a === 'end') { endSession(false); return; }
  if (a === 'done') {
    const lastSet = session.set >= sets;
    const lastEx = session.i >= session.s.items.length - 1;
    if (lastSet && lastEx) { endSession(true); return; }
    if (lastSet) { session.i++; session.set = 1; } else session.set++;
    session.resting = true;
    session.restLeft = parseRest(rest);
    renderHud();
    clearInterval(restTimer);
    restTimer = setInterval(() => {
      session.restLeft--;
      const el = $('#restLeft');
      if (el) el.textContent = fmt(session.restLeft);
      if (session.restLeft <= 0) { clearInterval(restTimer); beep(); session.resting = false; showSessionExercise(); }
    }, 1000);
    if (lastSet) selectExercise(session.s.items[session.i][0]);
  }
  if (a === 'skip') { clearInterval(restTimer); session.resting = false; showSessionExercise(); }
  if (a === 'add') { session.restLeft += 15; }
});

function endSession(completed) {
  clearInterval(restTimer);
  document.body.classList.remove('in-session');
  if (completed && session.key !== 'F') {
    const t = store.get('tracker', []);
    const idx = [...Array(36).keys()].find((i) => !t.includes(i));
    if (idx !== undefined) { t.push(idx); store.set('tracker', t); renderTracker(); }
    hud.innerHTML = `<h4>Session complete</h4><div class="big">Logged ✓</div><div class="meta">Ticked off in your tracker. Hit your protein and steps today.</div><div class="row"><button class="btn btn-ghost btn-sm" data-close>Close</button></div>`;
  } else if (completed) {
    hud.innerHTML = `<h4>Finisher complete</h4><div class="big">Done ✓</div><div class="meta">Walk it off for 5 minutes.</div><div class="row"><button class="btn btn-ghost btn-sm" data-close>Close</button></div>`;
  } else {
    hud.hidden = true;
  }
  session = null;
}
hud.addEventListener('click', (e) => { if (e.target.closest('[data-close]')) hud.hidden = true; });
$('#navStart').addEventListener('click', () => startSession('A'));

// On phones the session panel sits under the 3D view instead of covering it.
const phoneMQ = window.matchMedia('(max-width: 640px)');
const placeHud = () => {
  if (phoneMQ.matches) $('#labCanvas').after(hud);
  else $('#labCanvas').append(hud);
};
phoneMQ.addEventListener?.('change', placeHud);
placeHud();

// Compact menu for small screens.
const navMenu = $('#navMenu');
navMenu.addEventListener('click', () => {
  const open = $('#nav').classList.toggle('open');
  navMenu.setAttribute('aria-expanded', String(open));
});
$('#navLinks').addEventListener('click', (e) => {
  if (e.target.closest('a')) { $('#nav').classList.remove('open'); navMenu.setAttribute('aria-expanded', 'false'); }
});

// -----------------------------------------------------------------------------
// Fuel calculator
// -----------------------------------------------------------------------------
const calc = $('#calc');
let unit = 'metric';
function renderCalc() {
  const f = new FormData(calc);
  const newUnit = f.get('unit');
  if (newUnit !== unit) {
    const w = calc.weight; const ht = calc.height;
    if (newUnit === 'imperial') { w.value = (w.value * 2.2046).toFixed(0); ht.value = (ht.value / 2.54).toFixed(0); }
    else { w.value = (w.value / 2.2046).toFixed(1); ht.value = (ht.value * 2.54).toFixed(0); }
    unit = newUnit;
    if (unit === 'imperial') { w.min = 77; w.max = 660; ht.min = 47; ht.max = 90; }
    else { w.min = 35; w.max = 300; ht.min = 120; ht.max = 230; }
    $('#wLabel').textContent = unit === 'metric' ? 'Weight (kg)' : 'Weight (lb)';
    $('#hLabel').textContent = unit === 'metric' ? 'Height (cm)' : 'Height (in)';
  }
  const sex = f.get('sex');
  const age = +calc.age.value || 30;
  const kg = unit === 'metric' ? +calc.weight.value : +calc.weight.value / 2.2046;
  const cm = unit === 'metric' ? +calc.height.value : +calc.height.value * 2.54;
  const act = +f.get('activity');
  const def = +f.get('goal');
  if (!kg || !cm) return;
  const bmr = 10 * kg + 6.25 * cm - 5 * age + (sex === 'm' ? 5 : -161);
  // +~150 kcal/day averages the three weekly sessions
  const tdee = bmr * act + 150;
  const target = Math.round((tdee * (1 - def)) / 10) * 10;
  const proteinPerKg = def >= 0.25 ? 2.3 : 2.0;
  // Large bodies: base protein on an estimate of lean-ish mass (height − 100).
  const proteinKg = Math.min(kg, Math.max(cm - 100, 45) * 1.1);
  const protein = Math.round(proteinKg * proteinPerKg);
  const fat = Math.round(Math.max(kg * 0.7, (target * 0.25) / 9));
  const carbs = Math.max(0, Math.round((target - protein * 4 - fat * 9) / 4));
  const weeklyKg = ((tdee - target) * 7) / 7700;
  const pct = (weeklyKg / kg) * 100;
  const U = unit === 'metric' ? 'kg' : 'lb';
  const wk = unit === 'metric' ? weeklyKg : weeklyKg * 2.2046;
  const tot = protein * 4 + fat * 9 + carbs * 4;
  const steps = def >= 0.25 ? '12k' : def >= 0.2 ? '10k' : '8k';
  $('#results').innerHTML = `
    <div class="stat hl"><small>Daily calories</small><strong>${target.toLocaleString()}</strong><span>maintenance ≈ ${Math.round(tdee).toLocaleString()} kcal</span></div>
    <div class="stat"><small>Protein</small><strong>${protein} g</strong><span>${proteinKg < kg ? `${proteinPerKg} g/kg of ~${Math.round(proteinKg)} kg target weight` : `${proteinPerKg} g/kg`} · 3–4 meals</span></div>
    <div class="stat"><small>Expected loss</small><strong>${wk.toFixed(2)} ${U}</strong><span>per week · ${pct.toFixed(2)}% bodyweight</span></div>
    <div class="stat"><small>Steps</small><strong>${steps}</strong><span>per day · + walks after meals</span></div>
    <div class="stat macro"><small>Macro split</small>
      <div class="macro-bar"><i style="width:${(protein * 400) / tot}%;background:var(--ember)"></i><i style="width:${(fat * 900) / tot}%;background:var(--amber)"></i><i style="width:${(carbs * 400) / tot}%;background:var(--cyan)"></i></div>
      <div class="macro-legend"><span><i style="background:var(--ember)"></i>Protein <b>${protein} g</b></span><span><i style="background:var(--amber)"></i>Fat <b>${fat} g</b></span><span><i style="background:var(--cyan)"></i>Carbs <b>${carbs} g</b> — most of them around training</span></div>
    </div>
    ${target < Math.max(bmr, sex === 'm' ? 1500 : 1200) ? `<div class="warn">${target.toLocaleString()} kcal is below your resting needs (≈${Math.round(Math.max(bmr, sex === 'm' ? 1500 : 1200)).toLocaleString()} kcal). Use a gentler goal, or diet this low only with medical supervision.</div>` : ''}
    ${pct > 1 ? '<div class="warn">Faster than 1% of bodyweight per week usually costs muscle. Consider the −20% setting unless you have a lot of fat to lose.</div>' : ''}
    <div class="stat macro"><small>Water & micronutrients</small><span>≈ ${(kg * 0.035).toFixed(1)} L water/day · 30 g+ fibre · 2–3 fist-sized portions of vegetables per meal · creatine monohydrate 3–5 g/day is the one supplement with strong evidence.</span></div>`;
}
calc.addEventListener('input', renderCalc);
calc.addEventListener('change', renderCalc);
renderCalc();

// V-taper ratio
function renderRatio() {
  const s = +$('#shoulders').value; const w = +$('#waist').value;
  if (!s || !w) return;
  const r = s / w;
  const needS = (w * 1.618).toFixed(1);
  const needW = (s / 1.618).toFixed(1);
  const verdict = r >= 1.6 ? 'Golden zone ✓' : r >= 1.45 ? 'Athletic — keep going' : 'Building phase';
  $('#ratioOut').innerHTML = `${r.toFixed(2)}<small>${verdict} · target: shoulders ${needS} or waist ${needW}</small>`;
  $('#ratioFill').style.width = `${Math.min(100, Math.max(0, ((r - 1) / 0.8) * 100))}%`;
}
$('#shoulders').addEventListener('input', renderRatio);
$('#waist').addEventListener('input', renderRatio);
renderRatio();

// -----------------------------------------------------------------------------
// Field notes
// -----------------------------------------------------------------------------
const TAGS = { research: ['tag-research', 'Research'], craft: ['tag-craft', 'Coach craft'], forge: ['tag-forge', 'FORGE method'] };
function renderNotes(filter = 'all') {
  $('#notesGrid').innerHTML = FIELD_NOTES.filter((n) => filter === 'all' || n.tag === filter).map((n) => `
    <article class="card note">
      <span class="tag ${TAGS[n.tag][0]}">${TAGS[n.tag][1]}</span>
      <h3>${esc(n.title)}</h3>
      <p>${esc(n.body)}</p>
      <div class="how">${esc(n.how)}</div>
      <div class="ref">${esc(n.ref)}</div>
    </article>`).join('');
}
$('#noteFilters').addEventListener('click', (e) => {
  const c = e.target.closest('.chip');
  if (!c) return;
  $$('#noteFilters .chip').forEach((x) => x.classList.toggle('on', x === c));
  renderNotes(c.dataset.f);
});
renderNotes();

// -----------------------------------------------------------------------------
// Tracker
// -----------------------------------------------------------------------------
function renderTracker() {
  const done = new Set(store.get('tracker', []));
  const grid = $('#trackerGrid');
  grid.innerHTML = '';
  for (let w = 0; w < 12; w++) {
    const phase = w < 4 ? 1 : w < 8 ? 2 : 3;
    const col = h('div', { class: `tw p${phase} ${w === 7 ? 'deload' : ''}` }, `<small>W${w + 1}${w === 7 ? ' · DL' : ''}</small>`);
    const pattern = w % 2 === 0 ? ['A', 'B', 'A'] : ['B', 'A', 'B'];
    for (let s = 0; s < 3; s++) {
      const i = w * 3 + s;
      col.append(h('button', {
        class: `tcell ${done.has(i) ? 'done' : ''}`,
        'aria-label': `Week ${w + 1} session ${pattern[s]}`,
        'aria-pressed': done.has(i) ? 'true' : 'false',
        onclick: () => {
          const t = new Set(store.get('tracker', []));
          t.has(i) ? t.delete(i) : t.add(i);
          store.set('tracker', [...t]);
          renderTracker();
        },
      }, pattern[s]));
    }
    grid.append(col);
  }
  const n = done.size;
  $('#ringPct').textContent = `${Math.round((n / 36) * 100)}%`;
  $('#ringCount').textContent = `${n} / 36`;
  $('#ringFg').style.strokeDashoffset = 326.7 * (1 - n / 36);
}
// Two-tap reset (no confirm() dialog — it is blocked in sandboxed frames).
let resetArmed = null;
$('#resetTracker').addEventListener('click', (e) => {
  const btn = e.currentTarget;
  if (resetArmed) {
    clearTimeout(resetArmed); resetArmed = null;
    store.set('tracker', []); renderTracker();
    btn.textContent = 'Reset';
    return;
  }
  btn.textContent = 'Tap again to reset';
  resetArmed = setTimeout(() => { resetArmed = null; btn.textContent = 'Reset'; }, 3000);
});
renderTracker();

// -----------------------------------------------------------------------------
// Scroll reveal
// -----------------------------------------------------------------------------
const io = new IntersectionObserver((entries) => {
  entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
}, { threshold: 0.12 });
$$('.reveal').forEach((el) => io.observe(el));
