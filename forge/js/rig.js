// =============================================================================
// rig.js — a procedural, skinned, anatomically-muscled human figure.
// -----------------------------------------------------------------------------
// No model files. The body is assembled from lathe-turned segments and ~70
// individually shaped muscle bellies, then merged into skinned meshes driven
// by one skeleton. Vertices near each joint are blended between neighbouring
// bones, so elbows, knees, hips and shoulders bend like flesh instead of
// pivoting like a robot's ball joints. Every muscle group has its own
// material, so the movers of an exercise can glow, and some bellies
// "contract" (morph target) as the joint they cross flexes.
//
// Joint conventions (degrees, Euler order XYZ, character faces +Z):
//   root   x+ = pitch forward (head toward +Z)
//   spine/chest/neck x+ = flexion (round forward), x- = extension
//   shoulder x- = flexion (arm forward/up), x+ = extension (arm back)
//            z+ = abduction for the LEFT arm (right arm is mirrored)
//            y- = horizontal adduction (left arm sweeps toward the front)
//   elbow  x- = flexion        hip  x- = flexion (thigh forward)
//   knee   x+ = flexion        ankle x+ = plantar-flexion (point toes)
// "Sym" keys (shoulder, elbow, hip, knee, ankle, wrist) apply to both sides,
// mirroring y and z for the right side. L/R suffixed keys override.
// =============================================================================
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

export const DEG = Math.PI / 180;
const V2 = THREE.Vector2;
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

export const SIDE_JOINTS = ['shoulder', 'elbow', 'wrist', 'hip', 'knee', 'ankle'];
export const CENTER_JOINTS = ['root', 'spine', 'chest', 'neck', 'head'];
export const ALL_JOINTS = [
  ...CENTER_JOINTS,
  ...SIDE_JOINTS.flatMap((j) => [j + 'L', j + 'R']),
];

// Resting "neutral" angles so arms hang naturally beside the torso.
const REST = {
  shoulderL: [0, 0, 7], shoulderR: [0, 0, -7],
  elbowL: [-6, 0, 0], elbowR: [-6, 0, 0],
};

// Skin-weight blending per bone: the bone's own axis (local end point), and
// how far (as a fraction of that axis) vertices blend into parent / child.
const BLEND = {
  root: { seg: [0, 0.08, 0], child: ['spine', 0.35] },
  spine: { seg: [0, 0.2, 0], parent: ['root', 0.3], child: ['chest', 0.3] },
  chest: { seg: [0, 0.305, 0], parent: ['spine', 0.22], child: ['neck', 0.08] },
  neck: { seg: [0, 0.09, 0], parent: ['chest', 0.45], child: ['head', 0.3] },
  head: { seg: [0, 0.2, 0], parent: ['neck', 0.1] },
  shoulder: { seg: [0, -0.29, 0], parent: ['chest', 0.14, 0.42], child: ['elbow', 0.13] },
  elbow: { seg: [0, -0.26, 0], parent: ['shoulder', 0.13], child: ['wrist', 0.12] },
  wrist: { seg: [0, -0.1, 0], parent: ['elbow', 0.2] },
  hip: { seg: [0, -0.44, 0], parent: ['root', 0.14, 0.5], child: ['knee', 0.11] },
  knee: { seg: [0, -0.42, 0], parent: ['hip', 0.11], child: ['ankle', 0.09] },
  ankle: { seg: [0, -0.07, 0], parent: ['knee', 0.35] },
};

/** Tapered limb hanging from y=0 to y=-len with a gaussian belly. */
function limbGeo(len, r0, r1, belly = 0, peak = 0.35, radial = 28) {
  const p = [];
  const cap = 7;
  for (let i = 0; i <= cap; i++) {
    const a = (Math.PI / 2) * (i / cap);
    p.push(new V2(Math.sin(a) * r0, Math.cos(a) * r0 * 0.55));
  }
  const N = 22;
  for (let i = 1; i < N; i++) {
    const t = i / N;
    const b = belly * Math.exp(-Math.pow((t - peak) / 0.26, 2));
    p.push(new V2(lerp(r0, r1, t) + b, -t * len));
  }
  for (let i = 0; i <= cap; i++) {
    const a = (Math.PI / 2) * (i / cap);
    p.push(new V2(Math.cos(a) * r1, -len - Math.sin(a) * r1 * 0.55));
  }
  p.reverse(); // lathe wants ascending y for outward normals
  const g = new THREE.LatheGeometry(p, radial);
  g.computeVertexNormals();
  return g;
}

/** Lathe from a [radius, y] profile given bottom -> top. */
function torsoGeo(profile, radial = 40) {
  const g = new THREE.LatheGeometry(profile.map(([r, y]) => new V2(r, y)), radial);
  g.computeVertexNormals();
  return g;
}

const SPHERE = new THREE.SphereGeometry(1, 30, 22);
const SPHERE_LO = new THREE.SphereGeometry(1, 18, 12);



// Muscle catalogue, origin -> insertion (real anatomy), LEFT side, mirrored.
// [group, originBone, originPoint, insertionBone, insertionPoint, width, depth, opts]
// Points are in the named bone's local space. Each belly is generated along
// the origin->insertion line: tendon at both ends, a flat underside sunk into
// the deep layer, and skin weights that slide from the origin bone, through
// the bone it lies on (`on`), to the insertion bone, so muscles stretch
// across the joints they cross.
// opts: on, peak (belly position 0..1), tA/tB (tendon length fraction),
//       bow (outward curvature), sink, under, bands (tendinous lines), bulge
const MUSCLES = [
  // --- pectoralis major: three slips fanning from sternum/clavicle to humerus
  ['chest', 'chest', [0.035, 0.292, 0.075], 'shoulder', [0.004, -0.075, 0.03], 0.042, 0.024, { peak: 0.45, tB: 0.22, bow: 0.012, layer: 1 }],
  ['chest', 'chest', [0.012, 0.2, 0.108], 'shoulder', [0.0, -0.08, 0.028], 0.068, 0.032, { peak: 0.42, tB: 0.2, bow: 0.012, layer: 1 }],
  ['chest', 'chest', [0.045, 0.1, 0.104], 'shoulder', [-0.006, -0.085, 0.022], 0.05, 0.022, { peak: 0.4, tB: 0.25, bow: 0.008, layer: 1 }],
  // --- deltoid: three heads converging on the deltoid tuberosity
  ['delts', 'chest', [0.135, 0.296, 0.05], 'shoulder', [0.012, -0.135, 0.012], 0.04, 0.032, { on: 'shoulder', bow: 0.03, peak: 0.4, tA: 0.06, tB: 0.18, layer: 1 }],
  ['delts', 'chest', [0.198, 0.302, -0.008], 'shoulder', [0.016, -0.135, 0.0], 0.044, 0.036, { on: 'shoulder', bow: 0.036, peak: 0.4, tA: 0.06, tB: 0.18, layer: 1 }],
  ['delts', 'chest', [0.15, 0.292, -0.075], 'shoulder', [0.012, -0.135, -0.012], 0.04, 0.03, { on: 'shoulder', bow: 0.03, peak: 0.4, tA: 0.06, tB: 0.18, layer: 1 }],
  // --- arm
  ['biceps', 'shoulder', [0.0, -0.01, 0.036], 'elbow', [0.0, -0.035, 0.016], 0.034, 0.036, { peak: 0.58, tA: 0.16, tB: 0.16, bow: 0.012, bulge: 0.016, zB: 0.18, layer: 1 }],
  ['biceps', 'shoulder', [0.012, -0.15, 0.022], 'elbow', [0.0, -0.03, 0.012], 0.03, 0.018, { peak: 0.55, tB: 0.2 }], // brachialis
  ['triceps', 'shoulder', [0.024, -0.04, -0.03], 'elbow', [0.0, 0.015, -0.03], 0.034, 0.03, { peak: 0.42, tB: 0.28, bow: 0.006 }],
  ['triceps', 'shoulder', [-0.012, 0.0, -0.036], 'elbow', [0.0, 0.015, -0.03], 0.032, 0.032, { peak: 0.42, tB: 0.3, bow: 0.008 }],
  ['forearms', 'shoulder', [0.024, -0.19, 0.016], 'wrist', [0.012, 0.02, 0.004], 0.028, 0.028, { on: 'elbow', peak: 0.3, tA: 0.06, tB: 0.42, zA: 0.12, zB: 0.1, layer: 1 }],
  ['forearms', 'shoulder', [-0.03, -0.285, 0.004], 'wrist', [-0.008, 0.01, 0.012], 0.032, 0.026, { on: 'elbow', peak: 0.26, tA: 0.06, tB: 0.42, zA: 0.1, zB: 0.1 }],
  ['forearms', 'shoulder', [0.034, -0.285, -0.008], 'wrist', [0.008, 0.01, -0.012], 0.03, 0.024, { on: 'elbow', peak: 0.26, tA: 0.06, tB: 0.42, zA: 0.1, zB: 0.1 }],
  // --- neck & upper back
  ['traps', 'head', [0.012, 0.05, -0.075], 'chest', [0.17, 0.296, -0.03], 0.034, 0.018, { on: 'neck', peak: 0.55, tA: 0.12, tB: 0.12, zA: 0.2, zB: 0.45, layer: 1 }],
  ['traps', 'chest', [0.0, 0.29, -0.1], 'chest', [0.165, 0.275, -0.06], 0.05, 0.014, { tA: 0.18, tB: 0.1, layer: 1 }],
  ['traps', 'chest', [0.0, 0.08, -0.112], 'chest', [0.115, 0.245, -0.092], 0.044, 0.012, { tA: 0.2, tB: 0.12, layer: 1 }],
  ['traps', 'head', [0.055, 0.04, -0.02], 'chest', [0.02, 0.3, 0.075], 0.02, 0.02, { on: 'neck', peak: 0.5, tA: 0.1, tB: 0.18, zA: 0.2, zB: 0.3 }], // sternocleidomastoid
  ['upperback', 'chest', [0.07, 0.17, -0.118], 'shoulder', [0.0, -0.005, -0.04], 0.058, 0.018, { peak: 0.4, tB: 0.22 }], // infraspinatus
  ['upperback', 'chest', [0.115, 0.12, -0.1], 'shoulder', [-0.014, -0.06, -0.012], 0.03, 0.022, { peak: 0.45, tB: 0.2 }], // teres major
  // --- latissimus dorsi: wide sheet sweeping up to the humerus (the V-taper)
  ['lats', 'chest', [0.035, 0.02, -0.112], 'shoulder', [-0.016, -0.07, 0.002], 0.066, 0.022, { peak: 0.45, tB: 0.2, bow: 0.012, layer: 1 }],
  ['lats', 'chest', [0.1, -0.03, -0.085], 'shoulder', [-0.016, -0.072, 0.004], 0.064, 0.026, { peak: 0.45, tB: 0.2, bow: 0.016, layer: 1 }],
  ['lats', 'spine', [0.04, 0.03, -0.098], 'shoulder', [-0.016, -0.075, 0.006], 0.058, 0.02, { on: 'chest', peak: 0.5, tA: 0.22, tB: 0.2, zA: 0.3, layer: 1 }],
  // --- core
  ['abs', 'root', [0.026, -0.085, 0.084], 'chest', [0.044, 0.1, 0.113], 0.04, 0.018, { on: 'spine', peak: 0.55, tA: 0.06, tB: 0.04, sink: 0.005, under: 0.5, bands: [0.46, 0.64, 0.82], zA: 0.25, zB: 0.25 }],
  ['obliques', 'chest', [0.128, 0.03, 0.05], 'root', [0.085, 0.06, 0.07], 0.05, 0.024, { on: 'spine', peak: 0.45, tA: 0.06, tB: 0.18, zA: 0.25, zB: 0.25, layer: 1 }],
  ['obliques', 'chest', [0.14, 0.03, 0.05], 'chest', [0.12, 0.09, -0.03], 0.017, 0.014, { tA: 0.05, tB: 0.2 }],
  ['obliques', 'chest', [0.145, 0.075, 0.055], 'chest', [0.125, 0.13, -0.03], 0.017, 0.014, { tA: 0.05, tB: 0.2 }],
  ['obliques', 'chest', [0.145, 0.12, 0.06], 'chest', [0.125, 0.17, -0.03], 0.016, 0.013, { tA: 0.05, tB: 0.2 }],
  ['lowerback', 'root', [0.032, -0.03, -0.092], 'chest', [0.03, 0.2, -0.112], 0.03, 0.028, { on: 'spine', peak: 0.3, tA: 0.12, tB: 0.2, zA: 0.3, zB: 0.3 }],
  ['lowerback', 'root', [0.0, -0.02, -0.104], 'spine', [0.0, 0.14, -0.098], 0.075, 0.01, { on: 'spine', fascia: true, center: true, sink: 0.002, zA: 0.3, zB: 0.2, layer: 1 }], // thoracolumbar fascia
  ['abs', 'root', [0.0, -0.08, 0.093], 'chest', [0.0, 0.17, 0.119], 0.007, 0.006, { on: 'spine', fascia: true, center: true, sink: 0, zA: 0.25, zB: 0.25, layer: 1 }], // linea alba
  // --- hips
  ['glutes', 'root', [0.02, 0.01, -0.104], 'hip', [0.035, -0.12, -0.03], 0.088, 0.052, { peak: 0.42, bow: 0.03, tA: 0.06, tB: 0.16, zB: 0.3, layer: 1 }],
  ['glutes', 'root', [0.11, 0.07, -0.04], 'hip', [0.045, 0.0, 0.0], 0.06, 0.03, { peak: 0.4, bow: 0.012, tB: 0.2, zB: 0.3 }],
  ['glutes', 'root', [0.12, 0.03, 0.055], 'knee', [0.04, 0.0, 0.0], 0.034, 0.012, { on: 'hip', peak: 0.1, tA: 0.04, tB: 0.8, zA: 0.12, zB: 0.08, layer: 1 }], // TFL + IT band
  // --- thigh
  ['quads', 'root', [0.09, -0.04, 0.08], 'knee', [0.0, 0.03, 0.06], 0.04, 0.04, { on: 'hip', peak: 0.48, tA: 0.14, tB: 0.18, zA: 0.12, zB: 0.12, layer: 1 }],
  ['quads', 'hip', [0.048, -0.05, 0.0], 'knee', [0.022, 0.05, 0.046], 0.05, 0.046, { peak: 0.45, tB: 0.16, bow: 0.012 }],
  ['quads', 'hip', [-0.028, -0.2, 0.022], 'knee', [-0.016, 0.035, 0.042], 0.04, 0.04, { peak: 0.72, tB: 0.14 }],
  ['adductors', 'root', [0.03, -0.1, 0.035], 'hip', [-0.03, -0.3, -0.01], 0.05, 0.04, { peak: 0.35, tA: 0.1, tB: 0.2 }],
  ['hams', 'root', [0.06, -0.1, -0.065], 'knee', [0.042, -0.04, -0.02], 0.038, 0.04, { on: 'hip', peak: 0.48, tA: 0.12, tB: 0.2, zA: 0.16, zB: 0.12, bulge: 0.01 }],
  ['hams', 'root', [0.045, -0.1, -0.065], 'knee', [-0.042, -0.05, -0.018], 0.042, 0.042, { on: 'hip', peak: 0.55, tA: 0.12, tB: 0.22, zA: 0.16, zB: 0.12, bulge: 0.01 }],
  // --- lower leg
  ['calves', 'hip', [0.034, -0.41, -0.035], 'ankle', [0.0, -0.03, -0.06], 0.038, 0.044, { on: 'knee', peak: 0.28, tA: 0.06, tB: 0.52, zA: 0.1, zB: 0.1, bulge: 0.012, layer: 1 }],
  ['calves', 'hip', [-0.034, -0.42, -0.035], 'ankle', [0.0, -0.03, -0.06], 0.044, 0.05, { on: 'knee', peak: 0.33, tA: 0.06, tB: 0.5, zA: 0.1, zB: 0.1, bulge: 0.012, layer: 1 }],
  ['calves', 'knee', [0.0, -0.08, -0.03], 'ankle', [0.0, -0.02, -0.055], 0.052, 0.03, { peak: 0.5, tA: 0.1, tB: 0.35 }], // soleus
  ['quads', 'knee', [0.0, -0.004, 0.05], 'knee', [0.0, -0.075, 0.04], 0.014, 0.008, { fascia: true, sink: 0.001 }], // patellar tendon
  // --- deep layer (revealed when the superficial muscles are peeled away)
  ['chest', 'chest', [0.06, 0.2, 0.086], 'chest', [0.125, 0.28, 0.04], 0.04, 0.015, { layer: 2, tB: 0.2 }], // pectoralis minor
  ['upperback', 'chest', [0.08, 0.27, -0.08], 'shoulder', [0.01, 0.02, 0.0], 0.022, 0.016, { layer: 2, tB: 0.25 }], // supraspinatus
  ['upperback', 'chest', [0.0, 0.25, -0.106], 'chest', [0.075, 0.16, -0.112], 0.045, 0.012, { layer: 2, tA: 0.15 }], // rhomboids
  ['quads', 'hip', [0.0, -0.1, 0.035], 'knee', [0.0, 0.06, 0.04], 0.045, 0.03, { layer: 2, tB: 0.15 }], // vastus intermedius
  // --- face (écorché head)
  ['face', 'head', [0.075, 0.165, -0.01], 'head', [0.07, 0.07, 0.03], 0.042, 0.012, { peak: 0.3, tA: 0.05, tB: 0.3 }], // temporalis
  ['face', 'head', [0.03, 0.2, 0.055], 'head', [0.03, 0.126, 0.094], 0.032, 0.008, { tA: 0.35, tB: 0.05 }], // frontalis
  ['face', 'head', [0.062, 0.072, 0.06], 'head', [0.056, 0.005, 0.042], 0.024, 0.014, { tA: 0.12 }], // masseter
  ['face', 'head', [0.01, 0.121, 0.099], 'head', [0.056, 0.113, 0.084], 0.012, 0.006, { tA: 0.05, tB: 0.05 }], // orbicularis oculi (upper)
  ['face', 'head', [0.014, 0.091, 0.1], 'head', [0.056, 0.094, 0.084], 0.012, 0.006, { tA: 0.05, tB: 0.05 }], // orbicularis oculi (lower)
  ['face', 'head', [0.062, 0.082, 0.072], 'head', [0.026, 0.042, 0.1], 0.012, 0.008, { tA: 0.1, tB: 0.1 }], // zygomaticus
  ['face', 'head', [0.0, 0.046, 0.112], 'head', [0.03, 0.04, 0.096], 0.012, 0.008, { tA: 0.02, tB: 0.1 }], // orbicularis oris (upper)
  ['face', 'head', [0.0, 0.028, 0.109], 'head', [0.028, 0.035, 0.096], 0.012, 0.008, { tA: 0.02, tB: 0.1 }], // orbicularis oris (lower)
  ['calves', 'knee', [0.032, -0.05, 0.034], 'ankle', [-0.008, -0.03, 0.06], 0.024, 0.026, { peak: 0.3, tA: 0.08, tB: 0.42, zB: 0.12 }], // tibialis anterior
];

export const MUSCLE_GROUPS = [...new Set(MUSCLES.map((m) => m[0]))];

export const MUSCLE_LABEL = {
  chest: 'Chest', delts: 'Delts', biceps: 'Biceps', triceps: 'Triceps',
  forearms: 'Forearms / grip', lats: 'Lats', traps: 'Traps',
  upperback: 'Upper back', abs: 'Abs', obliques: 'Obliques',
  lowerback: 'Spinal erectors', glutes: 'Glutes', quads: 'Quads',
  hams: 'Hamstrings', calves: 'Calves', adductors: 'Adductors', face: 'Face',
};

// Colours for muscle states (shared by setHighlight).
const C_IDLE = new THREE.Color(1, 1, 1);
const C_PRIMARY = new THREE.Color(1.3, 0.72, 0.62);
const C_SECOND = new THREE.Color(1.22, 1.0, 0.72);
const E_PRIMARY = new THREE.Color(0xff2e12);
const E_SECOND = new THREE.Color(0xff8a1f);

let FIBER = null;
/** Procedural striated-muscle texture: fine fibres running along the belly. */
function fiberTextures() {
  if (FIBER) return FIBER;
  const W = 512; const H = 512;
  const c = document.createElement('canvas');
  c.width = W; c.height = H;
  const g = c.getContext('2d');
  g.fillStyle = '#cfcfcf';
  g.fillRect(0, 0, W, H);
  // low-frequency mottling so no two areas read identical
  for (let i = 0; i < 140; i++) {
    const x = Math.random() * W; const y = Math.random() * H; const r = 20 + Math.random() * 70;
    const l = Math.floor(185 + Math.random() * 60);
    const grd = g.createRadialGradient(x, y, 0, x, y, r);
    grd.addColorStop(0, `rgba(${l},${l},${l},0.35)`);
    grd.addColorStop(1, `rgba(${l},${l},${l},0)`);
    g.fillStyle = grd;
    g.fillRect(x - r, y - r, r * 2, r * 2);
  }
  // fascicles: bundles of fine fibres with darker grooves between bundles
  let x = 0;
  while (x < W) {
    const bw = 5 + Math.random() * 9;
    const ph = Math.random() * 6; const amp = 1.5 + Math.random() * 3;
    for (let f = 0; f < bw; f += 0.9) {
      const l = Math.floor(175 + Math.random() * 80);
      g.strokeStyle = `rgb(${l},${l},${l})`;
      g.lineWidth = 0.5 + Math.random();
      g.beginPath();
      for (let y = 0; y <= H; y += 12) g.lineTo(x + f + Math.sin(y / 80 + ph) * amp, y);
      g.stroke();
    }
    g.strokeStyle = 'rgba(70,70,70,0.55)';
    g.lineWidth = 1.2;
    g.beginPath();
    for (let y = 0; y <= H; y += 12) g.lineTo(x + bw + Math.sin(y / 80 + ph) * amp, y);
    g.stroke();
    x += bw + 1.5;
  }
  const map = new THREE.CanvasTexture(c);
  map.colorSpace = THREE.SRGBColorSpace;
  map.wrapS = map.wrapT = THREE.RepeatWrapping;
  map.repeat.set(4, 1);
  map.anisotropy = 4;
  const bump = new THREE.CanvasTexture(c);
  bump.wrapS = bump.wrapT = THREE.RepeatWrapping;
  bump.repeat.set(4, 1);
  FIBER = { map, bump };
  return FIBER;
}

/** Shared material set. One material per muscle group so highlighting is cheap. */
export function createMaterials({ ghost = false } = {}) {
  if (ghost) {
    const g = new THREE.MeshBasicMaterial({
      color: 0x58d6ff, transparent: true, opacity: 0.1, depthWrite: false,
    });
    const mats = { skin: g, hair: g, nail: g, deep: g, tendon: g, eye: g, eyeball: g, iris: g };
    MUSCLE_GROUPS.forEach((k) => (mats[k] = g));
    return mats;
  }
  const { map, bump } = fiberTextures();
  const skin = new THREE.MeshPhysicalMaterial({
    color: 0xa87462, roughness: 0.66, metalness: 0, vertexColors: true,
    sheen: 0.35, sheenRoughness: 0.7, sheenColor: 0xd99a80, specularIntensity: 0.35,
    emissive: 0x000000,
  });
  const hair = new THREE.MeshStandardMaterial({ color: 0x241a16, roughness: 0.85 });
  const nail = skin;
  // Deep muscle layer between the bellies, and pale tendon/fascia at joints.
  const deep = new THREE.MeshPhysicalMaterial({
    color: 0xa9443d, map, bumpMap: bump, bumpScale: 2, roughness: 0.6, vertexColors: true,
    specularIntensity: 0.45, sheen: 0.45, sheenRoughness: 0.5, sheenColor: 0xffb3a8, emissive: 0x000000,
  });
  const tendon = new THREE.MeshPhysicalMaterial({
    color: 0xcdbdb1, roughness: 0.5, vertexColors: true, specularIntensity: 0.45,
    sheen: 0.3, sheenColor: 0xf0d6c4, emissive: 0x000000,
  });
  const eye = new THREE.MeshStandardMaterial({ color: 0x3a2420, roughness: 0.6, vertexColors: true });
  const eyeball = new THREE.MeshPhysicalMaterial({ color: 0xf2ece6, roughness: 0.15, clearcoat: 1, vertexColors: true });
  const iris = new THREE.MeshPhysicalMaterial({ color: 0x3b2a1e, roughness: 0.2, clearcoat: 1, vertexColors: true });
  const mats = { skin, hair, nail, deep, tendon, eye, eyeball, iris };
  MUSCLE_GROUPS.forEach((k) => {
    mats[k] = new THREE.MeshPhysicalMaterial({
      color: C_IDLE.clone(), map, bumpMap: bump, bumpScale: 2.6, vertexColors: true,
      roughness: 0.52, metalness: 0, specularIntensity: 0.55,
      clearcoat: 0.15, clearcoatRoughness: 0.5, // thin moist film, not plastic
      sheen: 0.55, sheenRoughness: 0.5, sheenColor: 0xffc0b8,
      emissive: 0x000000, emissiveIntensity: 1,
    });
  });
  return mats;
}

export class Rig {
  constructor(mats) {
    this.mats = mats;
    this.bones = {};
    this.markers = {};
    this.parts = [];
    this.object = new THREE.Group();
    this.root = new THREE.Bone();
    this.root.name = 'root';
    this.root.position.set(0, 1, 0);
    this.bones.root = this.root;
    this.object.add(this.root);
    this._build();
    this._skin();
  }

  _bone(name, parent, pos) {
    const b = new THREE.Bone();
    b.name = name;
    b.position.set(...pos);
    parent.add(b);
    this.bones[name] = b;
    return b;
  }

  /** Queue a body part (geometry in bone-local space) for skinning. */
  _part(geo, mat, bone, pos = [0, 0, 0], scale = [1, 1, 1], rot = [0, 0, 0], extra = {}) {
    this.parts.push({ geo, mat, bone, pos, scale, rot, ...extra });
  }

  _marker(name, parent, pos) {
    const o = new THREE.Object3D();
    o.position.set(...pos);
    parent.add(o);
    this.markers[name] = o;
    return o;
  }

  _build() {
    const M = this.mats;
    const root = this.root;
    const S = M.skin; const D = M.deep; const T = M.tendon;

    // --- Pelvis -------------------------------------------------------------
    this._part(torsoGeo([[0, -0.13], [0.07, -0.124], [0.118, -0.08], [0.134, -0.02],
      [0.13, 0.04], [0.12, 0.09], [0, 0.11]]), D, root, [0, 0, -0.005], [1, 1, 0.74]);
    this._marker('sacrum', root, [0, -0.02, -0.11]);
    this._marker('gluteL', root, [0.068, -0.05, -0.144]);
    this._marker('gluteR', root, [-0.068, -0.05, -0.144]);
    this._marker('pelvis', root, [0, 0, 0]);

    // --- Lumbar / abdomen ---------------------------------------------------
    const spine = this._bone('spine', root, [0, 0.08, 0]);
    this._part(torsoGeo([[0, -0.04], [0.114, -0.02], [0.112, 0.06], [0.115, 0.14],
      [0.124, 0.2], [0, 0.23]]), D, spine, [0, 0, 0], [1, 1, 0.72]);
    this._marker('lumbar', spine, [0, 0.03, -0.1]);

    // --- Thorax -------------------------------------------------------------
    const chest = this._bone('chest', spine, [0, 0.2, 0]);
    this._part(torsoGeo([[0, -0.02], [0.124, 0.0], [0.136, 0.06], [0.152, 0.13],
      [0.164, 0.2], [0.16, 0.25], [0.14, 0.29], [0.095, 0.318], [0.05, 0.332], [0, 0.338]]),
    D, chest, [0, 0, -0.008], [1, 1, 0.62]);
    // clavicles
    for (const k of [1, -1]) {
      this._part(SPHERE_LO, T, chest, [0.095 * k, 0.288, 0.045], [0.08, 0.01, 0.011], [0, 22 * k, -8 * k]);
    }
    this._marker('upperBack', chest, [0, 0.17, -0.13]);
    this._marker('scapL', chest, [0.05, 0.2, -0.128]);
    this._marker('scapR', chest, [-0.05, 0.2, -0.128]);
    this._marker('sternum', chest, [0, 0.16, 0.12]);
    this._marker('chestMid', chest, [0, 0.14, 0]);

    // --- Neck & head --------------------------------------------------------
    const neck = this._bone('neck', chest, [0, 0.305, -0.005]);
    this._part(limbGeo(0.12, 0.056, 0.052, 0, 0.5), D, neck, [0, 0.11, 0]);
    const head = this._bone('head', neck, [0, 0.09, 0]);
    head.scale.setScalar(1.07);
    this._part(SPHERE, T, head, [0, 0.112, -0.006], [0.091, 0.108, 0.102]); // cranium (galea aponeurotica)
    this._part(SPHERE, D, head, [0, 0.06, 0.035], [0.071, 0.075, 0.078]); // face mass
    this._part(SPHERE_LO, D, head, [0, 0.02, 0.06], [0.05, 0.03, 0.045]); // jaw
    this._part(SPHERE_LO, T, head, [0, 0.012, 0.09], [0.022, 0.02, 0.02]); // chin
    this._part(SPHERE_LO, D, head, [0, 0.122, 0.078], [0.064, 0.014, 0.028]); // brow
    this._part(SPHERE_LO, T, head, [0, 0.086, 0.106], [0.01, 0.022, 0.014], [-14, 0, 0]); // nasal cartilage
    for (const k of [1, -1]) {
      this._part(SPHERE_LO, T, head, [0.089 * k, 0.09, 0.0], [0.012, 0.03, 0.02]); // ears
    }
    for (const k of [1, -1]) {
      this._part(SPHERE_LO, M.eye, head, [0.032 * k, 0.103, 0.086], [0.018, 0.012, 0.012]); // eye sockets
      this._part(SPHERE, M.eyeball, head, [0.032 * k, 0.103, 0.084], [0.0125, 0.0115, 0.0115]); // eyeballs
      this._part(SPHERE_LO, M.iris, head, [0.032 * k, 0.103, 0.0945], [0.0048, 0.0048, 0.0018]); // iris
      this._part(SPHERE_LO, D, head, [0.05 * k, 0.074, 0.074], [0.026, 0.014, 0.02], [0, 0, -10 * k]); // cheekbones
      this._part(SPHERE_LO, D, head, [0.05 * k, 0.035, 0.025], [0.026, 0.034, 0.034]); // jaw angle
    }
    this._marker('headTop', head, [0, 0.22, 0.01]);
    this._marker('occiput', head, [0, 0.11, -0.116]);
    this._marker('eyes', head, [0, 0.11, 0.11]);
    this._marker('chin', head, [0, 0.0, 0.08]);

    for (const s of ['L', 'R']) {
      const k = s === 'L' ? 1 : -1;
      // --- Arm ---------------------------------------------------------------
      const sh = this._bone('shoulder' + s, chest, [0.19 * k, 0.25, -0.01]);
      this._part(limbGeo(0.3, 0.046, 0.036, 0.004, 0.32), D, sh, [0, 0.01, 0]);
      const el = this._bone('elbow' + s, sh, [0, -0.29, 0]);
      this._part(limbGeo(0.265, 0.04, 0.026, 0.006, 0.22), D, el, [0, 0.01, 0]);
      this._part(SPHERE_LO, T, el, [0, 0.0, -0.024], [0.02, 0.022, 0.013]); // olecranon
      const wr = this._bone('wrist' + s, el, [0, -0.26, 0]);
      // hand: palm, four curled fingers, thumb
      this._part(SPHERE, T, wr, [0, -0.048, 0.002], [0.034 * 1, 0.05, 0.017]);
      for (let f = 0; f < 4; f++) {
        const fx = (0.024 - f * 0.016) * k;
        const len = [0.04, 0.046, 0.044, 0.036][f];
        this._part(new THREE.CapsuleGeometry(0.0085, len, 4, 10), T, wr,
          [fx, -0.105, 0.01], [1, 1, 1], [-28, 0, 0]);
      }
      this._part(new THREE.CapsuleGeometry(0.0095, 0.04, 4, 10), D, wr,
        [0.022 * k, -0.05, 0.026], [1, 1, 1], [-40, 0, -25 * k]);
      this._marker('hand' + s, wr, [0, -0.07, 0.0]);
      this._marker('grip' + s, wr, [0, -0.07, 0.0]); // procedural hand: grip centre = hand point
      this._marker('palm' + s, wr, [0, -0.07, 0.025]);

      // --- Leg ---------------------------------------------------------------
      const hip = this._bone('hip' + s, root, [0.095 * k, -0.06, 0]);
      this._part(limbGeo(0.45, 0.082, 0.05, 0.006, 0.25), D, hip, [0, 0.01, 0]);
      const kn = this._bone('knee' + s, hip, [0, -0.44, 0]);
      this._part(SPHERE_LO, T, kn, [0, 0.0, 0.04], [0.028, 0.032, 0.015]); // patella
      this._part(limbGeo(0.43, 0.05, 0.03, 0.008, 0.22), D, kn, [0, 0.01, 0]);
      this._marker('kneeCap' + s, kn, [0, 0, 0.06]);
      const an = this._bone('ankle' + s, kn, [0, -0.42, 0]);
      // foot: heel, arch, toe box
      this._part(SPHERE, T, an, [0, -0.04, -0.02], [0.036, 0.03, 0.045]);
      this._part(SPHERE, D, an, [0, -0.04, 0.06], [0.044, 0.028, 0.085], [-6, 0, 0]);
      this._part(SPHERE, T, an, [0.004 * k, -0.05, 0.145], [0.046, 0.018, 0.035]);
      // retinacula: white bands that strap tendons down at wrist and ankle
      this._part(limbGeo(0.026, 0.03, 0.028, 0, 0.5, 20), T, el, [0, -0.222, 0], [1, 1, 0.82]);
      this._part(limbGeo(0.03, 0.036, 0.034, 0, 0.5, 20), T, kn, [0, -0.36, 0], [1, 1, 0.9]);
      this._part(SPHERE_LO, T, an, [0.026 * k, -0.012, 0.0], [0.01, 0.014, 0.012]); // malleolus
      this._marker('heel' + s, an, [0, -0.067, -0.05]);
      this._marker('toe' + s, an, [0, -0.067, 0.175]);
      this._marker('ball' + s, an, [0, -0.067, 0.12]);
      this._marker('instep' + s, an, [0, 0.0, 0.08]);
    }

    // --- Muscles (mirrored, origin -> insertion) -------------------------------
    this.object.updateMatrixWorld(true);
    for (const spec of MUSCLES) for (const s of ['L', 'R']) this._muscle(spec, s);
  }

  /** Generate one muscle belly directly in bind space with its own weights. */
  _muscle([group, aBone, aPos, bBone, bPos, w0, d, o = {}], side) {
    if (o.center && side === 'R') return;
    const k = side === 'R' ? -1 : 1;
    const w = w0 * (o.fascia ? 1 : 1.12); // slight overlap so bellies read as one continuous surface
    const name = (n) => (SIDE_JOINTS.includes(n) ? n + side : n);
    const bones = [name(aBone), name(o.on || aBone), name(bBone)];
    const BA = this.bones[bones[0]]; const BON = this.bones[bones[1]]; const BB = this.bones[bones[2]];
    const A = BA.localToWorld(new THREE.Vector3(aPos[0] * k, aPos[1], aPos[2]));
    const B = BB.localToWorld(new THREE.Vector3(bPos[0] * k, bPos[1], bPos[2]));
    const Y = B.clone().sub(A); const len = Y.length(); Y.normalize();
    // "out" points from the bone the belly lies on toward the belly.
    const mid = A.clone().add(B).multiplyScalar(0.5);
    const base = bones[1].replace(/[LR]$/, '');
    const s0 = BON.getWorldPosition(new THREE.Vector3());
    const s1 = BON.localToWorld(new THREE.Vector3(...BLEND[base].seg));
    const sd = s1.clone().sub(s0);
    const tt = THREE.MathUtils.clamp(mid.clone().sub(s0).dot(sd) / sd.lengthSq(), 0, 1);
    let out = mid.clone().sub(s0.clone().addScaledVector(sd, tt));
    if (out.lengthSq() < 1e-6) out.set(0, 0, 1);
    out.normalize();
    const Z = out.addScaledVector(Y, -out.dot(Y)).normalize();
    const X = new THREE.Vector3().crossVectors(Y, Z);

    const peak = o.peak ?? 0.45; const tA = o.tA ?? 0.1; const tB = o.tB ?? 0.16;
    const bow = o.bow ?? 0; const sink = o.sink ?? d * 0.35; const under = o.under ?? 0.35;
    const zA = o.zA ?? 0.22; const zB = o.zB ?? 0.22;
    const RINGS = 26; const SEG = 20;
    const pos = []; const uv = []; const col = []; const si = []; const sw = []; const disp = []; const idx = [];
    const jitter = 0.9 + Math.random() * 0.16;
    const tissue = new THREE.Color().setRGB(0.8 * jitter, 0.33 * jitter, 0.31 * jitter, THREE.SRGBColorSpace);
    const tendon = new THREE.Color().setRGB(0.9, 0.84, 0.8, THREE.SRGBColorSpace);
    const iA = this._boneIndex(bones[0]); const iO = this._boneIndex(bones[1]); const iB = this._boneIndex(bones[2]);
    const P = new THREE.Vector3();
    for (let r = 0; r <= RINGS; r++) {
      const t = r / RINGS;
      const tp = t < peak ? 0.5 * t / peak : 0.5 + 0.5 * (t - peak) / (1 - peak);
      const belly = Math.pow(Math.sin(Math.PI * tp), 0.7);
      const tend = o.fascia ? 1 : 1 - smooth(0, tA, t) * smooth(1, 1 - tB, t);
      let band = 0;
      for (const b of o.bands || []) band = Math.max(band, Math.exp(-Math.pow((t - b) / 0.02, 2)));
      let prof = (r === 0 || r === RINGS) ? 0 : Math.max(0.1, o.fascia ? Math.min(1, belly * 3) : belly * (1 - 0.78 * tend));
      prof *= 1 - 0.12 * band;
      const wA = bones[0] !== bones[1] ? 1 - smooth(0, zA, t) : 0;
      const wB = bones[2] !== bones[1] ? smooth(1 - zB, 1, t) : 0;
      const wO = Math.max(0, 1 - wA - wB);
      for (let sg = 0; sg <= SEG; sg++) {
        const th = (sg / SEG) * Math.PI * 2;
        const cx = Math.cos(th); const sz = Math.sin(th);
        const x = cx * w * prof;
        const z = sz * d * prof * (sz < 0 ? under : 1);
        P.copy(A).addScaledVector(Y, len * t).addScaledVector(X, x)
          .addScaledVector(Z, z + bow * Math.sin(Math.PI * t) - sink);
        pos.push(P.x, P.y, P.z);
        uv.push(sg / SEG, (t * len) / 0.12);
        const ao = (0.62 + 0.38 * smooth(-0.5, 0.55, sz)) * (1 - 0.18 * band);
        const tm = Math.min(1, tend + band * 0.7);
        col.push((tissue.r + (tendon.r - tissue.r) * tm) * ao,
          (tissue.g + (tendon.g - tissue.g) * tm) * ao,
          (tissue.b + (tendon.b - tissue.b) * tm) * ao);
        si.push(iO, iA, iB, 0);
        sw.push(wO, wA, wB, 0);
        const bl = (o.bulge || 0) * belly * Math.max(0, sz);
        disp.push(Z.x * bl, Z.y * bl, Z.z * bl);
      }
    }
    for (let r = 0; r < RINGS; r++) {
      for (let sg = 0; sg < SEG; sg++) {
        const a0 = r * (SEG + 1) + sg; const a1 = a0 + 1; const b0 = a0 + SEG + 1; const b1 = b0 + 1;
        idx.push(a0, b0, a1, a1, b0, b1);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex(idx);
    g.computeVertexNormals();
    // keep normals pointing outward regardless of the X/Z handedness
    const N = g.attributes.normal; const C = new THREE.Vector3(); const nn = new THREE.Vector3();
    let dots = 0;
    for (let i = 0; i < N.count; i += 7) {
      P.fromBufferAttribute(g.attributes.position, i);
      const t = Math.min(1, Math.max(0, P.clone().sub(A).dot(Y) / len));
      C.copy(A).addScaledVector(Y, len * t);
      dots += nn.fromBufferAttribute(N, i).dot(P.sub(C));
    }
    if (dots < 0) {
      const ix = g.index.array;
      for (let i = 0; i < ix.length; i += 3) { const tmp = ix[i + 1]; ix[i + 1] = ix[i + 2]; ix[i + 2] = tmp; }
      g.computeVertexNormals();
    }
    g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(si, 4));
    g.setAttribute('skinWeight', new THREE.Float32BufferAttribute(sw, 4));
    g.userData.disp = new Float32Array(disp);
    g.userData.hasBulge = !!o.bulge;
    this.parts.push({ baked: g, mat: this.mats[group], group, layer: o.layer || 2 });
  }

  _boneIndex(n) {
    if (!this._bIdx) this._bIdx = new Map(Object.values(this.bones).map((b, i) => [b.name, i]));
    return this._bIdx.get(n);
  }

  /** Bake parts into bind space, compute skin weights, merge per material. */
  _skin() {
    this.object.updateMatrixWorld(true);
    const boneList = Object.values(this.bones);
    const idx = new Map(boneList.map((b, i) => [b.name, i]));
    this.skeleton = new THREE.Skeleton(boneList);

    const byMat = new Map();
    const m4 = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const e = new THREE.Euler();
    const a = new THREE.Vector3(); const b = new THREE.Vector3();
    const ab = new THREE.Vector3(); const v = new THREE.Vector3(); const n = new THREE.Vector3();

    for (const p of this.parts) {
      if (p.baked) {
        const key = p.mat.uuid + '|' + p.layer;
        if (!byMat.has(key)) byMat.set(key, { mat: p.mat, layer: p.layer, geos: [], groups: new Set() });
        byMat.get(key).geos.push(p.baked);
        byMat.get(key).groups.add(p.group);
        continue;
      }
      const g = p.geo.clone();
      const pos0 = g.attributes.position;
      const count = pos0.count;
      const unitY = p.geo.userData.unitY;
      const yAt = (i) => (unitY ? unitY[i] : pos0.getY(i));
      const prof = p.bulge ? new Float32Array(count) : null;
      if (prof) for (let i = 0; i < count; i++) prof[i] = Math.max(0, 1 - Math.abs(yAt(i)) * 1.15);
      const muscle = !!p.group;
      const tend = muscle ? new Float32Array(count) : null;
      if (tend) {
        // abs blocks have no tendon ends (their borders are the deep layer)
        if (p.group !== 'abs') for (let i = 0; i < count; i++) tend[i] = smooth(0.6, 1.0, Math.abs(yAt(i)));
      }

      e.set(p.rot[0] * DEG, p.rot[1] * DEG, p.rot[2] * DEG);
      q.setFromEuler(e);
      m4.compose(new THREE.Vector3(...p.pos), q, new THREE.Vector3(...p.scale));
      m4.premultiply(p.bone.matrixWorld);
      g.applyMatrix4(m4);
      if (g.attributes.normal) g.normalizeNormals();

      const base = p.bone.name.replace(/[LR]$/, '');
      const side = p.bone.name.length > base.length ? p.bone.name.slice(-1) : '';
      const cfg = BLEND[base];
      p.bone.getWorldPosition(a);
      b.set(...cfg.seg); p.bone.localToWorld(b);
      ab.subVectors(b, a);
      const L2 = ab.lengthSq();
      const own = idx.get(p.bone.name);
      const par = cfg.parent ? idx.get(cfg.parent[0] + (SIDE_JOINTS.includes(cfg.parent[0]) ? side : '')) : 0;
      const chi = cfg.child ? idx.get(cfg.child[0] + (SIDE_JOINTS.includes(cfg.child[0]) ? side : '')) : 0;

      const si = new Uint16Array(count * 4);
      const sw = new Float32Array(count * 4);
      const P = g.attributes.position;
      for (let i = 0; i < count; i++) {
        v.fromBufferAttribute(P, i);
        const t = v.sub(a).dot(ab) / L2;
        const s = cfg.parent ? smooth(-cfg.parent[1], cfg.parent[1], t) : 1;
        const c = cfg.child ? smooth(1 - cfg.child[1], 1 + cfg.child[1], t) : 0;
        let wp = 1 - s;
        if (cfg.parent?.[2] != null) wp = Math.min(wp, cfg.parent[2]);
        const wc = (1 - wp) * c;
        const wo = Math.max(0, 1 - wp - wc);
        si.set([own, par, chi, 0], i * 4);
        sw.set([wo, wp, wc, 0], i * 4);
      }
      // Vertex colour: muscles carry their own tissue colour (material colour is
      // a multiplier for highlighting); tendon ends fade to pale aponeurosis;
      // rims that dive under neighbours are darkened (cheap ambient occlusion).
      const col = new Float32Array(count * 3).fill(1);
      if (muscle) {
        const c0 = new THREE.Vector3(); g.computeBoundingSphere(); c0.copy(g.boundingSphere.center);
        const t0 = THREE.MathUtils.clamp(c0.clone().sub(a).dot(ab) / L2, 0, 1);
        const out = c0.clone().sub(a.clone().addScaledVector(ab, t0)).normalize();
        const N = g.attributes.normal;
        const jitter = 0.92 + Math.random() * 0.14;
        // tissue + tendon colours authored in sRGB, converted to linear
        const tissue = new THREE.Color().setRGB(0.62 * jitter, 0.2 * jitter, 0.17 * jitter, THREE.SRGBColorSpace);
        const tendon = new THREE.Color().setRGB(0.84, 0.74, 0.66, THREE.SRGBColorSpace);
        for (let i = 0; i < count; i++) {
          n.fromBufferAttribute(N, i);
          const ao = 0.35 + 0.65 * smooth(-0.45, 0.6, n.dot(out));
          const tt = tend[i];
          col[i * 3] = (tissue.r + (tendon.r - tissue.r) * tt) * ao;
          col[i * 3 + 1] = (tissue.g + (tendon.g - tissue.g) * tt) * ao;
          col[i * 3 + 2] = (tissue.b + (tendon.b - tissue.b) * tt) * ao;
        }
      }
      g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
      g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(si, 4));
      g.setAttribute('skinWeight', new THREE.Float32BufferAttribute(sw, 4));

      // Contraction morph: push the belly outward along its normal.
      const disp = new Float32Array(count * 3);
      if (prof) {
        const N = g.attributes.normal;
        for (let i = 0; i < count; i++) {
          n.fromBufferAttribute(N, i).multiplyScalar(p.bulge * prof[i]);
          disp.set([n.x, n.y, n.z], i * 3);
        }
      }
      g.userData.disp = disp;
      g.userData.hasBulge = !!prof;
      for (const k of Object.keys(g.attributes)) {
        if (!['position', 'normal', 'uv', 'color', 'skinIndex', 'skinWeight'].includes(k)) g.deleteAttribute(k);
      }
      const key = p.mat.uuid + '|0';
      if (!byMat.has(key)) byMat.set(key, { mat: p.mat, layer: 0, geos: [], groups: new Set() });
      const entry = byMat.get(key);
      entry.geos.push(g);
      if (p.group) entry.groups.add(p.group);
    }

    this.meshes = [];
    this.groupMesh = {};
    const ghost = !!this.mats.skin.transparent;
    for (const { mat, layer, geos, groups } of byMat.values()) {
      const bulgy = !ghost && geos.some((g) => g.userData.hasBulge);
      const merged = mergeGeometries(geos, false);
      if (bulgy) {
        const total = geos.reduce((s, g) => s + g.userData.disp.length, 0);
        const d = new Float32Array(total);
        let o = 0;
        for (const g of geos) { d.set(g.userData.disp, o); o += g.userData.disp.length; }
        merged.morphAttributes.position = [new THREE.Float32BufferAttribute(d, 3)];
        merged.morphTargetsRelative = true;
      }
      const mesh = new THREE.SkinnedMesh(merged, mat);
      mesh.bind(this.skeleton);
      mesh.frustumCulled = false;
      mesh.castShadow = !ghost;
      mesh.receiveShadow = !ghost;
      this.object.add(mesh);
      this.meshes.push(mesh);
      mesh.userData.layer = layer;
      mesh.userData.baseMat = mat;
      for (const gname of groups) (this.groupMesh[gname] = this.groupMesh[gname] || []).push(mesh);
    }
    this.parts = null;
  }

  /**
   * Apply an expanded pose: { joint: [x,y,z] degrees }.
   * Also contracts muscle bellies as the joints they cross bend.
   */
  applyPose(pose) {
    for (const name of ALL_JOINTS) {
      const b = this.bones[name];
      const a = pose[name] || REST[name] || [0, 0, 0];
      b.rotation.set(a[0] * DEG, a[1] * DEG, a[2] * DEG, name === 'root' ? 'YXZ' : 'XYZ');
    }
    const avg = (j, i, sign) => Math.max(0, sign * ((pose[j + 'L']?.[i] ?? 0) + (pose[j + 'R']?.[i] ?? 0)) / 2);
    const set = (g, f) => {
      for (const m of this.groupMesh[g] || []) if (m.morphTargetInfluences) m.morphTargetInfluences[0] = Math.min(1, f);
    };
    set('biceps', avg('elbow', 0, -1) / 120);
    set('hams', avg('knee', 0, 1) / 140);
    set('calves', avg('ankle', 0, 1) / 45);
  }

  /**
   * Anatomy layer: 'skin' (a skinned athletic body), 'superficial' (all
   * muscles) or 'deep' (superficial muscles peeled away).
   */
  setLayer(mode) {
    this.layer = mode;
    if (mode === 'skin' && !this.skinMat) {
      this.skinMat = new THREE.MeshPhysicalMaterial({
        color: 0xc0907c, roughness: 0.58, sheen: 0.35, sheenRoughness: 0.6, sheenColor: 0xf2b9a0,
        specularIntensity: 0.45, clearcoat: 0.05, emissive: 0x000000,
      });
    }
    for (const m of this.meshes) {
      const base = m.userData.baseMat;
      const keep = base === this.mats.eyeball || base === this.mats.iris;
      m.material = mode === 'skin' && !keep && !base.transparent ? this.skinMat : base;
      m.visible = !(mode === 'deep' && m.userData.layer === 1);
    }
  }

  /** Approximate whole-body centre of mass from segment midpoints. */
  com(target = new THREE.Vector3()) {
    const S = [
      ['pelvis', 'spine', 0.14], ['spine', 'chest', 0.13], ['chest', 'neck', 0.2], ['head', 'headTop', 0.08],
    ];
    for (const s of ['L', 'R']) {
      S.push(['shoulder' + s, 'elbow' + s, 0.028], ['elbow' + s, 'wrist' + s, 0.016], ['wrist' + s, 'hand' + s, 0.006],
        ['hip' + s, 'knee' + s, 0.1], ['knee' + s, 'ankle' + s, 0.047], ['ankle' + s, 'toe' + s, 0.014]);
    }
    target.set(0, 0, 0);
    let m = 0;
    const a = new THREE.Vector3(); const b = new THREE.Vector3();
    for (const [p, q, w] of S) {
      this.world(p, a); this.world(q, b);
      target.addScaledVector(a.add(b).multiplyScalar(0.5), w);
      m += w;
    }
    return target.multiplyScalar(1 / m);
  }

  /** World position of a bone or marker (supports "mid:a,b,c"). */
  world(name, target = new THREE.Vector3()) {
    if (name.startsWith('mid:')) {
      const parts = name.slice(4).split(',');
      target.set(0, 0, 0);
      const t = new THREE.Vector3();
      for (const p of parts) target.add(this.world(p, t));
      return target.multiplyScalar(1 / parts.length);
    }
    const o = this.markers[name] || this.bones[name];
    if (!o) throw new Error('Unknown point ' + name);
    return o.getWorldPosition(target);
  }

  setHighlight(primary = [], secondary = [], intensity = 1, faultTint = 0) {
    for (const g of MUSCLE_GROUPS) {
      const mat = this.mats[g];
      if (!mat.emissive) continue;
      if (primary.includes(g)) {
        mat.color.copy(C_PRIMARY);
        mat.emissive.copy(E_PRIMARY);
        mat.emissiveIntensity = 0.02 + 0.1 * intensity;
      } else if (secondary.includes(g)) {
        mat.color.copy(C_SECOND);
        mat.emissive.copy(E_SECOND);
        mat.emissiveIntensity = 0.02 + 0.08 * intensity;
      } else {
        mat.color.copy(C_IDLE);
        mat.emissive.setHex(0x000000);
      }
    }
    for (const k of ['skin', 'deep', 'tendon']) {
      const m = this.mats[k];
      if (!m.emissive) continue;
      m.emissive.setHex(0xff1a1a);
      m.emissiveIntensity = faultTint * 0.14;
    }
  }
}

/** Expand a compact authored pose into a full joint map. */
export function expandPose(p) {
  const out = {};
  for (const [k, v] of Object.entries(p)) {
    if (SIDE_JOINTS.includes(k)) {
      out[k + 'L'] = [v[0] || 0, v[1] || 0, v[2] || 0];
      out[k + 'R'] = [v[0] || 0, -(v[1] || 0), -(v[2] || 0)];
    }
  }
  for (const [k, v] of Object.entries(p)) {
    if (!SIDE_JOINTS.includes(k)) out[k] = [v[0] || 0, v[1] || 0, v[2] || 0];
  }
  for (const j of ALL_JOINTS) if (!out[j]) out[j] = REST[j] ? [...REST[j]] : [0, 0, 0];
  return out;
}

export function addPose(a, b) {
  const out = {};
  for (const j of ALL_JOINTS) {
    const x = a[j] || [0, 0, 0];
    const y = b[j] || [0, 0, 0];
    out[j] = [x[0] + y[0], x[1] + y[1], x[2] + y[2]];
  }
  return out;
}

/** Delta poses use the same compact syntax but default to zero (not REST). */
export function expandDelta(p) {
  const out = {};
  for (const [k, v] of Object.entries(p)) {
    if (SIDE_JOINTS.includes(k)) {
      out[k + 'L'] = [v[0] || 0, v[1] || 0, v[2] || 0];
      out[k + 'R'] = [v[0] || 0, -(v[1] || 0), -(v[2] || 0)];
    }
  }
  for (const [k, v] of Object.entries(p)) {
    if (!SIDE_JOINTS.includes(k)) out[k] = [v[0] || 0, v[1] || 0, v[2] || 0];
  }
  return out;
}

export function lerpPose(a, b, t) {
  const out = {};
  for (const j of ALL_JOINTS) {
    const x = a[j]; const y = b[j];
    out[j] = [lerp(x[0], y[0], t), lerp(x[1], y[1], t), lerp(x[2], y[2], t)];
  }
  return out;
}
