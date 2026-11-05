// =============================================================================
// anatomy.js — the anatomical figure (Z-Anatomy / BodyParts3D) at runtime.
// -----------------------------------------------------------------------------
// Assets are produced offline by tools/anatomy (extract -> process -> pack):
//   assets/anatomy/anatomy-{economy,standard}.glb   skinned, meshopt-compressed
//   assets/anatomy/anatomy.json                     skeleton, markers, names
//
// AnatomyRig exposes the same interface as the procedural Rig in rig.js
// (bones, markers, applyPose, world, com, setHighlight, setLayer, object), so
// the Stage's contact solver, IK and exercise timelines drive it unchanged.
//
// Tissue rendering (all real-time, no texture downloads):
//   - fibre-oriented striation: a per-vertex fibre direction (converging on
//     each muscle's atlas origin/insertion) drives an anisotropic noise used as
//     a bump function; microscopic detail fades out when it would alias
//   - colour: deep red / reddish-brown variation, pale fibrous tendons and
//     aponeuroses (per-vertex tendon factor), ivory bone
//   - subsurface approximation: wavelength-dependent wrap lighting (red light
//     wraps further past the terminator), no emissive "glow"
//   - baked ambient occlusion (two variants: full / deep layer)
//   - volume-preserving contraction: each muscle's radial distance from its
//     line of action is scaled by sqrt(L0 / L), L measured live between the
//     attachment points carried by their bones
// =============================================================================
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { ALL_JOINTS } from './rig.js';

const DEG = Math.PI / 180;
const REST = {
  shoulderL: [0, 0, 7], shoulderR: [0, 0, -7],
  elbowL: [-6, 0, 0], elbowR: [-6, 0, 0],
};
const MESHES = ['muscle', 'fascia', 'bone', 'eye', 'skin'];
const STATE_W = 1024;

export const ANATOMY_CREDIT = 'Anatomy: Z-Anatomy (CC BY-SA 4.0), based on BodyParts3D © DBCLS (CC BY 4.0); adapted for FORGE.';

/** Pick the quality level for this device. */
export function chooseLOD() {
  const coarse = window.matchMedia?.('(pointer: coarse)').matches;
  const small = Math.min(window.innerWidth, window.innerHeight) < 700;
  const cores = navigator.hardwareConcurrency || 4;
  const mem = navigator.deviceMemory || 8;
  return coarse || small || cores <= 4 || mem <= 4 ? 'economy' : 'standard';
}

const cache = new Map();
/** Load (and cache) GLB + metadata for a quality level. */
export function loadAnatomyAssets(base, lod) {
  const key = base + '|' + lod;
  if (cache.has(key)) return cache.get(key);
  const p = (async () => {
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    const [gltf, meta] = await Promise.all([
      loader.loadAsync(`${base}/anatomy-${lod}.glb`),
      fetch(`${base}/anatomy.json`).then((r) => r.json()),
    ]);
    gltf.scene.updateMatrixWorld(true);
    const meshes = {};
    gltf.scene.traverse((o) => {
      if (!o.isMesh) return;
      const name = MESHES.find((m) => o.name.startsWith(m) || o.parent?.name?.startsWith(m)) || o.name;
      const g = o.geometry;
      for (const [a, b] of [['_sid', 'sid'], ['_fiber', 'fiber'], ['_musc', 'musc'], ['_ao', 'ao']]) {
        const at = g.getAttribute(a);
        if (at) { g.setAttribute(b, at); g.deleteAttribute(a); }
      }
      meshes[name] = { geometry: g, matrix: o.matrixWorld.clone() };
    });
    // Per-structure centroid and dominant segment (label anchors, picking).
    const nS = meta.structures.length;
    const sum = new Float64Array(nS * 3); const cnt = new Uint32Array(nS);
    const segVotes = new Map();
    const v = new THREE.Vector3();
    for (const { geometry, matrix } of Object.values(meshes)) {
      const pos = geometry.getAttribute('position'); const sid = geometry.getAttribute('sid');
      const ji = geometry.getAttribute('skinIndex');
      for (let i = 0; i < pos.count; i += 3) {
        const s = Math.round(sid.getX(i));
        v.fromBufferAttribute(pos, i).applyMatrix4(matrix);
        sum[s * 3] += v.x; sum[s * 3 + 1] += v.y; sum[s * 3 + 2] += v.z; cnt[s]++;
        const k = s * 64 + ji.getX(i);
        segVotes.set(k, (segVotes.get(k) || 0) + 1);
      }
    }
    meta.structures.forEach((st, s) => {
      st.centroid = cnt[s] ? [sum[s * 3] / cnt[s], sum[s * 3 + 1] / cnt[s], sum[s * 3 + 2] / cnt[s]] : [0, 1, 0];
      let best = 0; let bi = 0;
      for (let j = 0; j < meta.segments.length; j++) { const c = segVotes.get(s * 64 + j) || 0; if (c > best) { best = c; bi = j; } }
      st.anchorSeg = meta.segments[bi];
    });
    return { meshes, meta, lod };
  })();
  cache.set(key, p);
  return p;
}

// -----------------------------------------------------------------------------
// GLSL
// -----------------------------------------------------------------------------
const NOISE = /* glsl */`
float aHash(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float aNoise(vec2 p){ vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(aHash(i), aHash(i + vec2(1.0, 0.0)), u.x), mix(aHash(i + vec2(0.0, 1.0)), aHash(i + vec2(1.0, 1.0)), u.x), u.y); }
float aHash3(vec3 p){ p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float aNoise3(vec3 x){ vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(aHash3(i), aHash3(i + vec3(1,0,0)), f.x), mix(aHash3(i + vec3(0,1,0)), aHash3(i + vec3(1,1,0)), f.x), f.y),
             mix(mix(aHash3(i + vec3(0,0,1)), aHash3(i + vec3(1,0,1)), f.x), mix(aHash3(i + vec3(0,1,1)), aHash3(i + vec3(1,1,1)), f.x), f.y), f.z); }
vec3 aPerturb(vec3 surfPos, vec3 surfNorm, vec2 dHdxy, float faceDir){
  vec3 sX = dFdx(surfPos); vec3 sY = dFdy(surfPos);
  vec3 R1 = cross(sY, surfNorm); vec3 R2 = cross(surfNorm, sX);
  float det = dot(sX, R1) * faceDir;
  vec3 grad = sign(det) * (dHdxy.x * R1 + dHdxy.y * R2);
  return normalize(abs(det) * surfNorm - grad);
}`;

function patchMaterial(mat, kind, rig, S) {
  const muscle = kind === 'muscle' || kind === 'fascia';
  const sss = { muscle: [0.42, 0.16, 0.1], fascia: [0.2, 0.12, 0.08], bone: [0.18, 0.12, 0.08], skin: [0.5, 0.2, 0.12], eye: [0.1, 0.1, 0.1] }[kind];
  const m3 = new THREE.Matrix3().setFromMatrix4(S);
  const scale = new THREE.Vector3().setFromMatrixScale(S);
  mat.userData.uniforms = {
    uState: { value: rig.stateTex },
    uDeep: { value: 0 },
    uS: { value: S.clone() },
    uSN: { value: new THREE.Matrix3().getNormalMatrix(S) },
    uInvS: { value: m3.clone().invert() },
    uUnit: { value: 3 / (scale.x + scale.y + scale.z) },
    uSel: { value: new THREE.Color(0x6fd3ff) },
    uFault: { value: 0 },
    uSSSWrap: { value: new THREE.Vector3(...sss) },
    uSSSAmount: { value: kind === 'eye' ? 0 : 1 },
  };
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, mat.userData.uniforms);
    sh.defines = sh.defines || {};
    if (muscle) sh.defines.ANAT_MUSCLE = '';
    if (kind === 'eye') sh.defines.ANAT_EYE = '';
    if (kind === 'bone') sh.defines.ANAT_BONE = '';
    // ---------------------------------------------------------------- vertex
    sh.vertexShader = sh.vertexShader.replace('#include <common>', `#include <common>
attribute float sid;
attribute vec2 ao;
uniform sampler2D uState; uniform float uDeep; uniform mat4 uS; uniform mat3 uSN; uniform mat3 uInvS; uniform float uUnit;
varying float vAO; varying float vHL; varying float vVar; varying float vHide; varying vec3 vBindPos;
#ifdef ANAT_MUSCLE
attribute vec3 fiber; attribute vec4 musc;
varying vec3 vBindCross; varying vec3 vBindFiber; varying float vTendon;
#endif`);
    sh.vertexShader = sh.vertexShader.replace('#include <skinning_vertex>', `#include <skinning_vertex>
vec4 aSt = texelFetch(uState, ivec2(int(sid + 0.5), 0), 0);
vHL = aSt.g; vVar = aSt.a; vHide = aSt.b < 0.5 ? 1.0 : 0.0;
vAO = mix(ao.x, ao.y, uDeep);
vBindPos = (uS * vec4(position, 1.0)).xyz;
#ifdef ANAT_MUSCLE
  // volume-preserving contraction: thicken where the belly is, never the tendon
  float aBell = pow(max(sin(3.14159265 * musc.x), 0.0), 1.3) * (1.0 - musc.z);
  transformed += normalize(objectNormal) * (aSt.r * musc.y * 0.08 * aBell * uUnit);
  vTendon = musc.z;
  vec3 aBF = normalize(fiber);
  vec3 aBN = normalize(uSN * normal);
  vBindFiber = aBF;
  vBindCross = normalize(cross(aBN, aBF) + 1e-5);
#endif`);
    sh.vertexShader = sh.vertexShader.replace('#include <project_vertex>', `#include <project_vertex>
if (vHide > 0.5) gl_Position = vec4(0.0, 0.0, -2.0, 1.0);`);
    // -------------------------------------------------------------- fragment
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
uniform vec3 uSel; uniform float uFault; uniform vec3 uSSSWrap; uniform float uSSSAmount;
varying float vAO; varying float vHL; varying float vVar; varying float vHide; varying vec3 vBindPos;
#ifdef ANAT_MUSCLE
varying vec3 vBindCross; varying vec3 vBindFiber; varying float vTendon;
#endif
${NOISE}`);
    // wavelength-dependent wrap lighting (subsurface approximation), diffuse only
    sh.fragmentShader = sh.fragmentShader.replace('#include <lights_physical_pars_fragment>',
      THREE.ShaderChunk.lights_physical_pars_fragment.replace(
        'reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );',
        `float aNdl = dot( geometryNormal, directLight.direction );
	vec3 aWrap = saturate( ( vec3( aNdl ) + uSSSWrap ) / ( 1.0 + uSSSWrap ) );
	vec3 aIrr = mix( irradiance, aWrap * directLight.color, uSSSAmount );
	reflectedLight.directDiffuse += aIrr * BRDF_Lambert( material.diffuseColor );`));
    sh.fragmentShader = sh.fragmentShader.replace('#include <color_fragment>', `#include <color_fragment>
float aVar = aNoise3(vBindPos * 16.0) * 0.6 + aNoise3(vBindPos * 47.0) * 0.4;
#ifdef ANAT_MUSCLE
  vec3 aTissue = diffuseColor.rgb * (0.84 + 0.3 * aVar);
  aTissue = mix(aTissue, aTissue * vec3(0.86, 0.66, 0.58), smoothstep(0.5, 0.85, aVar) * 0.55); // reddish-brown
  vec3 aTendon = vec3(0.7, 0.65, 0.58) * (0.92 + 0.12 * aVar);
  float aT = smoothstep(0.12, 0.8, vTendon);
  diffuseColor.rgb = mix(aTissue, aTendon, aT);
  // exercise activation: richer, more saturated red (no glow)
  float aAct = clamp(vHL, 0.0, 1.0);
  diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * vec3(1.32, 0.78, 0.7), aAct * (1.0 - aT));
#endif
#ifdef ANAT_BONE
  diffuseColor.rgb *= 0.92 + 0.12 * aVar;
#endif
#ifdef ANAT_EYE
  if (vVar > 0.5) diffuseColor.rgb = vec3(0.24, 0.16, 0.11);
#endif
diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * vec3(1.2, 0.55, 0.55), uFault * 0.5);`);
    sh.fragmentShader = sh.fragmentShader.replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
#ifdef ANAT_MUSCLE
  roughnessFactor = clamp(mix(roughnessFactor, 0.4, smoothstep(0.12, 0.8, vTendon)) + (aVar - 0.5) * 0.08, 0.05, 1.0);
#endif`);
    sh.fragmentShader = sh.fragmentShader.replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
#ifdef ANAT_MUSCLE
{
  // anisotropic striation along the fibres: fine fibre bundles + fascicles
  float sC = dot(vBindPos, normalize(vBindCross));
  float aC = dot(vBindPos, normalize(vBindFiber));
  vec2 q1 = vec2(sC * 650.0, aC * 26.0);
  vec2 q2 = vec2(sC * 150.0, aC * 7.0);
  float l1 = clamp(1.4 - fwidth(q1.x) * 1.2, 0.0, 1.0);
  float l2 = clamp(1.4 - fwidth(q2.x) * 1.2, 0.0, 1.0);
  float tendonish = smoothstep(0.12, 0.8, vTendon);
  float h = aNoise(q1) * 0.000035 * l1 + aNoise(q2) * mix(0.00022, 0.00009, tendonish) * l2;
  normal = aPerturb(-vViewPosition, normal, vec2(dFdx(h), dFdy(h)), faceDirection);
}
#endif`);
    sh.fragmentShader = sh.fragmentShader.replace('#include <aomap_fragment>', `#include <aomap_fragment>
reflectedLight.indirectDiffuse *= vAO;
reflectedLight.indirectSpecular *= mix(1.0, vAO, 0.8);
reflectedLight.directDiffuse *= mix(1.0, vAO, 0.4);`);
    sh.fragmentShader = sh.fragmentShader.replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
if (vHL > 1.5) {
  float aFr = pow(1.0 - saturate(dot(normalize(normal), normalize(vViewPosition))), 2.5);
  totalEmissiveRadiance += uSel * (0.1 + 0.55 * aFr);
}`);
  };
  mat.customProgramCacheKey = () => 'anat-' + kind;
  return mat;
}

function depthMaterial(rig) {
  const m = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking });
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uState = { value: rig.stateTex };
    sh.vertexShader = sh.vertexShader.replace('#include <common>', `#include <common>
attribute float sid; uniform sampler2D uState;`).replace('#include <project_vertex>', `#include <project_vertex>
if (texelFetch(uState, ivec2(int(sid + 0.5), 0), 0).b < 0.5) gl_Position = vec4(0.0, 0.0, -2.0, 1.0);`);
  };
  m.customProgramCacheKey = () => 'anat-depth';
  return m;
}

// -----------------------------------------------------------------------------
// Rig
// -----------------------------------------------------------------------------
export class AnatomyRig {
  constructor(assets, { ghost = false } = {}) {
    const { meta, meshes } = assets;
    this.meta = meta;
    this.isAnatomy = true;
    this.object = new THREE.Group();
    this.bones = {};
    this.markers = {};
    this.layer = 'superficial';
    const J = meta.joints;

    // ---------------------------------------------------------------- skeleton
    const list = [];
    for (const s of meta.segments) {
      const b = new THREE.Bone();
      b.name = s;
      const p = meta.parent[s];
      const pos = new THREE.Vector3(...J[s]);
      if (p) { pos.sub(new THREE.Vector3(...J[p])); this.bones[p].add(b); } else this.object.add(b);
      b.position.copy(pos);
      this.bones[s] = b;
      list.push(b);
    }
    this.root = this.bones.root;
    this.object.updateMatrixWorld(true);
    this.skeleton = new THREE.Skeleton(list);
    this.restLocal = {};
    for (const s of meta.segments) this.restLocal[s] = this.bones[s].position.clone();

    // canonical frame alignment (limbs hang along -Y in the pose convention)
    const dirOf = (a, b) => new THREE.Vector3(...J[b]).sub(new THREE.Vector3(...J[a])).normalize();
    const down = new THREE.Vector3(0, -1, 0);
    const sagittal = (d) => { const q = new THREE.Quaternion(); q.setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.atan2(-d.z, -d.y)); return q; };
    this.Ainv = {};
    for (const s of meta.segments) this.Ainv[s] = new THREE.Quaternion();
    for (const sd of ['L', 'R']) {
      this.Ainv['shoulder' + sd] = new THREE.Quaternion().setFromUnitVectors(down, dirOf('shoulder' + sd, 'elbow' + sd)).invert();
      this.Ainv['elbow' + sd] = sagittal(dirOf('elbow' + sd, 'wrist' + sd)).invert();
      this.Ainv['hip' + sd] = sagittal(dirOf('hip' + sd, 'knee' + sd)).invert();
      this.Ainv['knee' + sd] = sagittal(dirOf('knee' + sd, 'ankle' + sd)).invert();
    }

    // ---------------------------------------------------------------- markers
    for (const [k, { seg, p }] of Object.entries(meta.markers)) {
      const o = new THREE.Object3D();
      o.position.set(p[0] - J[seg][0], p[1] - J[seg][1], p[2] - J[seg][2]);
      this.bones[seg].add(o);
      this.markers[k] = o;
    }
    // stage overlays use a few names the procedural rig had as bones
    const alias = (name, seg, p) => { const o = new THREE.Object3D(); o.position.set(p[0] - J[seg][0], p[1] - J[seg][1], p[2] - J[seg][2]); this.bones[seg].add(o); this.markers[name] = o; };
    for (const sd of ['L', 'R']) {
      alias('ankleBone' + sd, 'ankle' + sd, J['ankle' + sd]);
    }

    // ---------------------------------------------------------------- state
    this.state = new Float32Array(STATE_W * 4);
    for (let i = 0; i < STATE_W; i++) this.state[i * 4 + 2] = 1; // visible
    meta.structures.forEach((s, i) => { if (/iris/i.test(s.name)) this.state[i * 4 + 3] = 1; });
    this.stateTex = new THREE.DataTexture(this.state, STATE_W, 1, THREE.RGBAFormat, THREE.FloatType);
    this.stateTex.needsUpdate = true;

    // ---------------------------------------------------------------- meshes
    const mk = (kind) => {
      if (ghost) {
        return new THREE.MeshBasicMaterial({ color: 0x8fd8ff, transparent: true, opacity: 0.09, depthWrite: false });
      }
      const base = {
        muscle: { color: 0x7e231b, roughness: 0.5, sheen: 0.35, sheenRoughness: 0.45, sheenColor: 0xd3958a, clearcoat: 0.1, clearcoatRoughness: 0.45, specularIntensity: 0.45 },
        fascia: { color: 0x7e231b, roughness: 0.45, sheen: 0.4, sheenRoughness: 0.4, sheenColor: 0xe6d8cc, clearcoat: 0.12, clearcoatRoughness: 0.4, specularIntensity: 0.5 },
        bone: { color: 0xcdbfa6, roughness: 0.62, specularIntensity: 0.35, sheen: 0.15, sheenColor: 0xffffff },
        eye: { color: 0xf0ebe5, roughness: 0.16, clearcoat: 1, clearcoatRoughness: 0.08 },
        skin: { color: 0xc48e74, roughness: 0.55, sheen: 0.5, sheenRoughness: 0.5, sheenColor: 0xffc6ad, specularIntensity: 0.45 },
      }[kind];
      return new THREE.MeshPhysicalMaterial({ metalness: 0, ...base });
    };
    this.mats = {};
    this.meshes = {};
    this.depthMat = ghost ? null : depthMaterial(this);
    for (const kind of MESHES) {
      const src = meshes[kind];
      if (!src) continue;
      const mat = mk(kind);
      if (!ghost) patchMaterial(mat, kind, this, src.matrix);
      const m = new THREE.SkinnedMesh(src.geometry, mat);
      m.matrixAutoUpdate = false;
      m.matrix.copy(src.matrix);
      m.bind(this.skeleton, src.matrix);
      m.frustumCulled = false;
      m.castShadow = !ghost && kind !== 'eye';
      m.receiveShadow = !ghost;
      if (this.depthMat) m.customDepthMaterial = this.depthMat;
      m.userData.kind = kind;
      this.object.add(m);
      this.mats[kind] = mat;
      this.meshes[kind] = m;
    }
    this.object.updateMatrixWorld(true);

    // ---------------------------------------------------------------- muscles
    this.groupSids = {};
    this.muscles = [];
    meta.structures.forEach((s, i) => {
      if (s.group) (this.groupSids[s.group] = this.groupSids[s.group] || []).push(i);
      if (s.O && s.I && s.L0 > 0.02) {
        this.muscles.push({ sid: i, O: new THREE.Vector3(...s.O), I: new THREE.Vector3(...s.I), L0: s.L0, a: meta.segments.indexOf(s.segO), b: meta.segments.indexOf(s.segI) });
      }
    });
    this._tmpM = new THREE.Matrix4();
    this.setLayer(ghost ? 'ghost' : 'superficial');
  }

  // --------------------------------------------------------------------------- posing
  applyPose(pose) {
    const q = new THREE.Quaternion(); const e = new THREE.Euler();
    const R = {};
    for (const name of ALL_JOINTS) {
      const a = pose[name] || REST[name] || [0, 0, 0];
      e.set(a[0] * DEG, a[1] * DEG, a[2] * DEG, name === 'root' ? 'YXZ' : 'XYZ');
      R[name] = new THREE.Quaternion().setFromEuler(e);
    }
    // scapulohumeral rhythm: the shoulder girdle follows ~22% of arm motion,
    // so raised arms lift and rotate the shoulder instead of pinching it.
    for (const sd of ['L', 'R']) {
      const sh = R['shoulder' + sd];
      const sc = new THREE.Quaternion().slerp(sh, 0.22);
      R['scap' + sd] = sc;
      R['shoulder' + sd] = sc.clone().invert().multiply(sh);
    }
    const W = {}; const G = {};
    for (const s of this.meta.segments) {
      const p = this.meta.parent[s];
      W[s] = p ? W[p].clone().multiply(R[s] || q.identity()) : (R[s] || new THREE.Quaternion()).clone();
      G[s] = W[s].clone().multiply(this.Ainv[s]);
      const b = this.bones[s];
      if (p) b.quaternion.copy(G[p]).invert().multiply(G[s]);
      else b.quaternion.copy(G[s]);
    }
  }

  /** Measure every muscle's current length and set its contraction. */
  updateContraction() {
    this.object.updateMatrixWorld(true);
    const bm = this.skeleton.bones; const inv = this.skeleton.boneInverses;
    const o = new THREE.Vector3(); const i = new THREE.Vector3(); const M = this._tmpM;
    for (const m of this.muscles) {
      o.copy(m.O).applyMatrix4(M.multiplyMatrices(bm[m.a].matrixWorld, inv[m.a]));
      i.copy(m.I).applyMatrix4(M.multiplyMatrices(bm[m.b].matrixWorld, inv[m.b]));
      const L = o.distanceTo(i);
      this.state[m.sid * 4] = THREE.MathUtils.clamp(Math.sqrt(m.L0 / Math.max(L, 1e-3)) - 1, -0.14, 0.32);
    }
    this.stateTex.needsUpdate = true;
  }

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

  /** Posed position of a structure's centroid (label anchor). */
  structureAnchor(sid, target = new THREE.Vector3()) {
    const s = this.meta.structures[sid];
    const k = this.meta.segments.indexOf(s.anchorSeg);
    const M = this._tmpM.multiplyMatrices(this.skeleton.bones[k].matrixWorld, this.skeleton.boneInverses[k]);
    return target.set(...s.centroid).applyMatrix4(M);
  }

  com(target = new THREE.Vector3()) {
    const S = [['pelvis', 'spine', 0.14], ['spine', 'chest', 0.13], ['chest', 'neck', 0.2], ['head', 'headTop', 0.08]];
    for (const s of ['L', 'R']) {
      S.push(['shoulder' + s, 'elbow' + s, 0.028], ['elbow' + s, 'wrist' + s, 0.016], ['wrist' + s, 'hand' + s, 0.006],
        ['hip' + s, 'knee' + s, 0.1], ['knee' + s, 'ankle' + s, 0.047], ['ankle' + s, 'toe' + s, 0.014]);
    }
    target.set(0, 0, 0);
    let m = 0;
    const a = new THREE.Vector3(); const b = new THREE.Vector3();
    for (const [p, q, w] of S) { this.world(p, a); this.world(q, b); target.addScaledVector(a.add(b).multiplyScalar(0.5), w); m += w; }
    return target.multiplyScalar(1 / m);
  }

  // --------------------------------------------------------------------------- appearance
  setHighlight(primary = [], secondary = [], intensity = 1, faultTint = 0) {
    const st = this.state;
    for (let i = 0; i < this.meta.structures.length; i++) if (st[i * 4 + 1] < 1.5) st[i * 4 + 1] = 0;
    const set = (g, v) => { for (const sid of this.groupSids[g] || []) if (st[sid * 4 + 1] < 1.5) st[sid * 4 + 1] = v; };
    for (const g of secondary) set(g, 0.35 * intensity);
    for (const g of primary) set(g, 0.55 + 0.45 * intensity);
    for (const m of Object.values(this.mats)) if (m.userData.uniforms) m.userData.uniforms.uFault.value = faultTint;
    this.stateTex.needsUpdate = true;
  }

  /** 'skin' | 'superficial' | 'deep' | 'skeleton' */
  setLayer(mode) {
    this.layer = mode;
    const st = this.state;
    const meta = this.meta;
    const iso = this.isolated;
    meta.structures.forEach((s, i) => {
      let vis = true;
      if (mode === 'deep' && s.superficial) vis = false;
      if (mode === 'skeleton' && (s.type === 'muscle' || s.type === 'fascia')) vis = false;
      if (iso != null && (s.type === 'muscle' || s.type === 'fascia') && i !== iso) vis = false;
      st[i * 4 + 2] = vis ? 1 : 0;
    });
    this.stateTex.needsUpdate = true;
    for (const [kind, m] of Object.entries(this.meshes)) {
      if (mode === 'ghost') { m.visible = kind !== 'skin' && kind !== 'eye'; continue; }
      if (kind === 'skin') m.visible = mode === 'skin';
      else if (kind === 'eye') m.visible = true;
      else m.visible = mode !== 'skin';
    }
    for (const m of Object.values(this.mats)) if (m.userData.uniforms) m.userData.uniforms.uDeep.value = mode === 'deep' || mode === 'skeleton' ? 1 : 0;
  }

  // --------------------------------------------------------------------------- inspection
  select(sid) {
    const st = this.state;
    if (this.selected != null) st[this.selected * 4 + 1] = 0;
    this.selected = sid;
    if (sid != null) st[sid * 4 + 1] = 2;
    this.stateTex.needsUpdate = true;
  }

  isolate(on) {
    this.isolated = on ? this.selected : null;
    this.setLayer(this.layer === 'skin' ? 'superficial' : this.layer);
  }

  /** Raycast the visible anatomy; returns the structure id or null. */
  pick(raycaster) {
    const targets = ['muscle', 'fascia', 'bone', 'eye'].map((k) => this.meshes[k]).filter((m) => m && m.visible);
    const hits = raycaster.intersectObjects(targets, false);
    for (const h of hits) {
      const sid = Math.round(h.object.geometry.getAttribute('sid').getX(h.face.a));
      if (this.state[sid * 4 + 2] > 0.5) return sid;
    }
    return null;
  }
}
