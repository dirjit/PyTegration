# FORGE — the minimum effective physique

A self-contained website: a 12-week lean-down + muscle-building plan built on
12 high-return exercises, with a real-time **three.js Form Lab** that animates
every rep.

## Run it

No build step. Serve the folder with any static server (ES modules need http):

```bash
cd forge
python3 -m http.server 8000
# open http://localhost:8000
```

three.js r170 loads from jsDelivr via an import map, so the page needs internet
access the first time.

## What's inside

| File | What it does |
| --- | --- |
| `js/rig.js` | Procedural écorché figure: about 60 muscles generated from real origin→insertion points with tendons, fascia (linea alba, IT band, thoracolumbar fascia, retinacula), face muscles and baked occlusion; skin weights slide across the joints each muscle crosses; superficial/deep layers; contraction morphs. |
| `js/stage.js` | Renderer, studio lighting, bloom, props, and the **contact solver** (feet/hands/back stay planted), Gauss-Newton IK for sliding contacts, joint-angle readouts, alignment lines, motion traces and range-of-motion ghosts. |
| `js/exercises.js` | The 12 movements: poses, tempo timelines, contact anchors, the "mistake" variant, cues, mistakes, breathing, progressions. |
| `js/program.js` | Phases, sessions, progression rules and tagged field notes. |
| `js/app.js` | UI: Form Lab controls, guided session mode with rest timer, calorie/macro calculator, V-taper ratio tool, tracker. |

## Form Lab features

- Orbit / zoom, camera presets (front, side, ¾, back, top), 0.25×–1.5× speed, scrubbable tempo timeline.
- **Anatomy layers**: Skin, Superficial muscles, or Deep muscles (pectoralis minor, rotator cuff, rhomboids, erectors, vastus intermedius, soleus revealed).
- Callout labels are placed around the figure (scored against the HUD, other labels and the limbs) with arrowed two-segment leader lines.
- **Joint angles** that turn gold when you're inside the target range.
- **Alignment line** (body line, spine neutral, hip lockout) that turns red when you break position.
- **Motion path** of the key landmark (sternum, bar path, bell arc…).
- **Range ghosts** showing both ends of the range of motion.
- **Mistake mode**: the most common fault, animated and tinted red.
- Muscle glow follows tension — brightest in the stretch and under load.

Educational content, not medical advice.
