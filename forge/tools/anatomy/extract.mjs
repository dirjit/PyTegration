// =============================================================================
// extract.mjs — step 1 of the anatomy asset pipeline.
// -----------------------------------------------------------------------------
// Reads the Z-Anatomy-derived data release (@authorod/svitylo-3d-anatomy-data
// 1.2.0, CC BY-SA 4.0), decodes its meshopt-compressed region chunks and
// splits every chunk into individual anatomical structures using the per-vertex
// `_ID` attribute. Writes flat binary buffers + an index for process.py.
//
// usage: node extract.mjs <release-dir> <economy|standard> <out-dir>
// =============================================================================
import fs from 'node:fs';
import path from 'node:path';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { MeshoptDecoder } from 'meshoptimizer';

const [REL, LOD, OUT] = process.argv.slice(2);
const SYSTEMS = ['muscular', 'skeletal', 'insertions', 'nervous', 'regions'];
fs.mkdirSync(OUT, { recursive: true });

const manifest = JSON.parse(fs.readFileSync(path.join(REL, 'manifest.json'), 'utf8'));
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.decoder': MeshoptDecoder });

const owner = new Map();
for (const s of manifest.structures) for (const m of s.meshes || []) owner.set(m, s.id);

const index = [];
const P = []; const N = []; const I = [];
let vBase = 0; let iBase = 0;

for (const ch of manifest.chunks) {
  if (!SYSTEMS.includes(ch.system)) continue;
  const doc = await io.read(path.join(REL, ch.files[LOD].path));
  for (const node of doc.getRoot().listNodes()) {
    const mesh = node.getMesh();
    if (!mesh) continue;
    // KHR_mesh_quantization stores positions as normalised integers; the node
    // transform (scale + offset) maps them back to metres.
    const M = node.getWorldMatrix();
    const xf = (a) => [M[0] * a[0] + M[4] * a[1] + M[8] * a[2] + M[12], M[1] * a[0] + M[5] * a[1] + M[9] * a[2] + M[13], M[2] * a[0] + M[6] * a[1] + M[10] * a[2] + M[14]];
    const nx = (a) => { const x = M[0] * a[0] + M[4] * a[1] + M[8] * a[2]; const y = M[1] * a[0] + M[5] * a[1] + M[9] * a[2]; const z = M[2] * a[0] + M[6] * a[1] + M[10] * a[2]; return [x, y, z]; };
    const sx = Math.hypot(M[0], M[1], M[2]); const sy = Math.hypot(M[4], M[5], M[6]); const sz = Math.hypot(M[8], M[9], M[10]);
    for (const prim of mesh.listPrimitives()) {
      const pos = prim.getAttribute('POSITION');
      const nor = prim.getAttribute('NORMAL');
      const ids = prim.getAttribute('_ID');
      const idx = prim.getIndices();
      const n = pos.getCount();
      const a = [0, 0, 0]; const b = [0, 0, 0]; const c = [0];
      // dequantised positions/normals and raw ids
      const pa = new Float32Array(n * 3); const na = new Float32Array(n * 3); const ia = new Int32Array(n);
      for (let v = 0; v < n; v++) {
        pos.getElement(v, a); pa.set(xf(a), v * 3);
        nor.getElement(v, b);
        // normals transform by the inverse-transpose (diagonal scale here)
        const nn = nx([b[0] / (sx * sx), b[1] / (sy * sy), b[2] / (sz * sz)]);
        const l = Math.hypot(nn[0], nn[1], nn[2]) || 1;
        na.set([nn[0] / l, nn[1] / l, nn[2] / l], v * 3);
        ids.getElement(v, c); ia[v] = Math.round(c[0]);
      }
      // ids may be local (0..meshCount-1) or global (meshStart..)
      let minId = Infinity; let maxId = -Infinity;
      for (let v = 0; v < n; v++) { minId = Math.min(minId, ia[v]); maxId = Math.max(maxId, ia[v]); }
      const local = maxId < ch.meshCount;
      const tri = idx.getArray();
      // group triangles by the id of their first vertex
      const groups = new Map();
      for (let t = 0; t < tri.length; t += 3) {
        const id = ia[tri[t]];
        if (!groups.has(id)) groups.set(id, []);
        groups.get(id).push(t);
      }
      for (const [rawId, tris] of groups) {
        const gid = local ? ch.meshStart + rawId : rawId;
        const sid = owner.get(gid);
        const remap = new Map();
        const lp = []; const ln = []; const li = [];
        for (const t of tris) {
          for (let k = 0; k < 3; k++) {
            const v = tri[t + k];
            let r = remap.get(v);
            if (r === undefined) {
              r = remap.size; remap.set(v, r);
              lp.push(pa[v * 3], pa[v * 3 + 1], pa[v * 3 + 2]);
              ln.push(na[v * 3], na[v * 3 + 1], na[v * 3 + 2]);
            }
            li.push(r);
          }
        }
        index.push({ id: sid, mesh: gid, chunk: ch.id, system: ch.system, v0: vBase, vn: remap.size, i0: iBase, in: li.length });
        P.push(Float32Array.from(lp)); N.push(Float32Array.from(ln)); I.push(Uint32Array.from(li));
        vBase += remap.size; iBase += li.length;
      }
    }
  }
}
const cat = (arrs, T) => { const n = arrs.reduce((s, a) => s + a.length, 0); const o = new T(n); let k = 0; for (const a of arrs) { o.set(a, k); k += a.length; } return o; };
fs.writeFileSync(path.join(OUT, 'positions.f32'), Buffer.from(cat(P, Float32Array).buffer));
fs.writeFileSync(path.join(OUT, 'normals.f32'), Buffer.from(cat(N, Float32Array).buffer));
fs.writeFileSync(path.join(OUT, 'indices.u32'), Buffer.from(cat(I, Uint32Array).buffer));
fs.writeFileSync(path.join(OUT, 'index.json'), JSON.stringify(index));
console.log(LOD, 'structures', index.length, 'vertices', vBase, 'triangles', iBase / 3);
