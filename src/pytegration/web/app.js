/*
 * Cosmic Explorer — page logic. LESSON: Module 11 (docs/11-cosmic-explorer.md)
 *
 * No framework, no build step: a small helper (`h`) builds DOM nodes, and every
 * piece of text goes in through `textContent`, never `innerHTML`.
 * SECURITY: that matters most for Nova's replies, which come from an LLM — text
 * set via textContent can never become live HTML/script (no XSS), and the
 * page's Content-Security-Policy is a second line of defence.
 *
 * PRIVACY: progress (XP, badges) and the name on the address card live only in
 * this browser's localStorage. Nothing personal is sent to the server.
 */
"use strict";

const API = "/api/v1/cosmos";
const LY_KM = 9_460_730_472_580.8;

// ---------------------------------------------------------------------------
// Tiny DOM helpers
// ---------------------------------------------------------------------------
const $ = (sel, root = document) => root.querySelector(sel);

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "text") el.textContent = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "style") Object.assign(el.style, value);
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

function fmt(n, digits = 1) {
  const abs = Math.abs(n);
  const words = [[1e12, "trillion"], [1e9, "billion"], [1e6, "million"]];
  for (const [t, w] of words) if (abs >= t) return `${+(n / t).toFixed(digits)} ${w}`;
  return abs >= 100 ? Math.round(n).toLocaleString() : (+n.toFixed(digits)).toLocaleString();
}

async function api(path, options = {}) {
  // GOTCHA: spread `options` FIRST, then build headers — otherwise a caller's
  //   `headers` would replace (not merge with) the JSON Content-Type.
  const response = await fetch(path.startsWith("/") ? path : `${API}/${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  let body = null;
  try { body = await response.json(); } catch { /* non-JSON body */ }
  if (!response.ok) {
    const err = new Error(body?.error?.message || `Request failed (${response.status})`);
    err.status = response.status;
    throw err;
  }
  return body;
}

// ---------------------------------------------------------------------------
// Progress: XP, ranks and badges (stored only in this browser)
// ---------------------------------------------------------------------------
const STORE_KEY = "cosmic-explorer:v1";

const RANKS = [
  { xp: 0, name: "Space Cadet" },
  { xp: 40, name: "Star Spotter" },
  { xp: 100, name: "Planet Hopper" },
  { xp: 180, name: "Galaxy Navigator" },
  { xp: 280, name: "Cosmic Explorer" },
];

const BADGES = [
  { id: "address", emoji: "🏠", name: "Cosmic Address", how: "Zoom out to the edge of the observable universe." },
  { id: "hopper", emoji: "🪐", name: "Planet Hopper", how: "Visit 8 different worlds." },
  { id: "time", emoji: "⏳", name: "Time Traveller", how: "See light that's over a billion years old." },
  { id: "gym", emoji: "💪", name: "Space Athlete", how: "Weigh yourself on other worlds." },
  { id: "walker", emoji: "🚶", name: "Solar System Walker", how: "Walk the scale model all the way out." },
  { id: "stargazer", emoji: "🌙", name: "Stargazer", how: "Complete 3 sky missions." },
  { id: "ace", emoji: "🧠", name: "Quiz Ace", how: "Get 5 out of 5 in a quiz." },
  { id: "curious", emoji: "❓", name: "Curious Mind", how: "Ask Nova a question." },
  { id: "dream", emoji: "🌟", name: "Dream Big", how: "Pick a space job you'd love." },
];

const progress = loadProgress();

function loadProgress() {
  const empty = { xp: 0, badges: [], seen: [], zoomMax: 1, missions: [], correct: [], dream: null, asks: 0 };
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? { ...empty, ...JSON.parse(raw) } : empty;
  } catch {
    return empty; // private mode / blocked storage: play without saving
  }
}

function saveProgress() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(progress)); } catch { /* ignore */ }
}

function addXp(amount, reason) {
  if (amount <= 0) return;
  const before = currentRank().name;
  progress.xp += amount;
  saveProgress();
  renderRank();
  const after = currentRank().name;
  if (after !== before) toast(`🎉 New rank: ${after}!`);
  else if (reason) toast(`+${amount} XP · ${reason}`);
}

function award(id) {
  if (progress.badges.includes(id)) return;
  const badge = BADGES.find((b) => b.id === id);
  progress.badges.push(id);
  saveProgress();
  toast(`${badge.emoji} Badge unlocked: ${badge.name}!`);
  progress.xp += 15;
  saveProgress();
  renderRank();
}

function currentRank() {
  return [...RANKS].reverse().find((r) => progress.xp >= r.xp);
}

function renderRank() {
  const rank = currentRank();
  const next = RANKS.find((r) => r.xp > progress.xp);
  $("#rank-name").textContent = rank.name;
  $("#xp").textContent = progress.xp;
  const pct = next ? ((progress.xp - rank.xp) / (next.xp - rank.xp)) * 100 : 100;
  $("#rank-fill").style.width = `${Math.min(100, pct)}%`;
}

let toastTimer = null;
function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.hidden = false;
  el.style.animation = "none";
  void el.offsetWidth; // restart the CSS animation
  el.style.animation = "";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2600);
}

function openBadges() {
  const rank = currentRank();
  const next = RANKS.find((r) => r.xp > progress.xp);
  $("#badges-rank").textContent = next
    ? `You're a ${rank.name} with ${progress.xp} XP. ${next.xp - progress.xp} XP to ${next.name}!`
    : `You're a ${rank.name} with ${progress.xp} XP — the highest rank. Amazing!`;
  $("#badges-list").replaceChildren(...BADGES.map((b) => h("li", { class: progress.badges.includes(b.id) ? "" : "locked" },
    h("span", { class: "em", "aria-hidden": "true", text: b.emoji }),
    h("strong", { text: b.name }),
    h("span", { class: "sub", text: progress.badges.includes(b.id) ? " ✓ Unlocked" : ` — ${b.how}` }),
  )));
  $("#badges-dialog").showModal();
}

// ---------------------------------------------------------------------------
// Tabs (with #hash routing so links and the back button work)
// ---------------------------------------------------------------------------
const loaders = {}; // tab name -> function to run the first time it opens
const loaded = new Set();

function showTab(name, { focus = false } = {}) {
  const tabs = [...document.querySelectorAll("[role=tab]")];
  if (!tabs.some((t) => t.dataset.tab === name)) name = "zoom";
  for (const tab of tabs) {
    const active = tab.dataset.tab === name;
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
    $(`#panel-${tab.dataset.tab}`).hidden = !active;
    if (active) tab.scrollIntoView({ block: "nearest", inline: "nearest" });
    if (active && focus) tab.focus();
  }
  if (!loaded.has(name) && loaders[name]) {
    loaded.add(name);
    loaders[name]();
  }
}

function initTabs() {
  const tablist = $("[role=tablist]");
  tablist.addEventListener("click", (e) => {
    const tab = e.target.closest("[role=tab]");
    if (tab) location.hash = tab.dataset.tab;
  });
  tablist.addEventListener("keydown", (e) => {
    if (!["ArrowLeft", "ArrowRight"].includes(e.key)) return;
    const tabs = [...tablist.querySelectorAll("[role=tab]")];
    const i = tabs.indexOf(document.activeElement);
    const next = tabs[(i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
    location.hash = next.dataset.tab;
    next.focus();
  });
  window.addEventListener("hashchange", () => showTab(location.hash.slice(1)));
}

// ---------------------------------------------------------------------------
// Starfield background
// ---------------------------------------------------------------------------
function initStars() {
  const canvas = $("#stars");
  const ctx = canvas.getContext("2d");
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let stars = [];

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = innerWidth * dpr;
    canvas.height = innerHeight * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = Math.round((innerWidth * innerHeight) / 4500);
    stars = Array.from({ length: count }, () => ({
      x: Math.random() * innerWidth,
      y: Math.random() * innerHeight,
      r: Math.random() * 1.3 + 0.2,
      a: Math.random() * 0.7 + 0.3,
      s: Math.random() * 0.02 + 0.004,
    }));
    draw();
  }

  function draw() {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    for (const st of stars) {
      ctx.globalAlpha = st.a;
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      ctx.arc(st.x, st.y, st.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function twinkle() {
    for (const st of stars) {
      st.a += (Math.random() - 0.5) * st.s * 4;
      st.a = Math.max(0.15, Math.min(1, st.a));
    }
    draw();
    setTimeout(() => requestAnimationFrame(twinkle), 120);
  }

  addEventListener("resize", resize);
  resize();
  if (!still) twinkle();
}

// ---------------------------------------------------------------------------
// Cosmic Zoom
// ---------------------------------------------------------------------------
let atlas = null;
let zoomIndex = 0;

function renderZoom(direction = 0) {
  const levels = atlas.zoom_levels;
  const level = levels[zoomIndex];
  const ring = $("#zoom-ring");
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const apply = () => {
    ring.style.setProperty("--ring", level.color);
    $("#zoom-emoji").textContent = level.emoji;
    $("#zoom-level-num").textContent = level.order;
    $("#zoom-level-total").textContent = levels.length;
    $("#zoom-title").textContent = level.title;
    $("#zoom-size").textContent = level.size_label;
    $("#zoom-light").textContent = level.light_crossing;
    $("#zoom-contains").textContent = level.contains;
    $("#zoom-analogy").textContent = level.analogy;
    $("#zoom-fact").textContent = level.fun_fact;
    const prev = levels[zoomIndex - 1];
    $("#zoom-prev").hidden = !prev;
    if (prev) $("#zoom-prev-label").textContent = `${prev.title} is in here — far too small to see!`;
    $("#zoom-in").disabled = zoomIndex === 0;
    $("#zoom-out").disabled = zoomIndex === levels.length - 1;
    $("#zoom-steps").replaceChildren(...levels.map((l, i) => h("li", {
      class: i === zoomIndex ? "current" : i < zoomIndex ? "done" : "",
      title: l.title,
    })));
    renderAddress();
  };

  if (!direction || reduce) { apply(); return; }
  ring.classList.add(direction > 0 ? "leaving" : "entering");
  setTimeout(() => {
    apply();
    ring.classList.remove("leaving", "entering");
    ring.classList.add(direction > 0 ? "entering" : "leaving");
    void ring.offsetWidth;
    ring.classList.remove("leaving", "entering");
  }, 380);
}

function renderAddress() {
  const levels = atlas.zoom_levels;
  let name = "";
  try { name = localStorage.getItem(`${STORE_KEY}:name`) || ""; } catch { /* ignore */ }
  const items = [h("li", { "data-n": "✉️", text: name.trim() || "Me" })];
  levels.forEach((level, i) => {
    const unlocked = i <= Math.max(zoomIndex, progress.zoomMax - 1);
    items.push(h("li", { "data-n": `${i + 1}.`, class: unlocked ? "" : "locked", text: unlocked ? level.address_line : "? ? ?" }));
  });
  $("#address-lines").replaceChildren(...items);
  $("#address-hint").textContent = progress.zoomMax >= levels.length
    ? "That's your whole cosmic address — from your home to the edge of everything we can see!"
    : "Zoom out to fill in more of your address!";
}

function zoom(step) {
  const next = zoomIndex + step;
  if (next < 0 || next >= atlas.zoom_levels.length) return;
  zoomIndex = next;
  if (zoomIndex + 1 > progress.zoomMax) {
    progress.zoomMax = zoomIndex + 1;
    saveProgress();
    addXp(5, "new zoom level");
    if (progress.zoomMax === atlas.zoom_levels.length) award("address");
  }
  renderZoom(step);
}

function initZoom() {
  $("#zoom-out").addEventListener("click", () => zoom(1));
  $("#zoom-in").addEventListener("click", () => zoom(-1));
  $("#zoom-stage").addEventListener("click", () => zoom(1));
  const input = $("#address-name");
  try { input.value = localStorage.getItem(`${STORE_KEY}:name`) || ""; } catch { /* ignore */ }
  input.addEventListener("input", () => {
    try { localStorage.setItem(`${STORE_KEY}:name`, input.value.slice(0, 30)); } catch { /* ignore */ }
    const first = $("#address-lines li");
    if (first) first.textContent = input.value.trim() || "Me";
  });
  renderZoom();
}

// ---------------------------------------------------------------------------
// Worlds
// ---------------------------------------------------------------------------
const KIND_LABELS = {
  planet: "Planets", dwarf_planet: "Dwarf planets", moon: "Moons", star: "Stars",
  galaxy: "Galaxies", nebula: "Nebulas", black_hole: "Black holes", spacecraft: "Spacecraft",
};
let worldFilter = "all";

function renderWorlds() {
  const filters = ["all", ...new Set(atlas.objects.map((o) => o.kind))];
  $("#world-filters").replaceChildren(...filters.map((kind) => h("button", {
    class: "chip", type: "button", "aria-pressed": String(kind === worldFilter),
    text: kind === "all" ? "Everything" : KIND_LABELS[kind] || kind,
    onclick: () => { worldFilter = kind; renderWorlds(); },
  })));
  const shown = atlas.objects.filter((o) => worldFilter === "all" || o.kind === worldFilter);
  $("#world-grid").replaceChildren(...shown.map((o) => {
    const card = h("button", { class: "world", type: "button", onclick: () => openWorld(o) },
      h("span", { class: "em", "aria-hidden": "true", text: o.emoji }),
      h("span", { class: "nm", text: o.name }),
      h("span", { class: "tg", text: o.tagline }),
      progress.seen.includes(o.slug) ? h("span", { class: "seen", text: "✓ Visited" }) : null,
    );
    card.style.setProperty("--c", o.color);
    return card;
  }));
}

function stat(label, value) {
  return value === null || value === undefined ? null : h("div", {}, h("dt", { text: label }), h("dd", { text: value }));
}

function openWorld(o) {
  $("#world-emoji").textContent = o.emoji;
  $("#world-kind").textContent = (KIND_LABELS[o.kind] || o.kind).replace(/s$/, "");
  $("#world-name").textContent = o.name;
  $("#world-tagline").textContent = o.tagline;
  const across = o.earths_across >= 1 ? `${fmt(o.earths_across)} Earths` : `${fmt(o.earths_across * 100, 2)}% of Earth`;
  $("#world-stats").replaceChildren(...[
    stat(o.distance_varies ? "Distance (at closest)" : "Distance from Earth", o.distance_label),
    stat("Width", o.diameter_label),
    stat("Width in Earths", across),
    stat("Gravity", o.surface_gravity_g !== null ? `${o.surface_gravity_g}× Earth's` : null),
    stat("One day", o.day_length_hours !== null ? (o.day_length_hours >= 48 ? `${fmt(o.day_length_hours / 24)} Earth days` : `${fmt(o.day_length_hours)} hours`) : null),
    stat("One year", o.orbital_period_days !== null ? (o.orbital_period_days >= 730 ? `${fmt(o.orbital_period_days / 365.25)} Earth years` : `${fmt(o.orbital_period_days)} days`) : null),
    stat("Known moons", o.moons !== null ? (o.moons > 10 ? `at least ${o.moons}` : String(o.moons)) : null),
  ].filter(Boolean));
  $("#world-light").textContent = o.light.message;
  $("#world-facts").replaceChildren(...o.fun_facts.map((f) => h("li", { text: f })));
  $("#world-extra").replaceChildren();

  const travel = $("#world-travel");
  travel.hidden = o.distance_km === 0;
  travel.onclick = async () => {
    try {
      const t = await api(`travel/${encodeURIComponent(o.slug)}`);
      $("#world-extra").replaceChildren(
        h("h3", { text: `🚀 Trip to ${t.destination} (${t.distance_label})` }),
        h("ul", { class: "list" }, t.legs.map((leg) => h("li", {}, h("span", { text: `${leg.emoji} ${leg.mode}` }), h("strong", { text: leg.label })))),
      );
    } catch (err) { showExtraError(err); }
  };

  const select = $("#world-compare");
  select.replaceChildren(h("option", { value: "", text: "— pick —" }),
    ...atlas.objects.filter((x) => x.slug !== o.slug).map((x) => h("option", { value: x.slug, text: x.name })));
  select.onchange = async () => {
    if (!select.value) return;
    try {
      const c = await api(`compare?a=${encodeURIComponent(o.slug)}&b=${encodeURIComponent(select.value)}`);
      $("#world-extra").replaceChildren(h("p", { class: "callout fact", text: `📏 ${c.summary}` }));
    } catch (err) { showExtraError(err); }
  };

  $("#world-dialog").showModal();
  if (!progress.seen.includes(o.slug)) {
    progress.seen.push(o.slug);
    saveProgress();
    addXp(3, `visited ${o.name}`);
    if (progress.seen.length >= 8) award("hopper");
    renderWorlds();
  }
}

function showExtraError(err) {
  $("#world-extra").replaceChildren(h("p", { class: "hint", text: `Hmm: ${err.message}` }));
}

// ---------------------------------------------------------------------------
// Light Time Machine
// ---------------------------------------------------------------------------
const MAX_LOG = Math.log10(13.8e9);
let timeDebounce = null;

function sliderToLy(value) { return 10 ** ((value / 1000) * MAX_LOG); }
function lyToSlider(ly) { return Math.round((Math.log10(Math.max(1, ly)) / MAX_LOG) * 1000); }
function lyLabel(ly) { return `${fmt(ly, ly < 10 ? 1 : 0)} light-year${Math.abs(ly - 1) < 0.05 ? "" : "s"}`; }

function initTime() {
  const slider = $("#time-slider");
  const update = () => {
    const ly = sliderToLy(+slider.value);
    $("#time-distance").textContent = lyLabel(ly);
    clearTimeout(timeDebounce);
    timeDebounce = setTimeout(async () => {
      try {
        const r = await api(`time-machine?light_years=${ly}`);
        $("#time-message").textContent = r.message;
        if (ly >= 1e9) award("time");
      } catch (err) { $("#time-message").textContent = err.message; }
    }, 150);
  };
  slider.addEventListener("input", update);
  slider.setAttribute("aria-valuetext", "1 light-year");
  slider.addEventListener("change", () => slider.setAttribute("aria-valuetext", $("#time-distance").textContent));

  const presets = atlas.objects.filter((o) => o.distance_km >= 0.5 * LY_KM);
  $("#time-presets").replaceChildren(...presets.map((o) => h("button", {
    class: "chip", type: "button", text: `${o.emoji} ${o.name}`,
    onclick: () => {
      const ly = o.distance_km / LY_KM;
      slider.value = lyToSlider(ly);
      $("#time-distance").textContent = `${o.name}: ${o.distance_label}`;
      $("#time-message").textContent = o.light.message;
      if (ly >= 1e9) award("time");
      addXp(o.slug === "andromeda" ? 2 : 1);
    },
  })));
  update();
}

// ---------------------------------------------------------------------------
// Space Gym
// ---------------------------------------------------------------------------
function initGym() {
  const weightForm = $("#weight-form");
  const ageForm = $("#age-form");

  weightForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const w = +$("#weight-input").value;
    const unit = weightForm.querySelector("input[name=unit]:checked").value;
    try {
      const rows = await api(`weight?earth_weight=${w}`);
      const max = Math.max(...rows.map((r) => r.weight));
      $("#weight-results").replaceChildren(...rows.map((r) => {
        const fill = h("span");
        fill.style.width = "0";
        fill.style.background = atlas.objects.find((o) => o.slug === r.slug)?.color || "";
        requestAnimationFrame(() => { fill.style.width = `${Math.max(1.5, (r.weight / max) * 100)}%`; });
        return h("li", {},
          h("span", { text: `${r.emoji} ${r.name}` }),
          h("span", { class: "bar" }, fill),
          h("span", {}, h("strong", { text: `${r.weight} ${unit}` }), h("span", { class: "sub", text: ` · jump ${r.jump_height_m} m` })),
        );
      }));
      award("gym");
    } catch (err) { $("#weight-results").replaceChildren(h("li", { text: err.message })); }
  });

  ageForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const rows = await api(`age?earth_years=${+$("#age-input").value}`);
      $("#age-results").replaceChildren(...rows.map((r) => h("li", {},
        h("span", { text: `${r.emoji} ${r.name}` }),
        h("span", {}, h("strong", { text: `${r.age} years old` }),
          h("span", { class: "sub", text: r.days_to_next_birthday === 0 ? " · birthday today! 🎂" : ` · next birthday in ${r.days_to_next_birthday.toLocaleString()} days` })),
      )));
      addXp(progress.badges.includes("gym") ? 0 : 2);
    } catch (err) { $("#age-results").replaceChildren(h("li", { text: err.message })); }
  });

  weightForm.requestSubmit();
  ageForm.requestSubmit();
}

// ---------------------------------------------------------------------------
// Scale Walk
// ---------------------------------------------------------------------------
const TRACK_PX = 3600;

function initScale() {
  const form = $("#scale-form");
  const wrap = $("#track-wrap");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const sunCm = +$("#scale-input").value;
    try {
      const model = await api(`scale-model?sun_diameter_cm=${sunCm}`);
      drawTrack(model);
      $("#scale-star").textContent = `🌟 ${model.nearest_star_message}`;
      $("#scale-table tbody").replaceChildren(...model.items.map((i) => h("tr", {},
        h("td", { text: `${i.emoji} ${i.name}` }),
        h("td", { text: `${i.size_cm < 1 ? `${+(i.size_cm * 10).toFixed(1)} mm` : `${+i.size_cm.toFixed(1)} cm`} — like ${i.looks_like}` }),
        h("td", { text: i.distance_m >= 1000 ? `${+(i.distance_m / 1000).toFixed(2)} km` : `${fmt(i.distance_m)} m` }),
        h("td", { text: i.steps.toLocaleString() }),
      )));
    } catch (err) { $("#scale-star").textContent = err.message; }
  });

  wrap.addEventListener("scroll", () => {
    if (wrap.scrollLeft + wrap.clientWidth >= wrap.scrollWidth - 40) award("walker");
  }, { passive: true });

  form.requestSubmit();
}

function drawTrack(model) {
  const track = $("#track");
  const maxM = Math.max(...model.items.map((i) => i.distance_m));
  const pxPerM = TRACK_PX / maxM;
  track.style.width = `${TRACK_PX + 160}px`;
  const sun = model.items.find((i) => i.slug === "sun");
  const sunPx = 46;
  const nodes = [];

  // Distance ticks: pick a round step giving ~15 ticks.
  const steps = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000];
  const step = steps.find((s) => maxM / s <= 16) || 10000;
  for (let m = 0; m <= maxM; m += step) {
    const tick = h("span", { class: "tick", text: m >= 1000 ? `${m / 1000} km` : `${m} m` });
    tick.style.left = `${60 + m * pxPerM}px`;
    nodes.push(tick);
  }

  model.items.forEach((i, idx) => {
    const x = 60 + i.distance_m * pxPerM;
    const size = i.slug === "sun" ? sunPx : Math.max(5, sunPx * (i.size_cm / sun.size_cm) * 8);
    const body = h("span", { class: "body", title: i.name });
    Object.assign(body.style, {
      left: `${x}px`, width: `${size}px`, height: `${size}px`,
      background: `radial-gradient(circle at 35% 35%, #fff8, ${i.color})`,
      boxShadow: i.slug === "sun" ? "0 0 30px #f59e0b" : "none",
    });
    const tag = h("span", { class: "tag", text: `${i.emoji} ${i.name}` });
    tag.style.left = `${x}px`;
    tag.style.top = idx % 2 ? "auto" : "12px";
    if (idx % 2) tag.style.bottom = "22px";
    nodes.push(body, tag);
  });
  track.replaceChildren(...nodes);
}

// ---------------------------------------------------------------------------
// Tonight
// ---------------------------------------------------------------------------
const SKY_MISSIONS = [
  { id: "moon", title: "Find the Moon", sub: "Check the phase on the left. Is it where you expected?" },
  { id: "dipper", title: "Spot the Big Dipper or Orion", sub: "Northern Hemisphere: the Big Dipper's 'pan'. Anywhere in winter evenings: Orion's three-star belt." },
  { id: "planet", title: "See a planet", sub: "Planets shine steadily — stars twinkle. Venus and Jupiter are the brightest." },
  { id: "station", title: "Watch the space station fly over", sub: "With a grown-up, look up the next pass for your town. It looks like a bright, silent, moving star." },
  { id: "dark", title: "Count stars in a fist-sized patch", sub: "Try again from somewhere darker. Light pollution hides most stars!" },
  { id: "diary", title: "Start a Moon diary", sub: "Draw the Moon every clear night for two weeks. Real astronomers keep logs like this." },
];

async function initTonight() {
  try {
    const m = await api("moon");
    $("#moon-emoji").textContent = m.emoji;
    $("#moon-name").textContent = m.name;
    $("#moon-detail").textContent = `${Math.round(m.illumination * 100)}% of the side facing us is lit · ${m.age_days} days into its cycle`;
    $("#moon-tip").textContent = m.tip;
  } catch (err) { $("#moon-name").textContent = err.message; }

  $("#sky-missions").replaceChildren(...SKY_MISSIONS.map((mission) => {
    const box = h("input", { type: "checkbox", checked: progress.missions.includes(mission.id) });
    box.addEventListener("change", () => {
      if (box.checked && !progress.missions.includes(mission.id)) {
        progress.missions.push(mission.id);
        saveProgress();
        addXp(10, "sky mission complete");
        if (progress.missions.length >= 3) award("stargazer");
      } else if (!box.checked) {
        progress.missions = progress.missions.filter((id) => id !== mission.id);
        saveProgress();
      }
    });
    return h("li", {}, h("label", {}, box, h("span", {}, h("strong", { text: mission.title }), h("span", { class: "sub", text: mission.sub }))));
  }));
}

// ---------------------------------------------------------------------------
// Quiz
// ---------------------------------------------------------------------------
async function startQuiz() {
  const body = $("#quiz-body");
  body.replaceChildren(h("p", { class: "hint", text: "Loading questions…" }));
  let questions;
  try {
    questions = await api(`quiz?count=5&seed=${Math.floor(Math.random() * 1e9)}`);
  } catch (err) {
    body.replaceChildren(h("p", { text: err.message }));
    return;
  }
  let index = 0;
  let score = 0;

  const ask = () => {
    const q = questions[index];
    const feedback = h("div", { class: "quiz-feedback", "aria-live": "polite" });
    const buttons = q.choices.map((choice) => h("button", {
      class: "btn", type: "button", text: choice,
      onclick: async (e) => {
        buttons.forEach((b) => { b.disabled = true; });
        let result;
        try {
          result = await api("quiz/answer", { method: "POST", body: JSON.stringify({ question_id: q.id, choice }) });
        } catch (err) {
          feedback.replaceChildren(h("p", { text: err.message }));
          return;
        }
        buttons.forEach((b) => { if (b.textContent === result.answer) b.classList.add("right"); });
        if (!result.correct) e.currentTarget?.classList.add("wrong");
        if (result.correct) {
          score += 1;
          if (!progress.correct.includes(q.id)) {
            progress.correct.push(q.id);
            saveProgress();
            addXp(result.points);
          }
        }
        const last = index === questions.length - 1;
        feedback.replaceChildren(
          h("p", { class: "verdict", text: result.correct ? "✅ Correct!" : "❌ Not quite!" }),
          h("p", { text: result.explanation }),
          h("button", { class: "btn primary", type: "button", text: last ? "See my score" : "Next question →", onclick: () => { index += 1; last ? finish() : ask(); } }),
        );
        feedback.querySelector("button").focus();
      },
    }));
    body.replaceChildren(
      h("p", { class: "quiz-progress", text: `Question ${index + 1} of ${questions.length} · ${q.topic}` }),
      h("p", { class: "quiz-prompt", text: q.prompt }),
      h("div", { class: "quiz-choices" }, buttons),
      feedback,
    );
    buttons[0].focus();
  };

  const finish = () => {
    const perfect = score === questions.length;
    if (perfect) award("ace");
    body.replaceChildren(
      h("p", { class: "score", text: `${score} / ${questions.length}` }),
      h("p", { text: perfect ? "Perfect score — you're a real space expert! 🌟" : score >= 3 ? "Great job! Every wrong answer is something new you learned." : "Nice try! Scientists get things wrong all the time — that's how they learn." }),
      h("p", { class: "hint", text: `You've answered ${progress.correct.length} different questions correctly so far.` }),
      h("button", { class: "btn primary", type: "button", text: "Play again", onclick: startQuiz }),
    );
  };

  ask();
}

// ---------------------------------------------------------------------------
// Careers
// ---------------------------------------------------------------------------
function renderCareers() {
  $("#career-grid").replaceChildren(...atlas.careers.map((c) => {
    const chosen = progress.dream === c.slug;
    return h("article", { class: "card career" },
      h("span", { class: "em", "aria-hidden": "true", text: c.emoji }),
      h("h2", { text: c.title }),
      h("p", { text: c.what_they_do }),
      h("div", { class: "subjects", "aria-label": "Helpful school subjects" }, c.helpful_subjects.map((s) => h("span", { text: s }))),
      h("p", { class: "callout fact" }, h("strong", { text: "Try this: " }), c.try_this),
      h("button", {
        class: chosen ? "btn primary small" : "btn small", type: "button", "aria-pressed": String(chosen),
        text: chosen ? "⭐ My dream job!" : "☆ This could be me",
        onclick: () => { progress.dream = chosen ? null : c.slug; saveProgress(); if (!chosen) award("dream"); renderCareers(); },
      }),
    );
  }));
}

// ---------------------------------------------------------------------------
// Ask Nova
// ---------------------------------------------------------------------------
const NOVA_SUGGESTIONS = [
  "How much would I weigh on Mars if I weigh 30 kg?",
  "Is Jupiter bigger than Earth?",
  "How long ago did the light from Andromeda leave?",
  "How long would it take to fly to the Moon?",
  "What is my cosmic address?",
  "Tell me about Saturn",
];
const TOOL_WORDS = {
  lookup_object: "checked the star charts",
  light_time_machine: "used the light time machine",
  weight_on_world: "did the gravity maths",
  compare_sizes: "measured both sizes",
  travel_time: "planned the trip",
  cosmic_address: "read your cosmic address",
};

function getPass() {
  try { return sessionStorage.getItem(`${STORE_KEY}:pass`) || ""; } catch { return ""; }
}

function initNova() {
  const passInput = $("#pass-input");
  passInput.value = getPass();
  const updateStatus = () => { $("#pass-status").textContent = passInput.value ? "✓ ready" : "(ask a grown-up)"; };
  passInput.addEventListener("input", () => {
    // sessionStorage: forgotten when the browser tab closes.
    try { sessionStorage.setItem(`${STORE_KEY}:pass`, passInput.value); } catch { /* ignore */ }
    updateStatus();
  });
  updateStatus();
  if (!passInput.value) $("#pass-details").open = true;

  const chat = $("#chat");
  chat.append(h("li", { class: "nova", text: "Hi! I'm Nova. Ask me anything about planets, stars or galaxies — I'll look up the real numbers for you." }));

  const ask = async (question) => {
    chat.append(h("li", { class: "me", text: question }));
    const thinking = h("li", { class: "nova", text: "Checking my star charts…" });
    chat.append(thinking);
    chat.scrollTop = chat.scrollHeight;
    try {
      const r = await api("/api/v1/agent/guide", {
        method: "POST",
        headers: { "X-API-Key": passInput.value },
        body: JSON.stringify({ message: question }),
      });
      thinking.textContent = r.reply; // textContent: LLM output is never parsed as HTML
      const used = r.trace.filter((t) => t.ok).map((t) => TOOL_WORDS[t.tool] || t.tool);
      if (used.length) thinking.append(h("span", { class: "tools", text: `Nova ${[...new Set(used)].join(" and ")}.` }));
      progress.asks += 1;
      saveProgress();
      award("curious");
      if (progress.asks <= 5) addXp(5);
    } catch (err) {
      thinking.remove();
      const msg = err.status === 401
        ? "Nova needs the Explorer Pass first — ask the grown-up who runs this site, then type it in above."
        : err.status === 429 ? "Whoa, lots of questions! Give Nova a few seconds to catch her breath." : `Nova couldn't answer: ${err.message}`;
      chat.append(h("li", { class: "err", text: msg }));
      if (err.status === 401) { $("#pass-details").open = true; passInput.focus(); }
    }
    chat.scrollTop = chat.scrollHeight;
  };

  $("#nova-suggestions").replaceChildren(...NOVA_SUGGESTIONS.map((q) => h("button", { class: "chip", type: "button", text: q, onclick: () => ask(q) })));
  $("#chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("#chat-input");
    const q = input.value.trim();
    if (!q) return;
    input.value = "";
    ask(q);
  });
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
async function boot() {
  initStars();
  renderRank();
  $("#rank-button").addEventListener("click", openBadges);
  $("#reset-progress").addEventListener("click", () => {
    if (!confirm("Start over? This clears your XP and badges on this device.")) return;
    try { localStorage.removeItem(STORE_KEY); } catch { /* ignore */ }
    location.reload();
  });

  try {
    atlas = await api("atlas");
  } catch (err) {
    $("#loading").hidden = true;
    const banner = $("#load-error");
    banner.textContent = `Couldn't reach the telescope (${err.message}). Is the server running?`;
    banner.hidden = false;
    return;
  }
  $("#loading").hidden = true;

  Object.assign(loaders, {
    zoom: initZoom,
    worlds: renderWorlds,
    time: initTime,
    gym: initGym,
    scale: initScale,
    tonight: initTonight,
    quiz: () => $("#quiz-start").addEventListener("click", startQuiz),
    careers: renderCareers,
    nova: initNova,
  });
  initTabs();
  showTab(location.hash.slice(1) || "zoom");
}

document.addEventListener("DOMContentLoaded", boot);
