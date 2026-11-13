// =============================================================================
// pack.mjs — step 3 of the anatomy asset pipeline.
// Builds one GLB per quality level from process.py's buffers:
//   meshes: muscle, fascia, bone, eye, digits, skin
//   attributes: POSITION, NORMAL, JOINTS_0, WEIGHTS_0 (skinning, no glTF skin:
//   the runtime builds its own skeleton from anatomy.json), _SID (structure),
//   _FIBER (fibre direction, int8), _MUSC (t along line of action, radial
//   distance /8 cm, tendon factor; uint8)
//   skin reuses them: _SID = muscle beneath, _MUSC = (t along that muscle,
//   swell weight, tendon factor, glow coverage), _FIBER = (may carry shorts,
//   hair, nail), _AO = (occlusion, relief)
// Then quantises positions/normals and applies EXT_meshopt_compression.
// usage: node pack.mjs <proc-dir> <out.glb>
// =============================================================================
import fs from 'node:fs';
import path from 'node:path';
import { Document, NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS, EXTMeshoptCompression, KHRMeshQuantization } from '@gltf-transform/extensions';
import { quantize, reorder, meshopt } from '@gltf-transform/functions';
import { MeshoptEncoder, MeshoptDecoder } from 'meshoptimizer';

const [DIR, OUTFILE] = process.argv.slice(2);
await MeshoptEncoder.ready; await MeshoptDecoder.ready;
const doc = new Document();
const buf = doc.createBuffer();
const scene = doc.createScene('anatomy');

const read = (g, k, spec) => {
  const s = spec[k];
  const T = { float32: Float32Array, uint32: Uint32Array, uint16: Uint16Array, uint8: Uint8Array }[s.dtype];
  const b = fs.readFileSync(path.join(DIR, `${g}.${k}.bin`));
  return new T(b.buffer, b.byteOffset, b.byteLength / T.BYTES_PER_ELEMENT);
};
const acc = (arr, type, normalized = false) => doc.createAccessor().setArray(arr).setType(type).setNormalized(normalized).setBuffer(buf);

for (const g of ['muscle', 'fascia', 'bone', 'eye', 'digits', 'skin']) {
  const sp = path.join(DIR, `${g}.spec.json`);
  if (!fs.existsSync(sp)) continue;
  const spec = JSON.parse(fs.readFileSync(sp, 'utf8'));
  const Pp = read(g, 'P', spec); const Nn = read(g, 'N', spec); const Ii = read(g, 'I', spec);
  const Jj = read(g, 'J', spec); const Ww = read(g, 'W', spec); const Ss = read(g, 'S', spec);
  const Ff = read(g, 'F', spec); const Mm = read(g, 'M', spec); const Aa = read(g, 'A', spec);
  const n = Pp.length / 3;
  const W8 = new Uint8Array(n * 4);
  for (let v = 0; v < n; v++) {
    // round weights to bytes but keep the sum exactly 255
    let sum = 0; let maxk = 0;
    for (let k = 0; k < 4; k++) { const q = Math.round(Ww[v * 4 + k] * 255); W8[v * 4 + k] = q; sum += q; if (Ww[v * 4 + k] > Ww[v * 4 + maxk]) maxk = k; }
    W8[v * 4 + maxk] += 255 - sum;
  }
  const F8 = new Int8Array(n * 3);
  for (let i = 0; i < n * 3; i++) F8[i] = Math.max(-127, Math.min(127, Math.round(Ff[i] * 127)));
  const M8 = new Uint8Array(n * 4);
  for (let i = 0; i < n * 4; i++) M8[i] = Math.max(0, Math.min(255, Math.round(Mm[i] * 255)));
  const prim = doc.createPrimitive()
    .setAttribute('POSITION', acc(new Float32Array(Pp), 'VEC3'))
    .setAttribute('NORMAL', acc(new Float32Array(Nn), 'VEC3'))
    .setAttribute('JOINTS_0', acc(new Uint8Array(Jj), 'VEC4'))
    .setAttribute('WEIGHTS_0', acc(W8, 'VEC4', true))
    .setAttribute('_SID', acc(new Uint16Array(Ss), 'SCALAR'))
    .setAttribute('_AO', acc(Uint8Array.from(Aa, (x) => Math.round(x * 255)), 'VEC2', true))
    .setIndices(acc(n < 65535 ? new Uint16Array(Ii) : new Uint32Array(Ii), 'SCALAR'));
  if (g === 'muscle' || g === 'fascia' || g === 'skin') {
    prim.setAttribute('_FIBER', acc(F8, 'VEC3', true));
    prim.setAttribute('_MUSC', acc(M8, 'VEC4', true));
  }
  const mesh = doc.createMesh(g).addPrimitive(prim);
  scene.addChild(doc.createNode(g).setMesh(mesh));
  console.log(g, 'verts', n, 'tris', Ii.length / 3);
}

doc.createExtension(KHRMeshQuantization).setRequired(true);
await doc.transform(
  reorder({ encoder: MeshoptEncoder }),
  quantize({ pattern: /^(POSITION|NORMAL)$/, quantizePosition: 16, quantizeNormal: 12 }),
  meshopt({ encoder: MeshoptEncoder, level: 'high' }),
);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder, 'meshopt.decoder': MeshoptDecoder });
await io.write(OUTFILE, doc);
console.log('wrote', OUTFILE, (fs.statSync(OUTFILE).size / 1e6).toFixed(2), 'MB');
