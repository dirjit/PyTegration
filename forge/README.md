# FORGE — the minimum effective physique

A self-contained website: a 12-week lean-down + muscle-building plan built on
12 high-return exercises, with a real-time **three.js Form Lab**: a muscular
athlete performs every rep while the muscles doing the work light up through
his skin.

## Run it

No build step. Serve the folder with any static server (ES modules need http):

```bash
cd forge
python3 -m http.server 8000
# open http://localhost:8000
```

three.js r170 loads from jsDelivr via an import map, so the page needs internet
access the first time.

## The athlete

The default view is a skinned, muscular man rather than an anatomy chart: people
are moved by a body they can picture as their own, and by seeing exactly which
part of it a movement builds.

- **Skin from the atlas, drawn tight.** The atlas' skin regions are welded into
  one surface and pulled down to a thin layer over the muscles, so the relief
  you see is the real muscle shape underneath, not a sculpt. The muscles the
  programme trains are thickened first (chest, shoulders, arms, back, legs).
- **Activation you can read at a glance.** Every skin vertex knows which muscle
  lies beneath it. Prime movers glow ember, assisting muscles amber; bands
  travel along each muscle from origin to insertion, and the brightness follows
  the tension of the rep (eased, so it swells into the hard part).
- **The skin moves with the muscle.** It bulges as the muscle beneath it
  shortens, and a little more while that muscle is working.
- **X-ray.** The skin becomes a faint shell; the working muscles are lit inside
  it and the resting ones fall back to a cool grey.
- **Muscles / Deep muscles / Skeleton** remain for study, and clicking the body
  in any view names the muscle under the pointer.

## Anatomical model

Under the skin is a real anatomical model, not a procedural mannequin:
**Z-Anatomy — The libre 3D atlas of anatomy** (CC BY-SA 4.0), built on
**BodyParts3D © DBCLS** (CC BY 4.0). 398 individually named muscles (English +
Latin), visible fasciae/aponeuroses, 200+ bones and the eyes, in two quality
levels picked per device (`assets/anatomy/anatomy-standard.glb` ≈ 12 MB,
`anatomy-economy.glb` ≈ 5 MB; force one with `?quality=standard|economy`).
The model files are CC BY-SA 4.0 — see `assets/anatomy/ATTRIBUTION.md`.
They are rebuilt with `tools/anatomy` (extract → process → pack).

- Skeleton derived from the bones (sphere-fit joint centres), skin weights from
  distance to bone surface, smoothed per mesh; scapulohumeral rhythm.
- Per-vertex fibre directions converge on each muscle's atlas origin/insertion;
  the shader adds fibre-aligned striation, tendon/aponeurosis colouring,
  wavelength-dependent wrap lighting for subsurface scattering, baked AO.
- Muscles shorten and thicken with roughly constant volume: radial scale
  √(rest length ÷ length) measured live between their attachments.
- Click a muscle to name it (English + Latin) and isolate it; superficial /
  deep / skeleton layers; elbow-flexion demo for inspecting biceps and triceps.

## What's inside

| File | What it does |
| --- | --- |
| `js/anatomy.js` | Loads the anatomical GLBs, builds the skeleton, skinned meshes and tissue shaders; the athlete's skin, activation glow and X-ray; contraction, highlighting, views, isolation, GPU picking. |
| `tools/anatomy/` | Offline asset pipeline (Node + Python) that produces `assets/anatomy/`. |
| `js/rig.js` | (fallback)  Procedural écorché figure: about 60 muscles generated from real origin→insertion points with tendons, fascia (linea alba, IT band, thoracolumbar fascia, retinacula), face muscles and baked occlusion; skin weights slide across the joints each muscle crosses; superficial/deep layers; contraction morphs. |
| `js/stage.js` | Renderer, studio lighting, bloom, props, and the **contact solver** (feet/hands/back stay planted), Gauss-Newton IK for sliding contacts, joint-angle readouts, alignment lines, motion traces and range-of-motion ghosts. |
| `js/exercises.js` | The 12 movements: poses, tempo timelines, contact anchors, the "mistake" variant, cues, mistakes, breathing, progressions. |
| `js/program.js` | Phases, sessions, progression rules and tagged field notes. |
| `js/app.js` | UI: Form Lab controls, guided session mode with rest timer, calorie/macro calculator, V-taper ratio tool, tracker. |

## Form Lab features

- Orbit / zoom, camera presets (front, side, ¾, back, top), 0.25×–1.5× speed, scrubbable tempo timeline.
- **Views**: Athlete (skin with muscle activation), X-ray, Muscles, Deep muscles (pectoralis minor, rotator cuff, rhomboids, erectors, vastus intermedius, soleus revealed) and Skeleton.
- Callout labels are placed around the figure (scored against the HUD, other labels and the limbs) with arrowed two-segment leader lines.
- **Joint angles** that turn gold when you're inside the target range.
- **Alignment line** (body line, spine neutral, hip lockout) that turns red when you break position.
- **Motion path** of the key landmark (sternum, bar path, bell arc…).
- **Range ghosts** showing both ends of the range of motion.
- **Mistake mode**: the most common fault, animated and tinted red.
- Muscle glow follows tension — brightest in the stretch and under load — and shows through the skin.

Educational content, not medical advice.
