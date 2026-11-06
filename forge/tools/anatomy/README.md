# Anatomy asset pipeline

Rebuilds `forge/assets/anatomy/*` from the Z-Anatomy-derived data release.
See `../../assets/anatomy/ATTRIBUTION.md` for sources and licences.

```bash
# 1. data (CC BY-SA 4.0) — the npm tarball is only data, nothing is executed
curl -O https://registry.npmjs.org/@authorod/svitylo-3d-anatomy-data/-/svitylo-3d-anatomy-data-1.2.0.tgz
tar -xzf svitylo-3d-anatomy-data-1.2.0.tgz          # -> package/releases/1.2.0
REL=package/releases/1.2.0

# 2. tools
npm i @gltf-transform/core@4 @gltf-transform/extensions@4 @gltf-transform/functions@4 meshoptimizer@0.21
python3 -m venv venv && venv/bin/pip install numpy scipy

# 3. build both quality levels
for L in economy standard; do
  node extract.mjs $REL $L work/$L
  venv/bin/python process.py work/$L $REL proc/$L
  node pack.mjs proc/$L ../../assets/anatomy/anatomy-$L.glb
done
cp proc/standard/anatomy.json ../../assets/anatomy/anatomy.json
```

| step | file | does |
| --- | --- | --- |
| 1 | `extract.mjs` | decodes the meshopt chunks, splits them into structures by `_ID` |
| 2 | `process.py` | classification, skeleton from bones, skin weights, fibre/tendon/AO attributes, markers |
| 3 | `pack.mjs` | merges into 5 meshes, quantises, meshopt-compresses |
