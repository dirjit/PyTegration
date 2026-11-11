# Anatomy model — attribution and licence

The files in this folder (`anatomy-economy.glb`, `anatomy-standard.glb`,
`anatomy.json`) are an **adapted work** and are licensed under
**[Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/)**.
Anyone who redistributes or displays them must keep the credits below and share
adaptations under the same licence. (The FORGE site code is not covered by this
licence; only these model files are.)

## Credit line

> Anatomy: “Z-Anatomy — The libre 3D atlas of anatomy” (CC BY-SA 4.0), based on
> “BodyParts3D, © The Database Center for Life Science” (CC BY 4.0), via the
> Svitylo 3D Anatomy Atlas data release; skinned, re-weighted and re-shaded for
> FORGE.

## Sources

| Source | Licence | Link |
| --- | --- | --- |
| Z-Anatomy — The libre 3D atlas of anatomy (models, Latin/English names, TA2 terms) | CC BY-SA 4.0 | https://github.com/Z-Anatomy/Models-of-human-anatomy |
| BodyParts3D, © The Database Center for Life Science (DBCLS) — the geometry Z-Anatomy is built on | CC BY 4.0 (current dataset terms) | https://dbarchive.biosciencedbc.jp/en/bodyparts3d/ |
| `@authorod/svitylo-3d-anatomy-data` 1.2.0, adult-male release (Z-Anatomy snapshot `e38ea5e6`, converted to metres/+Y up, two meshopt LODs) | CC BY-SA 4.0 for the Z-Anatomy content | https://www.npmjs.com/package/@authorod/svitylo-3d-anatomy-data |

The Svitylo release notes its own licence audit as “pending”; it only includes
assets marked CC BY-SA / CC BY and excludes non-commercial ones. Only the
musculoskeletal and eye structures were used here.

## Changes made for FORGE (`forge/tools/anatomy`)

1. **Selection.** Kept: muscles; a whitelist of visible fasciae/aponeuroses
   (iliotibial tract, thoracolumbar fascia, palmar/plantar aponeurosis,
   retinacula, linea alba); bones; eyes; the skin regions, head hair and
   eyebrows (see 6). Dropped: urogenital region and pubic hair, bursae, tendon
   sheaths, internal muscles (laryngeal, pharyngeal, extraocular, pelvic floor,
   deep intercostal layers), enveloping fasciae, teeth, ear ossicles, sinuses.
2. **Skeleton.** Joint centres derived from the bones: least-squares sphere fits
   to the humeral and femoral heads, distal humerus/femur condyles, malleoli,
   distal radius + lunate, vertebral levels (L3, T12/L1, C7/T1, C1),
   sternoclavicular joints; mirrored for left/right symmetry.
3. **Skin weights.** Distance to the actual bone surfaces of each skeletal
   segment, restricted to kinematic neighbours, smoothed over each mesh.
4. **Muscle data.** Origin/insertion centroids from the atlas attachment
   patches (principal-axis ends where a patch is missing); per-vertex fibre
   direction converging on the attachments; axial position; distance from the
   line of action; tendon/aponeurosis mask from tissue thickness near the
   attachments; baked ambient occlusion (full and deep-layer variants).
5. **Packaging.** Merged into six meshes with a per-vertex structure id,
   quantised, compressed with `EXT_meshopt_compression`.
6. **Athletic build and skin (changes the atlas' shapes).**
   - *Muscles thickened.* The bellies of the muscle groups the programme
     trains are displaced outward along their normals by 2-20 mm (most on
     chest, deltoids, arms, lats and quadriceps; none on tendons).
   - *Skin rebuilt as one surface.* Each atlas skin region is a closed slab
     (skin plus the fat beneath it). On the body only the outer sheet is kept;
     the sheets are stitched along their shared borders, small gaps are filled,
     and the surface is subdivided once. Head, hands and feet keep the atlas
     slabs unchanged.
   - *Skin drawn tight.* Body skin is moved to a 2.8 mm layer above the nearest
     (thickened) muscle, fascia or bone and lightly smoothed, i.e. the
     subcutaneous fat is removed. This is a deliberate departure from the
     atlas' body shape.
   - *Shorts.* The band from just below the navel to mid-thigh is smoothed into
     a plain garment and shaded as fabric; the urogenital region is closed over.
   - *Skin data.* Skin weights as in 3; per vertex, the id of the nearest
     muscle, its position along that muscle, a swell weight and an activation
     coverage; baked occlusion and relief.

Apart from point 6, no shapes were invented or re-drawn; geometry is the
atlas' own (decimated by the Svitylo release into the two quality levels).
The figure is an illustration of a trained build, not an anatomical reference
for body shape.

Not suitable for diagnosis or any clinical decision.
