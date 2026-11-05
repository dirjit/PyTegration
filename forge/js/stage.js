// =============================================================================
// stage.js — renderer, studio lighting, props, contact solver and overlays.
// -----------------------------------------------------------------------------
// The contact solver is what makes the animation believable: authored poses
// only describe joint angles; each frame we translate (and if needed rotate)
// the whole body so that the contact points the exercise declares — feet on
// the floor, hands on the bar, upper back on the mat — stay planted exactly.
// =============================================================================
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import {
  Rig, createMaterials, expandPose, expandDelta, addPose, lerpPose, DEG, SIDE_JOINTS,
} from './rig.js';
import { AnatomyRig } from './anatomy.js';

const tmpV = new THREE.Vector3();
const tmpV2 = new THREE.Vector3();
const tmpQ = new THREE.Quaternion();
const X_AXIS = new THREE.Vector3(1, 0, 0);

const ease = {
  inOut: (t) => t * t * t * (t * (t * 6 - 15) + 10),
  out: (t) => 1 - Math.pow(1 - t, 3),
  in: (t) => t * t * t,
  lin: (t) => t,
  // explosive concentric: fast start, gentle finish
  snap: (t) => 1 - Math.pow(1 - t, 4),
  // concentric drive: zero velocity at both ends, peak early (t = 1/3)
  drive: (t) => 1 - Math.pow(1 - t, 3) * (1 + 3 * t),
  driveIn: (t) => t * t * t * (4 - 3 * t),
};

// -----------------------------------------------------------------------------
// Props
// -----------------------------------------------------------------------------
function steelMat() {
  return new THREE.MeshPhysicalMaterial({ color: 0x9aa4b5, metalness: 0.95, roughness: 0.22, clearcoat: 0.4 });
}
function rubberMat(c = 0x16191f) {
  return new THREE.MeshStandardMaterial({ color: c, roughness: 0.85, metalness: 0.0 });
}

function cyl(r, len, mat, axis = 'y') {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, len, 28), mat);
  if (axis === 'x') m.rotation.z = Math.PI / 2;
  if (axis === 'z') m.rotation.x = Math.PI / 2;
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

function buildProps() {
  const steel = steelMat();
  const dark = rubberMat(0x1a1e26);
  const props = {};

  // Overhead bar (pull-ups, hanging leg raises, inverted rows)
  const bar = new THREE.Group();
  bar.userData.update = (y) => {
    bar.clear();
    bar.add(cyl(0.017, 1.5, steel, 'x'));
    for (const s of [-1, 1]) {
      const post = cyl(0.03, y + 0.06, dark);
      post.position.set(s * 0.75, -(y + 0.06) / 2 + 0.03, 0);
      bar.add(post);
      const foot = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.03, 0.7), dark);
      foot.position.set(s * 0.75, -y + 0.015, 0);
      foot.castShadow = foot.receiveShadow = true;
      bar.add(foot);
    }
  };
  props.bar = bar;

  // Parallel dip bars
  const dip = new THREE.Group();
  dip.userData.update = (y, x) => {
    dip.clear();
    for (const s of [-1, 1]) {
      const rail = cyl(0.02, 0.9, steel, 'z');
      rail.position.set(s * x, 0, 0);
      dip.add(rail);
      for (const z of [-0.42, 0.42]) {
        const post = cyl(0.025, y, dark);
        post.position.set(s * x, -y / 2, z);
        dip.add(post);
      }
    }
  };
  props.dip = dip;

  // Flat bench (Bulgarian split squat)
  const bench = new THREE.Group();
  const pad = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.07, 0.5), rubberMat(0x2a1714));
  pad.castShadow = pad.receiveShadow = true;
  bench.add(pad);
  bench.userData.update = (h) => {
    while (bench.children.length > 1) bench.remove(bench.children[1]);
    pad.position.y = -0.035;
    for (const z of [-0.18, 0.18]) {
      const leg = cyl(0.02, h - 0.07, dark);
      leg.position.set(0, -(h - 0.07) / 2 - 0.07, z);
      bench.add(leg);
    }
  };
  props.bench = bench;

  // Mat
  const mat = new THREE.Mesh(
    new THREE.BoxGeometry(0.62, 0.01, 1.85),
    new THREE.MeshStandardMaterial({ color: 0x1d2a33, roughness: 0.9 }),
  );
  mat.receiveShadow = true;
  props.mat = mat;

  // Dumbbells (attached to the hands)
  const makeDB = () => {
    const g = new THREE.Group();
    g.add(cyl(0.014, 0.16, steel, 'z'));
    for (const s of [-1, 1]) {
      const plate = cyl(0.05, 0.05, rubberMat(0x111318), 'z');
      plate.position.z = s * 0.1;
      g.add(plate);
    }
    return g;
  };
  props.dbL = makeDB();
  props.dbR = makeDB();

  // Kettlebell
  const kb = new THREE.Group();
  const bell = new THREE.Mesh(new THREE.SphereGeometry(0.1, 32, 24), rubberMat(0x15171c));
  bell.position.y = -0.14; bell.scale.y = 0.95; bell.castShadow = true;
  const handle = new THREE.Mesh(new THREE.TorusGeometry(0.055, 0.012, 12, 32, Math.PI), steel);
  handle.rotation.z = Math.PI; handle.position.y = -0.03; handle.castShadow = true;
  kb.add(bell, handle);
  props.kb = kb;

  return props;
}

// -----------------------------------------------------------------------------
// Overlay helpers (thick segments rendered on top of everything)
// -----------------------------------------------------------------------------
class Segment {
  constructor(color, radius = 0.007) {
    this.mat = new THREE.MeshBasicMaterial({ color, depthTest: false, transparent: true, opacity: 0.95 });
    this.mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, 1, 10, 1, true), this.mat);
    this.mesh.renderOrder = 999;
  }
  set(a, b) {
    const d = tmpV.subVectors(b, a);
    const len = d.length();
    this.mesh.position.addVectors(a, b).multiplyScalar(0.5);
    this.mesh.scale.set(1, Math.max(len, 1e-4), 1);
    this.mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize());
  }
}

function dot(color, r = 0.018) {
  const m = new THREE.Mesh(
    new THREE.SphereGeometry(r, 16, 12),
    new THREE.MeshBasicMaterial({ color, depthTest: false, transparent: true }),
  );
  m.renderOrder = 1000;
  return m;
}

// -----------------------------------------------------------------------------
// Stage
// -----------------------------------------------------------------------------
export class Stage {
  constructor(container, opts = {}) {
    this.container = container;
    this.opts = { hero: false, ...opts };
    this.speed = 1;
    this.playing = true;
    this.time = 0;
    this.rep = 0;
    this.toggles = { angles: true, line: true, trace: true, ghosts: false, fault: false };
    this.listeners = [];
    this.visible = true;

    const w = container.clientWidth || 800;
    const h = container.clientHeight || 600;

    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, this.opts.pixelRatio || 2));
    renderer.setSize(w, h);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.AgXToneMapping; // filmic, keeps deep reds from going pink
    renderer.toneMappingExposure = 1.1;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);
    this.renderer = renderer;

    const scene = new THREE.Scene();
    scene.background = studioBackdrop();
    scene.fog = new THREE.Fog(0x1d1e21, 9, 20);
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.55;
    this.scene = scene;

    const camera = new THREE.PerspectiveCamera(this.opts.hero ? 32 : 36, w / h, 0.05, 60);
    camera.position.set(3.2, 1.7, 3.4);
    this.camera = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 1.6;
    controls.maxDistance = 9;
    controls.maxPolarAngle = Math.PI * 0.495;
    controls.target.set(0, 1, 0);
    controls.enablePan = !this.opts.hero;
    controls.screenSpacePanning = true;
    controls.minDistance = 0.45;
    if (this.opts.hero) {
      controls.enableZoom = false;
      controls.autoRotate = true;
      controls.autoRotateSpeed = 0.6;
    }
    controls.addEventListener('start', () => (this.camTween = null));
    this.controls = controls;

    this._lights();
    this._floor();

    this.props = buildProps();
    Object.values(this.props).forEach((p) => (p.visible = false));
    ['bar', 'dip', 'bench', 'mat', 'kb'].forEach((k) => scene.add(this.props[k]));

    this.mats = createMaterials();
    this.rig = new Rig(this.mats);
    scene.add(this.rig.object);
    this.rig.bones.wristL.add(this.props.dbL);
    this.rig.bones.wristR.add(this.props.dbR);
    this.props.dbL.position.set(0, -0.07, 0.01);
    this.props.dbR.position.set(0, -0.07, 0.01);

    if (!this.opts.hero) {
      const gm = createMaterials({ ghost: true });
      this.ghosts = [new Rig(gm), new Rig(gm)];
      this.ghosts.forEach((g) => { g.object.visible = false; scene.add(g.object); });
    } else {
      this.ghosts = [];
    }

    this._overlays();

    // Post-processing: multisampled render + output (tone mapping, sRGB).
    // No bloom or depth-of-field: anatomy stays sharp everywhere.
    const rt = new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, samples: 4 });
    const composer = new EffectComposer(renderer, rt);
    composer.addPass(new RenderPass(scene, camera));
    composer.addPass(new OutputPass());
    this.composer = composer;
    this._frameTimes = [];
    this.quality = 1;

    this.labelLayer = document.createElement('div');
    this.labelLayer.className = 'label-layer';
    container.appendChild(this.labelLayer);
    this.labels = [];

    this.clock = new THREE.Clock();
    this._resize = this._resize.bind(this);
    new ResizeObserver(this._resize).observe(container);
    const io = new IntersectionObserver((e) => { this.visible = e[0].isIntersecting; });
    io.observe(container);
    renderer.setAnimationLoop(() => this._tick());
  }

  _lights() {
    // Soft studio rig: large warm-neutral key with soft shadows, cool fill,
    // separating rim and a little sky/ground bounce. Shading stays readable
    // in both shadows and highlights.
    const s = this.scene;
    s.add(new THREE.HemisphereLight(0xdfe4ea, 0x2a2622, 0.45));
    const key = new THREE.DirectionalLight(0xfff4ea, 2.4);
    key.position.set(2.2, 4.6, 3.4);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.left = -2.2; key.shadow.camera.right = 2.2;
    key.shadow.camera.top = 2.8; key.shadow.camera.bottom = -1.2;
    key.shadow.camera.near = 0.5; key.shadow.camera.far = 14;
    key.shadow.bias = -0.0003;
    key.shadow.normalBias = 0.012;
    key.shadow.radius = 6;
    key.shadow.blurSamples = 16;
    s.add(key);
    this.keyLight = key;
    const fill = new THREE.DirectionalLight(0xe6eef8, 0.9);
    fill.position.set(-3.2, 1.8, 2.6);
    s.add(fill);
    const rim = new THREE.DirectionalLight(0xffffff, 1.25);
    rim.position.set(-1.5, 3.2, -4);
    s.add(rim);
    const rim2 = new THREE.DirectionalLight(0xf4efe9, 0.6);
    rim2.position.set(3.5, 1.4, -3);
    s.add(rim2);
  }

  _floor() {
    // Quiet neutral floor: soft radial falloff, faint grid, contact shadows.
    const c = document.createElement('canvas');
    c.width = c.height = 1024;
    const g = c.getContext('2d');
    const grd = g.createRadialGradient(512, 512, 30, 512, 512, 512);
    grd.addColorStop(0, '#38393d');
    grd.addColorStop(0.5, '#2a2b2e');
    grd.addColorStop(1, '#1d1e21');
    g.fillStyle = grd;
    g.fillRect(0, 0, 1024, 1024);
    g.strokeStyle = 'rgba(255,255,255,0.035)';
    g.lineWidth = 1;
    for (let i = 0; i <= 1024; i += 32) {
      g.beginPath(); g.moveTo(i, 0); g.lineTo(i, 1024); g.stroke();
      g.beginPath(); g.moveTo(0, i); g.lineTo(1024, i); g.stroke();
    }
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(8, 96),
      new THREE.MeshStandardMaterial({ map: tex, roughness: 0.92, metalness: 0 }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    this.scene.add(floor);
  }

  _overlays() {
    this.overlay = new THREE.Group();
    this.scene.add(this.overlay);
    this.lineSegs = [new Segment(0x3dff9a, 0.004), new Segment(0x3dff9a, 0.004)];
    this.lineSegs.forEach((sg) => (sg.mat.opacity = 0.7));
    this.lineSegs.forEach((s) => this.overlay.add(s.mesh));
    this.lineDots = [dot(0xffffff, 0.02), dot(0xffffff, 0.02), dot(0xffffff, 0.02)];
    this.lineDots.forEach((d) => this.overlay.add(d));

    this.angleSegs = [];
    for (let i = 0; i < 6; i++) {
      const s = new Segment(0xffd166, 0.0025);
      s.mat.opacity = 0.6;
      this.angleSegs.push(s);
      this.overlay.add(s.mesh);
    }
    this.angleDots = [];
    for (let i = 0; i < 3; i++) {
      const d = dot(0xffd166, 0.012);
      this.angleDots.push(d);
      this.overlay.add(d);
    }

    // Motion trace: a fading ribbon of points following a key landmark.
    this.traceN = 140;
    this.tracePos = new Float32Array(this.traceN * 3);
    this.traceCol = new Float32Array(this.traceN * 3);
    const tg = new THREE.BufferGeometry();
    tg.setAttribute('position', new THREE.BufferAttribute(this.tracePos, 3));
    tg.setAttribute('color', new THREE.BufferAttribute(this.traceCol, 3));
    this.trace = new THREE.Line(tg, new THREE.LineBasicMaterial({
      vertexColors: true, transparent: true, depthTest: false, opacity: 0.95,
    }));
    this.trace.renderOrder = 998;
    this.trace.frustumCulled = false;
    this.overlay.add(this.trace);
    this.tracePts = new THREE.Points(tg, new THREE.PointsMaterial({
      size: 0.022, vertexColors: true, transparent: true, depthTest: false,
    }));
    this.tracePts.renderOrder = 998;
    this.tracePts.frustumCulled = false;
    this.overlay.add(this.tracePts);
    this.traceHistory = [];
  }

  on(fn) { this.listeners.push(fn); }

  /**
   * Replace the placeholder figure with the anatomical model. Geometry is
   * shared; each Stage gets its own skeleton, materials and state texture.
   */
  useAnatomy(assets, ghostAssets = assets) {
    const old = this.rig;
    this.scene.remove(old.object);
    this.rig = new AnatomyRig(assets);
    this.scene.add(this.rig.object);
    this.rig.bones.wristL.add(this.props.dbL);
    this.rig.bones.wristR.add(this.props.dbR);
    for (const s of ['L', 'R']) {
      const db = this.props['db' + s];
      db.position.copy(this.rig.markers['hand' + s].position);
      db.rotation.set(0, Math.PI / 2, 0);
    }
    this.rig.meshes.muscle && Object.values(this.rig.meshes).forEach((m) => m.layers.enable(1));
    if (this.ghosts.length) {
      this.ghosts.forEach((g) => this.scene.remove(g.object));
      this.ghosts = [new AnatomyRig(ghostAssets, { ghost: true }), new AnatomyRig(ghostAssets, { ghost: true })];
      this.ghosts.forEach((g) => { g.object.visible = false; this.scene.add(g.object); });
    }
    if (this._layer) this.rig.setLayer(this._layer);
    if (this.ex) this.setExercise(this.ex, { keepTime: true, transition: true });
    this.anatomy = true;
  }

  /** GPU picking: which anatomical structure is under this canvas point? */
  pick(clientX, clientY) {
    if (!this.rig.isAnatomy) return null;
    if (!this._pick) {
      const target = new THREE.WebGLRenderTarget(1, 1);
      const mat = new THREE.MeshBasicMaterial();
      mat.onBeforeCompile = (sh) => {
        sh.uniforms.uState = { value: this.rig.stateTex };
        mat.userData.sh = sh;
        sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nattribute float sid; uniform sampler2D uState; flat varying float vSid;')
          .replace('#include <project_vertex>', '#include <project_vertex>\nvSid = sid; if (texelFetch(uState, ivec2(int(sid + 0.5), 0), 0).b < 0.5) gl_Position = vec4(0.0, 0.0, -2.0, 1.0);');
        sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nflat varying float vSid;')
          .replace('vec4 diffuseColor = vec4( diffuse, opacity );', 'float id = vSid + 1.0; vec4 diffuseColor = vec4( mod(id, 256.0) / 255.0, floor(id / 256.0) / 255.0, 0.0, 1.0 );');
      };
      mat.toneMapped = false;
      this._pick = { target, mat, buf: new Uint8Array(4) };
    }
    const { target, mat, buf } = this._pick;
    if (mat.userData.sh) mat.userData.sh.uniforms.uState.value = this.rig.stateTex;
    const r = this.renderer.domElement.getBoundingClientRect();
    const x = clientX - r.left; const y = clientY - r.top;
    const cam = this.camera;
    cam.setViewOffset(r.width, r.height, x, y, 1, 1);
    cam.layers.set(1);
    const prevBg = this.scene.background; const prevOv = this.scene.overrideMaterial;
    this.scene.background = null; this.scene.overrideMaterial = mat;
    const prevTM = this.renderer.toneMapping; this.renderer.toneMapping = THREE.NoToneMapping;
    const prevCS = this.renderer.outputColorSpace;
    this.renderer.setRenderTarget(target);
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.clear();
    this.renderer.render(this.scene, cam);
    this.renderer.readRenderTargetPixels(target, 0, 0, 1, 1, buf);
    this.renderer.setRenderTarget(null);
    this.renderer.toneMapping = prevTM; this.renderer.outputColorSpace = prevCS;
    this.scene.background = prevBg; this.scene.overrideMaterial = prevOv;
    cam.clearViewOffset(); cam.layers.set(0);
    const id = buf[0] + buf[1] * 256 - 1;
    return id >= 0 ? id : null;
  }

  select(sid) {
    if (!this.rig.isAnatomy) return;
    this.rig.select(sid);
    this.selected = sid;
  }

  // ---------------------------------------------------------------------------
  // Exercise setup
  // ---------------------------------------------------------------------------
  setExercise(ex, { keepTime = false, transition = false } = {}) {
    this.ex = ex;
    this.poses = ex.poses.map(expandPose);
    this.faultPoses = ex.fault
      ? this.poses.map((p, i) => addPose(p, expandDelta(ex.fault.delta[i] || ex.fault.delta[0] || {})))
      : this.poses;
    this.cycle = ex.tempo.reduce((s, seg) => s + seg.dur, 0);
    if (this.rig.setGrip) this.rig.setGrip(ex.grip ?? 0.18);
    if (this.rig.setPronation) this.rig.setPronation(ex.pron ?? 90);
    this.ghosts.forEach((g) => g.setPronation?.(ex.pron ?? 90));
    this.ghosts.forEach((g) => g.setGrip?.(ex.grip ?? 0.18));
    if (!keepTime) { this.time = 0; this.rep = 0; }
    this.traceHistory = [];

    // Props
    const P = this.props;
    Object.values(P).forEach((p) => (p.visible = false));
    (ex.props || []).forEach((k) => { if (P[k]) P[k].visible = true; });
    if (ex.props?.includes('db')) { P.dbL.visible = P.dbR.visible = true; }

    // Solve pose 0 once to place static props (and the IK target) correctly.
    this.ikTasks = null;
    this.rig._ik = [];
    this.ghosts.forEach((g) => (g._ik = []));
    this.lockQ = null;
    this._pose(this.poses[0], this.rig, false);
    const r = this.rig;
    if (ex.lockFeet) {
      this.lockQ = {};
      for (const s of ex.lockFeet) this.lockQ[s] = r.bones['ankle' + s].getWorldQuaternion(new THREE.Quaternion());
    }
    if (ex.ik) {
      this.ikTasks = [].concat(ex.ik).map((t) => {
        const joints = [].concat(t.joints);
        const dims = t.dims || ['z'];
        const p0 = r.world(t.point);
        return {
          joints, dims, point: t.point, axes: t.axes || joints.map(() => 0),
          names: joints.map((j) => (SIDE_JOINTS.includes(j) ? [j + 'L', j + 'R'] : [j])),
          target: dims.map((d) => p0[d]),
        };
      });
    }
    if (ex.props?.includes('bar')) {
      const h = r.world('mid:handL,handR');
      P.bar.position.copy(h);
      P.bar.userData.update(h.y);
    }
    if (ex.props?.includes('dip')) {
      const a = r.world('handL'); const b = r.world('handR');
      P.dip.position.set((a.x + b.x) / 2, a.y - 0.02, a.z);
      P.dip.userData.update(a.y - 0.02, Math.abs(a.x - b.x) / 2);
    }
    if (ex.props?.includes('bench')) {
      const i = r.world(ex.benchFoot || 'instepR');
      P.bench.position.set(i.x, i.y - 0.035, i.z - 0.12);
      P.bench.userData.update(i.y - 0.035);
    }
    if (ex.props?.includes('mat')) {
      const c = r.world('pelvis');
      P.mat.position.set(0, 0.005, ex.matZ ?? c.z);
    }

    // Ghosts: show the two extremes of the range of motion.
    if (this.ghosts.length) {
      const ends = ex.romPoses || [0, 1];
      this.ghosts.forEach((g, i) => this._pose(this.poses[ends[i]], g));
    }
    this._applyGhostVisibility();

    this._frame();
    if (transition && this._hasView) {
      // Keep the current orbit angle, just re-fit distance and target.
      const dir = this.camera.position.clone().sub(this.controls.target).normalize();
      const to = this._center.clone().add(dir.multiplyScalar(this._fitDistance()));
      to.y = Math.max(0.2, to.y);
      this.camTween = { from: this.camera.position.clone(), to, t: 0 };
    } else {
      this.setView(ex.view || 'threeQuarter', true);
    }
    this._hasView = true;
  }

  /** Sample the whole rep and frame the camera on the union bounding box. */
  _frame() {
    const box = new THREE.Box3();
    const pts = this.ex.frame || ['headTop', 'toeL', 'toeR', 'heelL', 'heelR', 'handL', 'handR', 'kneeCapL', 'kneeCapR', 'pelvis', 'sacrum', 'elbowL', 'elbowR'];
    const v = new THREE.Vector3();
    const src = this.poses;
    for (let k = 0; k < 10; k++) {
      const s = this._sample((k / 10) * this.cycle);
      this._pose(lerpPose(src[s.seg.from], src[s.seg.to], s.e), this.rig);
      for (const n of pts) box.expandByPoint(this.rig.world(n, v));
    }
    this.rig._ik = [];
    this._center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    this._radius = Math.max(this.ex.frame ? 0.32 : 0.7, 0.5 * Math.hypot(size.x, size.y, size.z));
  }

  _fitDistance() {
    const vf = (this.camera.fov * DEG) / 2;
    const hf = Math.atan(Math.tan(vf) * this.camera.aspect);
    const f = Math.min(vf, hf);
    return (this._radius / Math.sin(f)) * (this.opts.hero ? 1.05 : 1.3);
  }

  _applyGhostVisibility() {
    this.ghosts.forEach((g) => (g.object.visible = this.toggles.ghosts && !!this.ex));
  }

  setLayer(mode) {
    this._layer = mode;
    this.rig.setLayer(mode);
  }

  setToggle(k, v) {
    this.toggles[k] = v;
    if (k === 'ghosts') this._applyGhostVisibility();
    if (k === 'trace') this.traceHistory = [];
  }

  setView(name, instant = false) {
    const c = this._center || new THREE.Vector3(0, 1, 0);
    const d = this._radius ? this._fitDistance() : 4;
    const views = {
      front: [0, 0.12, 1],
      side: [1, 0.08, 0.001],
      threeQuarter: [0.68, 0.22, 0.72],
      back: [-0.55, 0.28, -0.8],
      top: [0.12, 1, 0.18],
      low: [0.8, -0.12, 0.55],
    };
    let dir = views[name] || views.threeQuarter;
    // Bar exercises: shift the side view off the posts' line of sight.
    if (name === 'side' && this.ex?.props?.includes('bar')) dir = [1, 0.1, 0.42];
    const v = new THREE.Vector3(...dir).normalize().multiplyScalar(d);
    const to = new THREE.Vector3(c.x + v.x, Math.max(0.2, c.y + v.y), c.z + v.z);
    this.view = name;
    if (instant) {
      this.camera.position.copy(to);
      this.controls.target.copy(c);
      this.camTween = null;
    } else {
      this.camTween = { from: this.camera.position.clone(), to, t: 0 };
    }
  }

  // ---------------------------------------------------------------------------
  // Pose + contact solver
  // ---------------------------------------------------------------------------
  _pose(pose, rig, useIK = true) {
    const ex = this.ex;
    const run = (p) => { rig.applyPose(p); this._contacts(rig); };
    if (!useIK || !this.ikTasks) { run(pose); return; }
    const tmp = { ...pose };
    rig._ik = rig._ik || [];
    // Damped Gauss-Newton on 1–2 joint angles per task so a contact point
    // (hands on the floor, rear foot on the bench, heel on the mat) stays
    // pinned while the rest of the body moves through the rep.
    this.ikTasks.forEach((task, ti) => {
      const n = task.joints.length;
      const v = new THREE.Vector3();
      const evalAt = (params) => {
        for (const name of task.names.flat()) tmp[name] = [...pose[name]];
        task.joints.forEach((j, k) => {
          const ax = task.axes[k];
          for (const name of task.names[k]) tmp[name][ax] += params[k] * (ax && name.endsWith('R') ? -1 : 1);
        });
        run(tmp);
        rig.world(task.point, v);
        return task.dims.map((d, k) => v[d] - task.target[k]);
      };
      const solve = (start) => {
        let p = [...start];
        let r = evalAt(p);
        for (let it = 0; it < 6; it++) {
          const err = Math.hypot(...r);
          if (err < 4e-4) break;
          const h = 0.5;
          const J = [];
          for (let k = 0; k < n; k++) {
            const q = [...p]; q[k] += h;
            const rq = evalAt(q);
            J.push(rq.map((x, i) => (x - r[i]) / h));
          }
          let step;
          if (n === 1) step = [-r[0] / (J[0][0] || 1e-6)];
          else {
            // J columns per param -> solve 2x2 with light damping
            const a = J[0][0], b = J[1][0], c = J[0][1], d = J[1][1];
            const lam = 1e-5;
            const det = (a * d - b * c) || lam;
            step = [(-r[0] * d + r[1] * b) / det, (r[0] * c - r[1] * a) / det];
          }
          p = p.map((x, k) => THREE.MathUtils.clamp(x + THREE.MathUtils.clamp(step[k], -20, 20), -85, 85));
          r = evalAt(p);
        }
        return { p, err: Math.hypot(...r) };
      };
      let res = solve(rig._ik[ti] || new Array(n).fill(0));
      if (res.err > 3e-3) {
        const alt = solve(new Array(n).fill(0));
        if (alt.err < res.err) res = alt;
        evalAt(res.p);
      }
      rig._ik[ti] = res.p;
      task.joints.forEach((j, k) => task.names[k].forEach((name) => { pose = { ...pose, [name]: tmp[name] }; }));
    });
  }

  _contacts(rig) {
    const root = rig.root;
    root.position.set(0, 1, 0);
    root.updateMatrixWorld(true);
    const A = this.ex.anchor;
    const flat = this.ex.flatFeet;

    for (let iter = 0; iter < (flat ? 2 : 1); iter++) {
      // Primary contact: translate so the declared point(s) land on target.
      const p = rig.world(A.point, tmpV2);
      const t = A.target;
      root.position.x += t[0] - p.x;
      root.position.y += t[1] - p.y;
      root.position.z += t[2] - p.z;
      root.updateMatrixWorld(true);

      // Balance: hanging bodies settle with their centre of mass under the grip.
      if (this.ex.balance) {
        const T = new THREE.Vector3(...t);
        for (let k = 0; k < 2; k++) {
          const c = rig.com(new THREE.Vector3());
          const dy = c.y - T.y; const dz = c.z - T.z;
          if (Math.abs(dy) < 1e-4) break;
          tmpQ.setFromAxisAngle(X_AXIS, Math.atan(-dz / dy));
          root.position.sub(T).applyQuaternion(tmpQ).add(T);
          root.quaternion.premultiply(tmpQ);
          root.updateMatrixWorld(true);
        }
      }

      // Secondary contact: rotate about the world X axis through the primary
      // target until the second point sits at its target height.
      if (A.second) {
        const T = new THREE.Vector3(...t);
        const S = rig.world(A.second.point, new THREE.Vector3());
        const dy = S.y - T.y; const dz = S.z - T.z;
        const r = Math.hypot(dy, dz);
        const want = THREE.MathUtils.clamp((A.second.y - T.y) / r, -1, 1);
        const phi = Math.atan2(dy, dz);
        let phi2 = Math.asin(want);
        if (dz < 0) phi2 = Math.PI - phi2;
        const alpha = phi - phi2;
        tmpQ.setFromAxisAngle(X_AXIS, alpha);
        root.position.sub(T).applyQuaternion(tmpQ).add(T);
        root.quaternion.premultiply(tmpQ);
        root.updateMatrixWorld(true);
      }

      // Floor clamp (lying exercises): nothing may sink below the mat.
      if (this.ex.floorClamp) {
        let minY = Infinity;
        for (const n of ['gluteL', 'gluteR', 'scapL', 'scapR', 'occiput', 'sacrum', 'lumbar', 'upperBack']) minY = Math.min(minY, rig.world(n, tmpV).y);
        if (minY < 0) { root.position.y -= minY; root.updateMatrixWorld(true); }
      }

      // Flat feet: orient each foot level with the floor regardless of the
      // chain above it, then re-run the solve once so contacts stay exact.
      if (flat) {
        for (const s of flat === true ? ['L', 'R'] : flat) {
          const an = rig.bones['ankle' + s];
          an.parent.getWorldQuaternion(tmpQ);
          an.quaternion.copy(tmpQ.invert());
          an.updateMatrixWorld(true);
        }
      }
      // Locked feet keep the exact world orientation they had in pose 0
      // (e.g. the rear foot resting laces-down on the bench).
      if (this.lockQ && iter === 0) {
        for (const [s, q] of Object.entries(this.lockQ)) {
          const an = rig.bones['ankle' + s];
          an.parent.getWorldQuaternion(tmpQ);
          an.quaternion.copy(tmpQ.invert().multiply(q));
          an.updateMatrixWorld(true);
        }
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Timeline
  // ---------------------------------------------------------------------------
  _sample(time) {
    const ex = this.ex;
    let t = ((time % this.cycle) + this.cycle) % this.cycle;
    let acc = 0;
    for (let i = 0; i < ex.tempo.length; i++) {
      const seg = ex.tempo[i];
      if (t <= acc + seg.dur || i === ex.tempo.length - 1) {
        const local = seg.dur ? Math.min(1, (t - acc) / seg.dur) : 1;
        const e = (ease[seg.ease] || ease.inOut)(local);
        return { seg, i, local, e, cycleT: t / this.cycle };
      }
      acc += seg.dur;
    }
    return null;
  }

  _tick() {
    const dt = Math.min(this.clock.getDelta(), 0.05);
    if (!this.visible || !this.ex) return;
    if (this.playing) this.time += dt * this.speed;

    const s = this._sample(this.time);
    const prevRep = this.rep;
    this.rep = Math.floor(this.time / this.cycle);
    const src = this.toggles.fault ? this.faultPoses : this.poses;
    const pose = lerpPose(src[s.seg.from], src[s.seg.to], s.e);
    this._pose(pose, this.rig);

    // Tension drives the muscle glow: brightest under load / in the stretch.
    const ten = s.seg.tension ?? (s.seg.from === s.seg.to ? 0.35 : 0.9);
    const pulse = 0.85 + 0.15 * Math.sin(this.time * 6);
    this.rig.setHighlight(this.ex.primary, this.ex.secondary, ten * pulse, this.toggles.fault ? 1 : 0);

    if (this.rig.updateContraction) this.rig.updateContraction();
    this._updateKB();
    this._updateOverlays(s);
    this._updateCamera(dt);

    if (this.rep !== prevRep) this.traceHistory = [];
    for (const fn of this.listeners) fn({ seg: s.seg, index: s.i, local: s.local, cycleT: s.cycleT, rep: this.rep });

    this.controls.update();
    this.composer.render();
    this._adapt(dt);
    this._updateLabels(dt);
  }

  /** Adaptive resolution: trade pixel density for frame rate, never geometry. */
  _adapt(dt) {
    const f = this._frameTimes;
    f.push(dt);
    if (f.length < 90) return;
    const avg = f.reduce((a, b) => a + b, 0) / f.length;
    f.length = 0;
    const max = Math.min(window.devicePixelRatio, this.opts.pixelRatio || 2);
    if (avg > 1 / 40 && this.quality > 0.5) this.quality = Math.max(0.5, this.quality - 0.15);
    else if (avg < 1 / 58 && this.quality < 1) this.quality = Math.min(1, this.quality + 0.1);
    const pr = Math.max(1, max * this.quality);
    if (Math.abs(pr - this.renderer.getPixelRatio()) > 0.05) {
      this.renderer.setPixelRatio(pr);
      this.composer.setPixelRatio(pr);
      this._resize();
    }
  }

  _updateKB() {
    const kb = this.props.kb;
    if (!kb.visible) return;
    const h = this.rig.world('mid:handL,handR', new THREE.Vector3());
    const sh = this.rig.world('mid:shoulderL,shoulderR', new THREE.Vector3());
    const dir = h.clone().sub(sh).normalize();
    kb.position.copy(h);
    kb.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), dir);
  }

  _updateCamera(dt) {
    if (this._center) this.controls.target.lerp(this._center, 1 - Math.exp(-dt * 4));
    if (this.camTween) {
      const tw = this.camTween;
      tw.t = Math.min(1, tw.t + dt / 0.9);
      // Orbit around the target (spherical interpolation) so view changes
      // swing around the figure instead of flying through it.
      const c = this.controls.target;
      if (!tw.s0) {
        tw.s0 = new THREE.Spherical().setFromVector3(tw.from.clone().sub(c));
        tw.s1 = new THREE.Spherical().setFromVector3(tw.to.clone().sub(c));
        let dth = tw.s1.theta - tw.s0.theta;
        if (dth > Math.PI) dth -= Math.PI * 2;
        if (dth < -Math.PI) dth += Math.PI * 2;
        tw.dth = dth;
      }
      const e = ease.inOut(tw.t);
      const sp = new THREE.Spherical(
        tw.s0.radius + (tw.s1.radius - tw.s0.radius) * e,
        tw.s0.phi + (tw.s1.phi - tw.s0.phi) * e,
        tw.s0.theta + tw.dth * e,
      );
      this.camera.position.setFromSpherical(sp).add(c);
      if (tw.t >= 1) this.camTween = null;
    }
  }

  _updateOverlays(s) {
    const ex = this.ex;
    const r = this.rig;
    const show = !this.opts.hero;
    this.readouts = [];

    // Body line (straightness check through three landmarks)
    const L = ex.line;
    const lineOn = show && this.toggles.line && L;
    this.lineSegs.forEach((sg) => (sg.mesh.visible = !!lineOn));
    this.lineDots.forEach((d) => (d.visible = !!lineOn));
    if (lineOn) {
      const a = r.world(L.pts[0], new THREE.Vector3());
      const b = r.world(L.pts[1], new THREE.Vector3());
      const c = r.world(L.pts[2], new THREE.Vector3());
      const ang = 180 - angleAt(a, b, c);
      const ok = ang <= (L.tol ?? 10);
      const col = ok ? 0x3dff9a : 0xff3b5c;
      this.lineSegs[0].set(a, b); this.lineSegs[1].set(b, c);
      this.lineSegs.forEach((sg) => sg.mat.color.setHex(col));
      [a, b, c].forEach((p, i) => this.lineDots[i].position.copy(p));
      this.readouts.push({ pos: b.clone(), name: L.label, value: `${ang.toFixed(0)}° ${ok ? '✓' : '✕'}`, cls: ok ? 'good' : 'bad', prio: ok ? 1 : 0 });
    }

    // Joint angle readouts
    const A = (show && this.toggles.angles && ex.angles) || [];
    let segI = 0; let dotI = 0;
    this.angleSegs.forEach((sg) => (sg.mesh.visible = false));
    this.angleDots.forEach((d) => (d.visible = false));
    A.slice(0, 3).forEach((m) => {
      const a = r.world(m.pts[0], new THREE.Vector3());
      const b = r.world(m.pts[1], new THREE.Vector3());
      const c = r.world(m.pts[2], new THREE.Vector3());
      const deg = angleAt(a, b, c);
      if (segI < 6) { this.angleSegs[segI].set(a, b); this.angleSegs[segI++].mesh.visible = true; }
      if (segI < 6) { this.angleSegs[segI].set(b, c); this.angleSegs[segI++].mesh.visible = true; }
      if (dotI < 3) { this.angleDots[dotI].position.copy(b); this.angleDots[dotI++].visible = true; }
      const inRange = m.good ? deg >= m.good[0] && deg <= m.good[1] : true;
      this.readouts.push({ pos: b.clone(), name: m.label, value: `${deg.toFixed(0)}°`, cls: inRange ? 'angle in' : 'angle', prio: 2 });
    });

    // Selected structure label (anatomy inspection)
    if (show && this.selected != null && this.rig.structureAnchor) {
      const st = this.rig.meta.structures[this.selected];
      this.readouts.push({ pos: this.rig.structureAnchor(this.selected, new THREE.Vector3()), name: st.name.replace(/[()]/g, ''), value: '', cls: 'select', prio: -1 });
    }

    // Motion trace
    const traceOn = show && this.toggles.trace && ex.trace;
    this.trace.visible = this.tracePts.visible = !!traceOn;
    if (traceOn) {
      const p = r.world(ex.trace.pt, new THREE.Vector3());
      this.traceHistory.push(p);
      if (this.traceHistory.length > this.traceN) this.traceHistory.shift();
      const n = this.traceHistory.length;
      const hot = new THREE.Color(0x52d4ff);
      for (let i = 0; i < this.traceN; i++) {
        const q = this.traceHistory[Math.min(i, n - 1)] || p;
        this.tracePos.set([q.x, q.y, q.z], i * 3);
        const k = n ? Math.min(i, n - 1) / Math.max(1, n - 1) : 0;
        this.traceCol.set([hot.r * k, hot.g * k, hot.b * k], i * 3);
      }
      this.trace.geometry.attributes.position.needsUpdate = true;
      this.trace.geometry.attributes.color.needsUpdate = true;
      this.trace.geometry.setDrawRange(0, Math.max(1, n));
      if (ex.trace.label) this.readouts.push({ pos: p.clone(), name: ex.trace.label, value: '', cls: 'trace', prio: 3 });
    }
  }

  /**
   * Callout labels. Each readout is placed by scoring 8 candidate spots around
   * the figure's on-screen outline: leader length, overlap with HUD elements
   * and other labels (heavily penalised), and overlap with the figure itself.
   * Labels that cannot be placed cleanly are hidden rather than stacked, and
   * a side is only abandoned when another is clearly better (no flicker).
   * Leaders are two-segment, with a dark halo so they read over muscle.
   */
  _updateLabels(dt = 1 / 60) {
    const R = (this.readouts || []).slice().sort((a, b) => a.prio - b.prio);
    const W = this.container.clientWidth;
    const H = this.container.clientHeight;
    const NS = 'http://www.w3.org/2000/svg';
    if (!this.leaderSvg) {
      this.leaderSvg = document.createElementNS(NS, 'svg');
      this.leaderSvg.setAttribute('class', 'leaders');
      this.labelLayer.appendChild(this.leaderSvg);
      this.leaders = [];
      this.labelLayer.setAttribute('aria-hidden', 'true');
    }
    const narrow = W < 560;
    const list = (narrow ? R.filter((r) => r.cls !== 'trace') : R).slice(0, narrow ? 3 : 5);
    while (this.labels.length < list.length) {
      const el = document.createElement('div');
      el.className = 'label3d';
      el.innerHTML = '<b></b><span class="v"></span>';
      this.labelLayer.appendChild(el);
      this.labels.push(el);
      const g = document.createElementNS(NS, 'g');
      g.innerHTML = '<polyline class="halo"/><polyline class="ln"/><polygon/><circle r="3.2"/>';
      this.leaderSvg.appendChild(g);
      this.leaders.push(g);
    }

    // HUD obstacles, refreshed a few times per second (layout reads are costly).
    this._obsT = (this._obsT || 0) - dt;
    if (this._obsT <= 0 || !this._obstacles) {
      this._obsT = 0.25;
      const cr = this.container.getBoundingClientRect();
      this._obstacles = [...this.container.querySelectorAll('.hud-top > *, #faultBanner:not([hidden]), #legend > *, #viewBtns, #sessionHud:not([hidden])')]
        .map((e) => e.getBoundingClientRect())
        .filter((r) => r.width && r.height)
        .map((r) => ({ x: r.left - cr.left - 4, y: r.top - cr.top - 4, w: r.width + 8, h: r.height + 8 }));
    }

    // Screen-space outline of the body.
    const pts = ['headTop', 'toeL', 'toeR', 'heelL', 'handL', 'handR', 'elbowL', 'elbowR', 'kneeCapL', 'kneeCapR', 'pelvis', 'shoulderL', 'shoulderR', 'sacrum'];
    let x0 = Infinity; let y0 = Infinity; let x1 = -Infinity; let y1 = -Infinity;
    const v = new THREE.Vector3();
    for (const n of pts) {
      this.rig.world(n, v).project(this.camera);
      const sx = (v.x * 0.5 + 0.5) * W; const sy = (-v.y * 0.5 + 0.5) * H;
      x0 = Math.min(x0, sx); x1 = Math.max(x1, sx); y0 = Math.min(y0, sy); y1 = Math.max(y1, sy);
    }
    const pad = 14; x0 -= pad; x1 += pad; y0 -= pad * 1.6; y1 += pad;
    const fig = { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
    // Body occupancy: boxes along every limb, so labels avoid the actual body
    // (not just its bounding box, which is mostly empty in a T-shape).
    const SEGS = [['pelvis', 'chestMid'], ['chestMid', 'neck'], ['neck', 'headTop'], ['shoulderL', 'shoulderR'],
      ['shoulderL', 'elbowL'], ['elbowL', 'handL'], ['shoulderR', 'elbowR'], ['elbowR', 'handR'],
      ['hipL', 'kneeCapL'], ['kneeCapL', 'ankleL'], ['ankleL', 'toeL'], ['hipR', 'kneeCapR'], ['kneeCapR', 'ankleR'], ['ankleR', 'toeR']];
    const blobs = [];
    const A3 = new THREE.Vector3(); const B3 = new THREE.Vector3(); const C3 = new THREE.Vector3();
    const camDist = this.camera.position.distanceTo(this.controls.target);
    const rpx = (0.075 / (2 * Math.tan((this.camera.fov * DEG) / 2) * camDist)) * H;
    for (const [m, n] of SEGS) {
      this.rig.world(m, A3); this.rig.world(n, B3);
      for (const f of [0, 0.25, 0.5, 0.75, 1]) {
        C3.lerpVectors(A3, B3, f).project(this.camera);
        const bx = (C3.x * 0.5 + 0.5) * W; const by = (-C3.y * 0.5 + 0.5) * H;
        blobs.push({ x: bx - rpx, y: by - rpx, w: 2 * rpx, h: 2 * rpx });
      }
    }
    const G = narrow ? 14 : 24; const EDGE = 8;
    const ov = (a, b) => Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) *
      Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));

    const placed = [];
    this.labels.forEach((el) => { el.style.display = 'none'; });
    this.leaders.forEach((g) => { g.style.display = 'none'; });

    list.forEach((r, i) => {
      const el = this.labels[i];
      if (el._name !== r.name) {
        el.firstChild.textContent = r.name; el._name = r.name; el._w = 0; el._side = null;
        el.classList.toggle('noval', !r.value);
      }
      if (el._val !== r.value) { el.lastChild.textContent = r.value; el._val = r.value; }
      const cls = 'label3d ' + r.cls + (r.value ? '' : ' noval');
      if (el.className !== cls) el.className = cls;
      el.style.display = 'block';
      if (!el._w) { el._w = el.offsetWidth; el._h = el.offsetHeight; }
      const p = r.pos.clone().project(this.camera);
      if (p.z > 1) { el.style.display = 'none'; return; }
      const px = (p.x * 0.5 + 0.5) * W; const py = (-p.y * 0.5 + 0.5) * H;
      const w = el._w; const h = el._h;
      const cand = {
        L: [x0 - G - w, py - h / 2], R: [x1 + G, py - h / 2],
        T: [px - w / 2, y0 - G - h], B: [px - w / 2, y1 + G],
        TL: [x0 - G - w, y0 - G - h], TR: [x1 + G, y0 - G - h],
        BL: [x0 - G - w, y1 + G], BR: [x1 + G, y1 + G],
      };
      const score = {};
      let best = null;
      for (const [side, [cx, cy]] of Object.entries(cand)) {
        const box = {
          x: Math.min(W - EDGE - w, Math.max(EDGE, cx)),
          y: Math.min(H - EDGE - h, Math.max(EDGE, cy)), w, h,
        };
        let hit = 0;
        for (const o of this._obstacles) hit += ov(box, o);
        for (const o of placed) hit += ov(box, o);
        const ax = Math.min(box.x + w, Math.max(box.x, px)); const ay = Math.min(box.y + h, Math.max(box.y, py));
        const lead = Math.hypot(ax - px, ay - py);
        let body = 0;
        for (const o of blobs) body += ov(box, o);
        const sc = lead + 1e4 * hit + 4 * body + 60 * (ov(box, fig) / (w * h));
        score[side] = { sc, box, hit };
        if (!best || sc < best.sc) best = { side, sc, box, hit };
      }
      const prev = el._side && score[el._side];
      if (prev && prev.hit === 0 && best.sc > prev.sc * 0.7) best = { side: el._side, ...prev };
      if (best.hit > 0) { el.style.display = 'none'; return; }
      el._side = best.side;
      placed.push({ x: best.box.x - 4, y: best.box.y - 4, w: w + 8, h: h + 8 });

      const k = el._x == null || Math.abs(el._x - best.box.x) > 240 ? 1 : 1 - Math.exp(-dt * 12);
      el._x = el._x == null ? best.box.x : el._x + (best.box.x - el._x) * k;
      el._y = el._y == null ? best.box.y : el._y + (best.box.y - el._y) * k;
      el.style.transform = `translate(${el._x.toFixed(1)}px, ${el._y.toFixed(1)}px)`;

      // Two-segment leader: straight out of the label, then angled to the joint.
      const lx = el._x; const ly = el._y;
      let sx; let sy; let ex; let ey;
      const side = best.side;
      if (side === 'L' || side === 'TL' || side === 'BL') { sx = lx + w; sy = ly + h / 2; ex = sx + 10; ey = sy; }
      else if (side === 'R' || side === 'TR' || side === 'BR') { sx = lx; sy = ly + h / 2; ex = sx - 10; ey = sy; }
      else if (side === 'T') { sx = lx + w / 2; sy = ly + h; ex = sx; ey = sy + 8; }
      else { sx = lx + w / 2; sy = ly; ex = sx; ey = sy - 8; }
      const dx = px - ex; const dy = py - ey; const len = Math.hypot(dx, dy) || 1;
      const ux = dx / len; const uy = dy / len;
      const tipX = px - ux * 5; const tipY = py - uy * 5;
      const pts2 = `${sx.toFixed(1)},${sy.toFixed(1)} ${ex.toFixed(1)},${ey.toFixed(1)} ${(tipX - ux * 6).toFixed(1)},${(tipY - uy * 6).toFixed(1)}`;
      const g = this.leaders[i];
      g.style.display = '';
      g.setAttribute('class', 'leader ' + r.cls);
      const [halo, ln, poly, dotEl] = g.children;
      halo.setAttribute('points', pts2);
      ln.setAttribute('points', pts2);
      const bx = tipX - ux * 9; const by = tipY - uy * 9;
      poly.setAttribute('points', `${tipX.toFixed(1)},${tipY.toFixed(1)} ${(bx - uy * 4.5).toFixed(1)},${(by + ux * 4.5).toFixed(1)} ${(bx + uy * 4.5).toFixed(1)},${(by - ux * 4.5).toFixed(1)}`);
      dotEl.setAttribute('cx', px.toFixed(1)); dotEl.setAttribute('cy', py.toFixed(1));
    });
  }

  _resize() {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    if (!w || !h) return;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
    this.composer.setSize(w, h);
  }

  /** Jump to a fraction of the rep cycle (scrubbing). */
  seek(frac) {
    this.time = (this.rep + frac) * this.cycle;
    this.traceHistory = [];
  }
}

function studioBackdrop() {
  const c = document.createElement('canvas');
  c.width = 16; c.height = 512;
  const g = c.getContext('2d');
  const grd = g.createLinearGradient(0, 0, 0, 512);
  grd.addColorStop(0, '#2b2c30');
  grd.addColorStop(0.55, '#3a3b3f');
  grd.addColorStop(1, '#232427');
  g.fillStyle = grd;
  g.fillRect(0, 0, 16, 512);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function angleAt(a, b, c) {
  const u = tmpV.subVectors(a, b).normalize();
  const v = tmpV2.subVectors(c, b).normalize();
  return Math.acos(THREE.MathUtils.clamp(u.dot(v), -1, 1)) / DEG;
}
