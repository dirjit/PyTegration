// =============================================================================
// rig.js — a procedural, anatomically-zoned 3D mannequin built from scratch.
// -----------------------------------------------------------------------------
// No external model files: every body segment is a lathe-turned tapered shape
// and every major muscle is its own mesh, so we can light it up (primary /
// secondary movers) and make it "contract" as the joint it crosses flexes.
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

export const DEG = Math.PI / 180;
const V2 = THREE.Vector2;
const lerp = (a, b, t) => a + (b - a) * t;

export const SIDE_JOINTS = ['shoulder', 'elbow', 'wrist', 'hip', 'knee', 'ankle'];
export const CENTER_JOINTS = ['root', 'spine', 'chest', 'neck', 'head'];
export const ALL_JOINTS = [
  ...CENTER_JOINTS,
  ...SIDE_JOINTS.flatMap((j) => [j + 'L', j + 'R']),
];

// Resting "neutral" angles so arms don't clip through the torso.
const REST = {
  shoulderL: [0, 0, 7], shoulderR: [0, 0, -7],
  elbowL: [-6, 0, 0], elbowR: [-6, 0, 0],
};

/** Tapered limb hanging from y=0 to y=-len with a gaussian muscle belly. */
function limbGeo(len, r0, r1, belly = 0, peak = 0.35, radial = 36) {
  const p = [];
  const cap = 8;
  for (let i = 0; i <= cap; i++) {
    const a = (Math.PI / 2) * (i / cap);
    p.push(new V2(Math.sin(a) * r0, Math.cos(a) * r0 * 0.55));
  }
  const N = 26;
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
function torsoGeo(profile, radial = 48) {
  const g = new THREE.LatheGeometry(profile.map(([r, y]) => new V2(r, y)), radial);
  g.computeVertexNormals();
  return g;
}

const SPHERE = new THREE.SphereGeometry(1, 40, 28);

// Muscle catalogue: [group, bone, position, scale, rotation(deg), mirror]
// Positions are for the LEFT side (+X); mirrored automatically.
const MUSCLES = [
  ['chest', 'chest', [0.082, 0.19, 0.098], [0.088, 0.066, 0.036], [0, 0, 18], true],
  ['delts', 'shoulder', [0.012, -0.03, 0.0], [0.064, 0.085, 0.07], [0, 0, 6], true],
  ['biceps', 'shoulder', [0.0, -0.16, 0.034], [0.038, 0.088, 0.038], [0, 0, 0], true],
  ['triceps', 'shoulder', [0.0, -0.14, -0.034], [0.044, 0.1, 0.04], [0, 0, 0], true],
  ['forearms', 'elbow', [0.0, -0.085, 0.006], [0.043, 0.095, 0.038], [0, 0, 0], true],
  ['lats', 'chest', [0.118, 0.11, -0.055], [0.058, 0.135, 0.038], [8, 0, -22], true],
  ['traps', 'chest', [0.07, 0.29, -0.035], [0.085, 0.042, 0.05], [0, 0, -22], true],
  ['upperback', 'chest', [0.055, 0.19, -0.095], [0.06, 0.07, 0.028], [0, 0, 0], true],
  ['abs', 'spine', [0.034, 0.015, 0.098], [0.03, 0.03, 0.018], [0, 0, 0], true],
  ['abs', 'spine', [0.034, 0.085, 0.1], [0.031, 0.032, 0.018], [0, 0, 0], true],
  ['abs', 'spine', [0.034, 0.155, 0.1], [0.032, 0.032, 0.018], [0, 0, 0], true],
  ['abs', 'chest', [0.034, 0.025, 0.103], [0.032, 0.03, 0.018], [0, 0, 0], true],
  ['obliques', 'spine', [0.103, 0.09, 0.035], [0.03, 0.085, 0.055], [0, 0, 4], true],
  ['lowerback', 'spine', [0.038, 0.09, -0.084], [0.03, 0.11, 0.028], [0, 0, 0], true],
  ['glutes', 'root', [0.068, -0.045, -0.075], [0.085, 0.092, 0.07], [0, 0, 0], true],
  ['quads', 'hip', [0.0, -0.205, 0.04], [0.07, 0.175, 0.058], [0, 0, 0], true],
  ['hams', 'hip', [0.0, -0.22, -0.042], [0.06, 0.165, 0.052], [0, 0, 0], true],
  ['calves', 'knee', [0.0, -0.12, -0.035], [0.05, 0.105, 0.048], [0, 0, 0], true],
];

export const MUSCLE_GROUPS = [...new Set(MUSCLES.map((m) => m[0]))];

export const MUSCLE_LABEL = {
  chest: 'Chest', delts: 'Delts', biceps: 'Biceps', triceps: 'Triceps',
  forearms: 'Forearms / grip', lats: 'Lats', traps: 'Traps',
  upperback: 'Upper back', abs: 'Abs', obliques: 'Obliques',
  lowerback: 'Spinal erectors', glutes: 'Glutes', quads: 'Quads',
  hams: 'Hamstrings', calves: 'Calves',
};

/** Shared material set. One material per muscle group so highlighting is cheap. */
export function createMaterials({ ghost = false } = {}) {
  if (ghost) {
    const g = new THREE.MeshBasicMaterial({
      color: 0x58d6ff, transparent: true, opacity: 0.11, depthWrite: false,
    });
    const mats = { body: g, joint: g, visor: g };
    MUSCLE_GROUPS.forEach((k) => (mats[k] = g));
    return mats;
  }
  const body = new THREE.MeshPhysicalMaterial({
    color: 0x3a4354, roughness: 0.4, metalness: 0.15,
    clearcoat: 0.7, clearcoatRoughness: 0.28, sheen: 0.4, sheenColor: 0x3b4a66,
  });
  const joint = body.clone();
  joint.color = new THREE.Color(0x262c38);
  const visor = new THREE.MeshStandardMaterial({
    color: 0x0a0c10, emissive: 0x52d4ff, emissiveIntensity: 1.6, roughness: 0.2,
  });
  const mats = { body, joint, visor };
  MUSCLE_GROUPS.forEach((k) => {
    mats[k] = new THREE.MeshPhysicalMaterial({
      color: 0x566175, roughness: 0.34, metalness: 0.1,
      clearcoat: 0.85, clearcoatRoughness: 0.2,
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
    this.muscleMeshes = [];
    this.root = new THREE.Group();
    this.root.name = 'root';
    this.bones.root = this.root;
    this._build();
    this.root.traverse((o) => {
      if (o.isMesh) {
        o.castShadow = !mats.body.transparent;
        o.receiveShadow = !mats.body.transparent;
      }
    });
  }

  _bone(name, parent, pos) {
    const g = new THREE.Group();
    g.name = name;
    g.position.set(...pos);
    parent.add(g);
    this.bones[name] = g;
    return g;
  }

  _mesh(geo, mat, parent, pos = [0, 0, 0], scale = [1, 1, 1], rot = [0, 0, 0]) {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(...pos);
    m.scale.set(...scale);
    m.rotation.set(rot[0] * DEG, rot[1] * DEG, rot[2] * DEG);
    parent.add(m);
    return m;
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

    // --- Pelvis -------------------------------------------------------------
    this._mesh(torsoGeo([[0, -0.13], [0.07, -0.125], [0.12, -0.08], [0.138, -0.02],
      [0.136, 0.04], [0.125, 0.09], [0, 0.11]]), M.body, root, [0, 0, -0.005], [1, 1, 0.74]);
    this._marker('sacrum', root, [0, -0.02, -0.11]);
    this._marker('pelvis', root, [0, 0, 0]);

    // --- Lumbar / abdomen ---------------------------------------------------
    const spine = this._bone('spine', root, [0, 0.08, 0]);
    this._mesh(torsoGeo([[0, -0.04], [0.118, -0.02], [0.118, 0.06], [0.12, 0.14],
      [0.128, 0.2], [0, 0.23]]), M.body, spine, [0, 0, 0], [1, 1, 0.74]);
    this._marker('lumbar', spine, [0, 0.03, -0.1]);

    // --- Thorax -------------------------------------------------------------
    const chest = this._bone('chest', spine, [0, 0.2, 0]);
    this._mesh(torsoGeo([[0, -0.02], [0.128, 0.0], [0.14, 0.06], [0.158, 0.13],
      [0.172, 0.2], [0.168, 0.25], [0.148, 0.29], [0.1, 0.318], [0.05, 0.332], [0, 0.338]]),
    M.body, chest, [0, 0, -0.008], [1, 1, 0.64]);
    this._marker('upperBack', chest, [0, 0.17, -0.13]);
    this._marker('sternum', chest, [0, 0.16, 0.12]);
    this._marker('chestMid', chest, [0, 0.14, 0]);

    // --- Neck & head --------------------------------------------------------
    const neck = this._bone('neck', chest, [0, 0.305, -0.005]);
    this._mesh(new THREE.CapsuleGeometry(0.048, 0.07, 8, 24), M.body, neck, [0, 0.04, 0]);
    const head = this._bone('head', neck, [0, 0.09, 0]);
    this._mesh(SPHERE, M.body, head, [0, 0.1, 0.012], [0.094, 0.118, 0.106]);
    this._mesh(new THREE.SphereGeometry(1, 40, 6, Math.PI / 2 - 0.95, 1.9, 1.38, 0.24),
      M.visor, head, [0, 0.1, 0.012], [0.098, 0.122, 0.11]);
    this._marker('headTop', head, [0, 0.22, 0.01]);
    this._marker('eyes', head, [0, 0.12, 0.11]);
    this._marker('chin', head, [0, 0.0, 0.07]);

    // --- Arms (built for both sides) ---------------------------------------
    for (const s of ['L', 'R']) {
      const k = s === 'L' ? 1 : -1;
      const sh = this._bone('shoulder' + s, chest, [0.19 * k, 0.25, -0.01]);
      this._mesh(limbGeo(0.29, 0.05, 0.04, 0.006, 0.32), M.body, sh);
      const el = this._bone('elbow' + s, sh, [0, -0.29, 0]);
      this._mesh(SPHERE, M.joint, el, [0, 0, 0], [0.04, 0.04, 0.04]);
      this._mesh(limbGeo(0.26, 0.043, 0.03, 0.008, 0.25), M.body, el);
      const wr = this._bone('wrist' + s, el, [0, -0.26, 0]);
      this._mesh(SPHERE, M.body, wr, [0, -0.055, 0.004], [0.032 + 0.0, 0.058, 0.026]);
      this._marker('hand' + s, wr, [0, -0.07, 0.0]);
      this._marker('palm' + s, wr, [0, -0.07, 0.025]);

      // --- Legs ---------------------------------------------------------------
      const hip = this._bone('hip' + s, root, [0.095 * k, -0.06, 0]);
      this._mesh(limbGeo(0.44, 0.088, 0.055, 0.008, 0.25), M.body, hip);
      const kn = this._bone('knee' + s, hip, [0, -0.44, 0]);
      this._mesh(SPHERE, M.joint, kn, [0, 0, 0.012], [0.056, 0.06, 0.056]);
      this._mesh(limbGeo(0.42, 0.054, 0.034, 0.012, 0.22), M.body, kn);
      this._marker('kneeCap' + s, kn, [0, 0, 0.06]);
      const an = this._bone('ankle' + s, kn, [0, -0.42, 0]);
      this._mesh(new THREE.CapsuleGeometry(0.04, 0.17, 8, 20), M.body, an,
        [0, -0.035, 0.06], [1.1, 0.8, 1], [90, 0, 0]);
      this._marker('heel' + s, an, [0, -0.067, -0.05]);
      this._marker('toe' + s, an, [0, -0.067, 0.175]);
      this._marker('ball' + s, an, [0, -0.067, 0.12]);
      this._marker('instep' + s, an, [0, 0.0, 0.08]);
    }

    // --- Muscles ------------------------------------------------------------
    for (const [group, bone, pos, scale, rot, mirror] of MUSCLES) {
      const sides = mirror ? ['L', 'R'] : [''];
      for (const s of sides) {
        const k = s === 'R' ? -1 : 1;
        const boneName = ['shoulder', 'elbow', 'hip', 'knee'].includes(bone) ? bone + s : bone;
        const parent = this.bones[boneName];
        const p = [...pos];
        const r = [...rot];
        if (['shoulder', 'elbow', 'hip', 'knee'].includes(bone)) {
          p[0] = pos[0] * k;
          r[1] *= k; r[2] *= k;
        } else {
          p[0] = pos[0] * k;
          r[1] *= k; r[2] *= k;
        }
        const m = this._mesh(SPHERE, this.mats[group], parent, p, scale, r);
        m.userData = { group, baseScale: m.scale.clone(), side: s };
        this.muscleMeshes.push(m);
      }
    }
  }

  /**
   * Apply an expanded pose: { joint: [x,y,z] degrees }.
   * Also "flexes" muscle bellies as the joints they cross bend.
   */
  applyPose(pose) {
    for (const name of ALL_JOINTS) {
      const b = this.bones[name];
      const a = pose[name] || REST[name] || [0, 0, 0];
      if (name === 'root') {
        b.rotation.set(a[0] * DEG, a[1] * DEG, a[2] * DEG, 'YXZ');
      } else {
        b.rotation.set(a[0] * DEG, a[1] * DEG, a[2] * DEG, 'XYZ');
      }
    }
    // Muscle bulge: biceps grow with elbow flexion, quads/glutes with load, etc.
    for (const m of this.muscleMeshes) {
      const { group, baseScale, side } = m.userData;
      let f = 0;
      if (group === 'biceps') f = Math.max(0, -(pose['elbow' + side]?.[0] ?? 0)) / 140;
      else if (group === 'triceps') f = Math.max(0, 1 - Math.max(0, -(pose['elbow' + side]?.[0] ?? 0)) / 120) * 0.4;
      else if (group === 'hams') f = Math.max(0, pose['knee' + side]?.[0] ?? 0) / 160;
      else if (group === 'calves') f = Math.max(0, pose['ankle' + side]?.[0] ?? 0) / 50;
      m.scale.set(baseScale.x * (1 + f * 0.28), baseScale.y * (1 - f * 0.12), baseScale.z * (1 + f * 0.32));
    }
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
    const P = new THREE.Color(0xff4f2b);
    const S = new THREE.Color(0xffa63d);
    for (const g of MUSCLE_GROUPS) {
      const mat = this.mats[g];
      if (!mat.emissive) continue;
      if (primary.includes(g)) {
        mat.emissive.copy(P);
        mat.emissiveIntensity = 0.35 + 1.25 * intensity;
        mat.color.setHex(0x8a3a2c);
      } else if (secondary.includes(g)) {
        mat.emissive.copy(S);
        mat.emissiveIntensity = 0.15 + 0.45 * intensity;
        mat.color.setHex(0x7a5a32);
      } else {
        mat.emissive.setHex(0x000000);
        mat.color.setHex(0x566175);
      }
    }
    if (this.mats.body.emissive) {
      this.mats.body.emissive.setHex(0xff1a1a);
      this.mats.body.emissiveIntensity = faultTint * 0.12;
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
