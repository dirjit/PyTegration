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

/**
 * Muscle belly shapes, built from a unit sphere so UVs (fibres run along v)
 * and the |y| tendon mask stay meaningful:
 *  - 'belly' fusiform: full in the upper third, tapering into tendon ends
 *  - 'block' superellipsoid: the flat, squarish segments of the rectus abdominis
 *  - 'fan'   wide at one end, converging to a tendon (pecs, lats, delts)
 */
function shapeGeo(kind) {
  const g = new THREE.SphereGeometry(1, 34, 26);
  const P = g.attributes.position;
  const v = new THREE.Vector3();
  for (let i = 0; i < P.count; i++) {
    v.fromBufferAttribute(P, i);
    const y = v.y;
    if (kind === 'belly') {
      const taper = 0.62 + 0.38 * Math.pow(1 - Math.abs(y), 0.6);
      v.x *= taper; v.z *= taper;
      v.y = y + 0.14 * (1 - y * y); // belly peak sits proximally
    } else if (kind === 'block') {
      const e = 0.5;
      v.set(Math.sign(v.x) * Math.pow(Math.abs(v.x), e), Math.sign(v.y) * Math.pow(Math.abs(v.y), e), v.z);
      v.z *= 0.9;
    } else if (kind === 'fan') {
      const w = 0.45 + 0.55 * (y + 1) / 2; // wide at +y, narrow at -y
      v.x *= w * 1.05;
      v.z *= 0.8 + 0.2 * w;
    }
    P.setXYZ(i, v.x, v.y, v.z);
  }
  g.computeVertexNormals();
  g.userData.unitY = Float32Array.from({ length: P.count }, (_, i) => SPHERE_Y(g, i));
  return g;
}
function SPHERE_Y(g, i) {
  // recover the original sphere latitude from the uv (v runs pole to pole)
  return 1 - 2 * g.attributes.uv.getY(i);
}
const BELLY = shapeGeo('belly');
const BLOCK = shapeGeo('block');
const FAN = shapeGeo('fan');
const SHAPE_BY_GROUP = { abs: BLOCK, chest: FAN, lats: FAN, traps: FAN, upperback: FAN };

// Muscle catalogue: [group, bone, position, scale, rotation(deg), bulge]
// Positions are for the LEFT side (+X) and mirrored automatically.
// Bellies are unit spheres scaled into anatomical shapes and sunk into the
// underlying segment so only their contour shows, like real muscle under fascia.
const MUSCLES = [
  // --- chest & shoulder girdle ---
  ['chest', 'chest', [0.07, 0.195, 0.088], [0.088, 0.072, 0.042], [-8, -10, 16], 0],
  ['chest', 'chest', [0.12, 0.215, 0.07], [0.055, 0.042, 0.034], [0, -20, 32], 0],
  ['chest', 'chest', [0.065, 0.14, 0.092], [0.07, 0.035, 0.03], [0, -8, 8], 0],
  ['delts', 'shoulder', [0.012, -0.04, 0.026], [0.05, 0.095, 0.05], [10, 0, 6], 0],
  ['delts', 'shoulder', [0.03, -0.045, 0.0], [0.045, 0.1, 0.055], [0, 0, 8], 0],
  ['delts', 'shoulder', [0.012, -0.04, -0.028], [0.05, 0.092, 0.05], [-10, 0, 6], 0],
  ['traps', 'chest', [0.07, 0.29, -0.03], [0.09, 0.042, 0.055], [0, 0, -24], 0],
  ['traps', 'neck', [0.032, 0.035, 0.03], [0.016, 0.065, 0.02], [-28, 0, -8], 0],
  ['upperback', 'chest', [0.045, 0.2, -0.098], [0.06, 0.085, 0.03], [0, 0, -10], 0],
  ['upperback', 'chest', [0.11, 0.2, -0.085], [0.05, 0.05, 0.03], [0, 20, -20], 0],
  ['lats', 'chest', [0.115, 0.11, -0.055], [0.068, 0.15, 0.042], [10, 0, -20], 0],
  ['lats', 'spine', [0.085, 0.13, -0.075], [0.06, 0.1, 0.032], [0, 0, -12], 0],
  // --- arms ---
  ['biceps', 'shoulder', [-0.005, -0.165, 0.034], [0.036, 0.095, 0.04], [0, 0, 0], 0.016],
  ['triceps', 'shoulder', [0.016, -0.13, -0.032], [0.038, 0.11, 0.04], [0, 0, 4], 0],
  ['triceps', 'shoulder', [-0.014, -0.17, -0.03], [0.032, 0.09, 0.035], [0, 0, -4], 0],
  ['forearms', 'elbow', [-0.012, -0.075, 0.016], [0.036, 0.095, 0.034], [0, 0, -4], 0],
  ['forearms', 'elbow', [0.016, -0.065, 0.004], [0.036, 0.1, 0.034], [0, 0, 6], 0],
  // --- core ---
  ['abs', 'spine', [0.03, 0.015, 0.093], [0.028, 0.031, 0.02], [0, 0, 0], 0],
  ['abs', 'spine', [0.031, 0.083, 0.096], [0.029, 0.032, 0.021], [0, 0, 0], 0],
  ['abs', 'spine', [0.032, 0.152, 0.097], [0.03, 0.032, 0.021], [0, 0, 0], 0],
  ['abs', 'chest', [0.033, 0.025, 0.1], [0.031, 0.03, 0.02], [0, 0, 0], 0],
  ['obliques', 'spine', [0.098, 0.085, 0.038], [0.034, 0.09, 0.06], [0, 0, 6], 0],
  ['obliques', 'chest', [0.13, 0.12, 0.05], [0.022, 0.017, 0.022], [0, 0, -30], 0],
  ['obliques', 'chest', [0.135, 0.085, 0.045], [0.022, 0.017, 0.022], [0, 0, -30], 0],
  ['obliques', 'chest', [0.132, 0.05, 0.04], [0.022, 0.017, 0.022], [0, 0, -30], 0],
  ['lowerback', 'spine', [0.036, 0.09, -0.082], [0.03, 0.12, 0.03], [0, 0, 0], 0],
  ['lowerback', 'root', [0.034, 0.03, -0.088], [0.028, 0.07, 0.025], [0, 0, 0], 0],
  // --- hips & legs ---
  ['glutes', 'root', [0.068, -0.05, -0.072], [0.088, 0.1, 0.072], [0, 0, -8], 0],
  ['glutes', 'root', [0.112, 0.02, -0.025], [0.045, 0.06, 0.055], [0, 0, -10], 0],
  ['quads', 'hip', [0.0, -0.205, 0.05], [0.044, 0.18, 0.044], [4, 0, 0], 0],
  ['quads', 'hip', [0.042, -0.24, 0.012], [0.048, 0.17, 0.05], [0, 0, 3], 0],
  ['quads', 'hip', [-0.034, -0.33, 0.034], [0.044, 0.085, 0.044], [0, 0, -10], 0],
  ['adductors', 'hip', [-0.048, -0.13, -0.002], [0.042, 0.13, 0.05], [0, 0, -12], 0],
  ['hams', 'hip', [0.024, -0.245, -0.045], [0.04, 0.17, 0.044], [0, 0, 2], 0.01],
  ['hams', 'hip', [-0.024, -0.245, -0.045], [0.038, 0.17, 0.042], [0, 0, -2], 0.01],
  ['calves', 'knee', [0.022, -0.12, -0.034], [0.033, 0.1, 0.042], [0, 0, 3], 0.012],
  ['calves', 'knee', [-0.02, -0.11, -0.036], [0.035, 0.105, 0.044], [0, 0, -3], 0.012],
  ['calves', 'knee', [0.0, -0.2, -0.024], [0.044, 0.1, 0.034], [0, 0, 0], 0],
  ['calves', 'knee', [0.022, -0.16, 0.03], [0.02, 0.12, 0.022], [0, 0, 0], 0],
];

export const MUSCLE_GROUPS = [...new Set(MUSCLES.map((m) => m[0]))];

export const MUSCLE_LABEL = {
  chest: 'Chest', delts: 'Delts', biceps: 'Biceps', triceps: 'Triceps',
  forearms: 'Forearms / grip', lats: 'Lats', traps: 'Traps',
  upperback: 'Upper back', abs: 'Abs', obliques: 'Obliques',
  lowerback: 'Spinal erectors', glutes: 'Glutes', quads: 'Quads',
  hams: 'Hamstrings', calves: 'Calves', adductors: 'Adductors',
};

// Colours for muscle states (shared by setHighlight).
const C_IDLE = new THREE.Color(0.92, 0.9, 0.9);
const C_PRIMARY = new THREE.Color(1.3, 0.78, 0.66);
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
    const mats = { skin: g, hair: g, nail: g, deep: g, tendon: g };
    MUSCLE_GROUPS.forEach((k) => (mats[k] = g));
    return mats;
  }
  const { map, bump } = fiberTextures();
  const skin = new THREE.MeshPhysicalMaterial({
    color: 0xb48770, roughness: 0.68, metalness: 0, vertexColors: true,
    sheen: 0.35, sheenRoughness: 0.7, sheenColor: 0xd99a80, specularIntensity: 0.35,
    emissive: 0x000000,
  });
  const hair = new THREE.MeshStandardMaterial({ color: 0x241a16, roughness: 0.85 });
  const nail = skin;
  // Deep muscle layer between the bellies, and pale tendon/fascia at joints.
  const deep = new THREE.MeshPhysicalMaterial({
    color: 0x6e2a23, map, bumpMap: bump, bumpScale: 2, roughness: 0.7, vertexColors: true,
    specularIntensity: 0.4, sheen: 0.2, sheenColor: 0xff8f7a, emissive: 0x000000,
  });
  const tendon = new THREE.MeshPhysicalMaterial({
    color: 0xc2ab98, roughness: 0.5, vertexColors: true, specularIntensity: 0.5,
    sheen: 0.3, sheenColor: 0xf0d6c4, emissive: 0x000000,
  });
  const mats = { skin, hair, nail, deep, tendon };
  MUSCLE_GROUPS.forEach((k) => {
    mats[k] = new THREE.MeshPhysicalMaterial({
      color: C_IDLE.clone(), map, bumpMap: bump, bumpScale: 2.6, vertexColors: true,
      roughness: 0.56, metalness: 0, specularIntensity: 0.55,
      clearcoat: 0.12, clearcoatRoughness: 0.6, // thin moist film, not plastic
      sheen: 0.25, sheenRoughness: 0.6, sheenColor: 0xff8f80,
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
      this._part(SPHERE_LO, T, chest, [0.095 * k, 0.29, 0.05], [0.085, 0.012, 0.014], [0, 22 * k, -8 * k]);
    }
    this._marker('upperBack', chest, [0, 0.17, -0.13]);
    this._marker('sternum', chest, [0, 0.16, 0.12]);
    this._marker('chestMid', chest, [0, 0.14, 0]);

    // --- Neck & head --------------------------------------------------------
    const neck = this._bone('neck', chest, [0, 0.305, -0.005]);
    this._part(limbGeo(0.12, 0.05, 0.046, 0, 0.5), D, neck, [0, 0.11, 0]);
    const head = this._bone('head', neck, [0, 0.09, 0]);
    this._part(SPHERE, S, head, [0, 0.112, -0.006], [0.091, 0.108, 0.102]); // cranium
    this._part(SPHERE, S, head, [0, 0.06, 0.035], [0.071, 0.075, 0.078]); // face mass
    this._part(SPHERE_LO, S, head, [0, 0.02, 0.06], [0.05, 0.03, 0.045]); // jaw
    this._part(SPHERE_LO, S, head, [0, 0.012, 0.09], [0.022, 0.02, 0.02]); // chin
    this._part(SPHERE_LO, S, head, [0, 0.122, 0.078], [0.064, 0.014, 0.028]); // brow
    this._part(SPHERE_LO, S, head, [0, 0.086, 0.106], [0.01, 0.022, 0.014], [-14, 0, 0]); // nose
    for (const k of [1, -1]) {
      this._part(SPHERE_LO, S, head, [0.089 * k, 0.09, 0.0], [0.012, 0.03, 0.02]); // ears
    }
    this._part(new THREE.SphereGeometry(1, 30, 14, 0, Math.PI * 2, 0, 1.35), M.hair, head,
      [0, 0.118, -0.01], [0.095, 0.11, 0.106], [-14, 0, 0]);
    this._marker('headTop', head, [0, 0.22, 0.01]);
    this._marker('eyes', head, [0, 0.11, 0.11]);
    this._marker('chin', head, [0, 0.0, 0.08]);

    for (const s of ['L', 'R']) {
      const k = s === 'L' ? 1 : -1;
      // --- Arm ---------------------------------------------------------------
      const sh = this._bone('shoulder' + s, chest, [0.19 * k, 0.25, -0.01]);
      this._part(limbGeo(0.3, 0.046, 0.036, 0.004, 0.32), D, sh, [0, 0.01, 0]);
      const el = this._bone('elbow' + s, sh, [0, -0.29, 0]);
      this._part(limbGeo(0.265, 0.04, 0.026, 0.006, 0.22), D, el, [0, 0.01, 0]);
      this._part(SPHERE_LO, T, el, [0, 0.0, -0.03], [0.022, 0.024, 0.016]); // olecranon
      const wr = this._bone('wrist' + s, el, [0, -0.26, 0]);
      // hand: palm, four curled fingers, thumb
      this._part(SPHERE, S, wr, [0, -0.048, 0.002], [0.034 * 1, 0.05, 0.017]);
      for (let f = 0; f < 4; f++) {
        const fx = (0.024 - f * 0.016) * k;
        const len = [0.04, 0.046, 0.044, 0.036][f];
        this._part(new THREE.CapsuleGeometry(0.0085, len, 4, 10), S, wr,
          [fx, -0.105, 0.01], [1, 1, 1], [-28, 0, 0]);
      }
      this._part(new THREE.CapsuleGeometry(0.0095, 0.04, 4, 10), S, wr,
        [0.022 * k, -0.05, 0.026], [1, 1, 1], [-40, 0, -25 * k]);
      this._marker('hand' + s, wr, [0, -0.07, 0.0]);
      this._marker('palm' + s, wr, [0, -0.07, 0.025]);

      // --- Leg ---------------------------------------------------------------
      const hip = this._bone('hip' + s, root, [0.095 * k, -0.06, 0]);
      this._part(limbGeo(0.45, 0.082, 0.05, 0.006, 0.25), D, hip, [0, 0.01, 0]);
      const kn = this._bone('knee' + s, hip, [0, -0.44, 0]);
      this._part(SPHERE_LO, T, kn, [0, 0.0, 0.046], [0.03, 0.034, 0.018]); // patella
      this._part(limbGeo(0.43, 0.05, 0.03, 0.008, 0.22), D, kn, [0, 0.01, 0]);
      this._marker('kneeCap' + s, kn, [0, 0, 0.06]);
      const an = this._bone('ankle' + s, kn, [0, -0.42, 0]);
      // foot: heel, arch, toe box
      this._part(SPHERE, S, an, [0, -0.04, -0.02], [0.036, 0.03, 0.045]);
      this._part(SPHERE, S, an, [0, -0.04, 0.06], [0.044, 0.028, 0.085], [-6, 0, 0]);
      this._part(SPHERE, S, an, [0.004 * k, -0.05, 0.145], [0.046, 0.018, 0.035]);
      this._part(SPHERE_LO, T, an, [0.03 * k, -0.012, 0.0], [0.012, 0.016, 0.014]); // malleolus
      this._marker('heel' + s, an, [0, -0.067, -0.05]);
      this._marker('toe' + s, an, [0, -0.067, 0.175]);
      this._marker('ball' + s, an, [0, -0.067, 0.12]);
      this._marker('instep' + s, an, [0, 0.0, 0.08]);
    }

    // --- Muscles (mirrored) ----------------------------------------------------
    const SIDED = ['shoulder', 'elbow', 'hip', 'knee', 'wrist', 'ankle'];
    for (const [group, bone, pos, scale, rot, bulge] of MUSCLES) {
      for (const s of ['L', 'R']) {
        const k = s === 'R' ? -1 : 1;
        const boneName = SIDED.includes(bone) ? bone + s : bone;
        this._part(SHAPE_BY_GROUP[group] || BELLY, this.mats[group], this.bones[boneName],
          [pos[0] * k, pos[1], pos[2]], [scale[0] * 1.1, scale[1] * 1.05, scale[2] * 1.08], [rot[0], rot[1] * k, rot[2] * k],
          { group, bulge });
      }
    }
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
      if (!byMat.has(p.mat)) byMat.set(p.mat, { geos: [], groups: new Set() });
      const entry = byMat.get(p.mat);
      entry.geos.push(g);
      if (p.group) entry.groups.add(p.group);
    }

    this.meshes = [];
    this.groupMesh = {};
    const ghost = !!this.mats.skin.transparent;
    for (const [mat, { geos, groups }] of byMat) {
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
      for (const gname of groups) this.groupMesh[gname] = mesh;
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
      const m = this.groupMesh[g];
      if (m?.morphTargetInfluences) m.morphTargetInfluences[0] = Math.min(1, f);
    };
    set('biceps', avg('elbow', 0, -1) / 120);
    set('hams', avg('knee', 0, 1) / 140);
    set('calves', avg('ankle', 0, 1) / 45);
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
        mat.emissiveIntensity = 0.03 + 0.26 * intensity;
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
