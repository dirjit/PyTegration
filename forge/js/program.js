// =============================================================================
// program.js — the 12-week FORGE plan, principles, and field notes.
// =============================================================================

export const PRINCIPLES = [
  {
    k: '01', title: 'Minimum effective dose',
    body: 'Three 45-minute full-body sessions a week. 12 movements cover every pattern: push, pull, squat, hinge and core. Everything else is optional.',
  },
  {
    k: '02', title: 'Tension, not tiredness',
    body: 'Muscle grows from hard sets taken close to failure (0–2 reps in reserve) under control. Sweat and soreness are not the goal; tempo and proximity to failure are.',
  },
  {
    k: '03', title: 'Bias the stretch',
    body: 'Reps that load a muscle at long lengths (bottom of the push-up, dead hang, deep split squat) produce more growth. Most exercises here pause where the muscle is longest; the rest slow the lowering.',
  },
  {
    k: '04', title: 'Lose fat at the table',
    body: 'A moderate deficit (~20%) with high protein (≈2 g/kg) strips fat while training keeps muscle. Training burns far less than people think; steps and food do the heavy lifting.',
  },
  {
    k: '05', title: 'Walk, don\'t grind',
    body: '8–12k steps a day and short walks after meals. Low-intensity movement burns fat without eating into recovery the way extra HIIT does.',
  },
  {
    k: '06', title: 'Sleep is a training session',
    body: 'Short sleep during a diet shifts weight loss away from fat toward muscle. 7–9 hours is non-negotiable when you are in a deficit.',
  },
];

// Workout templates -----------------------------------------------------------
// Each item: [exerciseId, sets×reps, tempo, rest, technique note]
export const SESSIONS = {
  A: {
    name: 'Session A — Push · Pull · Legs',
    focus: 'Chest, lats, quads, side delts',
    items: [
      ['pushup', '4 × 6–12', '3-1-1-0', '90 s', 'Last set: + 5 bottom-half partials'],
      ['pullup', '4 × 4–8', '3-0-1-1', '2 min', 'Scap set before every rep'],
      ['bss', '3 × 8–12 / leg', '3-1-1-0', '90 s', 'Start with the weaker leg'],
      ['lateral', '3 × 12–20', '3-0-1-1', '60 s', 'Last set: myo-reps (3 × 4, 15 s rests)'],
      ['legraise', '3 × 8–12', '3-0-1-1', '75 s', 'Exhale fully at the top'],
    ],
  },
  B: {
    name: 'Session B — Overhead · Row · Hinge',
    focus: 'Shoulders, upper back, hamstrings, glutes',
    items: [
      ['pike', '4 × 5–10', '3-1-1-0', '2 min', 'Elevate feet when 10 reps is easy'],
      ['row', '4 × 8–12', '2-0-1-2', '90 s', '2 s squeeze at the top'],
      ['rdl', '3 × 8–12', '3-1-1-0', '2 min', 'Stop where the hips stop'],
      ['dip', '3 × 6–12', '3-1-1-0', '2 min', 'Last set: 20 s stretch hold'],
      ['hollow', '3 × 20–40 s', 'Hold', '60 s', 'Back glued to the floor'],
      ['bridge', '2 × 12–15 / leg', '2-0-1-2', '45 s', 'Superset with hollow hold'],
    ],
  },
  F: {
    name: 'Finisher — Swing EMOM',
    focus: 'Conditioning, posterior chain, fat loss',
    items: [
      ['swing', '10 min EMOM × 10–15', 'Explosive', 'rest of minute', 'Stop the set the moment form slips'],
    ],
  },
};

export const PHASES = [
  {
    id: 1, name: 'Foundation', weeks: 'Weeks 1–4',
    goal: 'Own the positions. Build tendon and technique capacity.',
    rir: '2–3 reps in reserve',
    sets: 'Use the lower set number (e.g. 3 instead of 4)',
    deficit: '~15% below maintenance',
    steps: '8,000 / day',
    extras: ['Master the tempo — film one set per session', 'Dead hang 3 × 30 s daily', 'No finishers yet'],
    week: ['A', 'Walk', 'B', 'Mobility', 'A', 'Long walk', 'Rest'],
    alt: ['B', 'Walk', 'A', 'Mobility', 'B', 'Long walk', 'Rest'],
  },
  {
    id: 2, name: 'Build', weeks: 'Weeks 5–8',
    goal: 'Push intensity. Add lengthened partials and myo-reps.',
    rir: '0–1 reps in reserve on the last set',
    sets: 'Full set numbers',
    deficit: '~20% below maintenance',
    steps: '10,000 / day',
    extras: ['Add the Swing finisher after Session A', 'Lengthened partials on the last set', 'Week 8 = deload + diet break (maintenance calories, -40% sets)'],
    week: ['A + F', 'Walk', 'B', 'Mobility', 'A + F', 'Long walk', 'Rest'],
    alt: ['B', 'Walk', 'A + F', 'Mobility', 'B', 'Long walk', 'Rest'],
  },
  {
    id: 3, name: 'Shred', weeks: 'Weeks 9–12',
    goal: 'Density. Same strength, less rest, more output.',
    rir: '0–1 RIR, harder progressions',
    sets: 'Antagonist supersets (push ↔ pull), 60–75 s rest',
    deficit: '~20–25% below maintenance',
    steps: '12,000 / day',
    extras: ['Superset: push-up ↔ pull-up, pike ↔ row', 'Mechanical drop-sets on the last set', 'Week 12: taper volume -30%, keep intensity'],
    week: ['A + F', 'Walk', 'B + F', 'Mobility', 'A + F', 'Long walk', 'Rest'],
    alt: ['B + F', 'Walk', 'A + F', 'Mobility', 'B + F', 'Long walk', 'Rest'],
  },
];

export const DAY_INFO = {
  Walk: '45 min brisk walk or zone-2 (nose-breathing pace) + 3 × 20 s stomach vacuums',
  Mobility: '20 min: dead hang, deep squat hold, couch stretch, wall slides + 10 min walk after each meal',
  'Long walk': '60–90 min hike / walk. Easy pace, outdoors if possible',
  Rest: 'Full rest. Sleep 8 h. Hit protein.',
};

export const PROGRESSION_RULES = [
  ['Double progression', 'Stay in a rep range (e.g. 6–12). When you hit the top on every set with clean tempo, move one step up the progression ladder and restart at the bottom of the range.'],
  ['Tempo before reps', 'With bodyweight, "add weight" by adding time: 3-1-1 → 4-2-1 → 5-3-1. Time under tension climbs ~60% without a single extra rep.'],
  ['Last-set reality check', 'Take the last set of each exercise to true technical failure once a week. Most people underestimate how many reps they have left by 2–4 — this recalibrates you.'],
  ['Deload on purpose', 'Week 8 cuts sets by 40% and food goes back to maintenance. You come back stronger and the diet stops stalling.'],
];

// Field notes -----------------------------------------------------------------
// tag: 'research' (peer-reviewed support), 'craft' (coaching tradition),
//      'forge' (the method original to this plan).
export const FIELD_NOTES = [
  {
    tag: 'research', title: 'Lengthened partials after failure',
    body: 'When full reps run out, keep going with 4–6 half-reps in the bottom (stretched) half: deficit push-ups, dips, split squats. Partial reps at long muscle lengths have matched or beaten full-range reps for growth in several studies.',
    how: 'Only on the last set. Bottom half only. Stop when speed dies.',
    ref: 'Pedrosa et al. 2022; Kassiano et al. 2023',
  },
  {
    tag: 'research', title: 'Sleep decides what you lose',
    body: 'In a controlled diet study, people sleeping 5.5 h instead of 8.5 h lost the same weight — but far less of it was fat and more was lean mass. Sleep is the cheapest muscle-sparing drug there is.',
    how: 'Fixed wake time, dark & cool room, caffeine cut-off 8 h before bed.',
    ref: 'Nedeltcheva et al. 2010, Annals of Internal Medicine',
  },
  {
    tag: 'research', title: 'Diet breaks beat straight dieting',
    body: 'In the MATADOR trial, alternating 2 weeks of dieting with 2 weeks at maintenance produced more fat loss and less rebound than dieting continuously. Our week-8 deload is a lighter version: one 7-day break at maintenance.',
    how: 'Every 6–8 weeks: 7 days at maintenance, mostly extra carbs.',
    ref: 'Byrne et al. 2018, MATADOR study',
  },
  {
    tag: 'research', title: '10-minute walks after meals',
    body: 'In a study of adults with type 2 diabetes, a 10-minute walk after each meal lowered post-meal blood sugar more than one 30-minute walk at another time. Two of these walks add roughly 2,000 steps without "doing cardio".',
    how: '10 min after the two biggest meals. Phone calls count.',
    ref: 'Reynolds et al. 2016, Diabetologia',
  },
  {
    tag: 'forge', title: 'Scap-ignition reps',
    body: 'Every pulling rep starts with a 1-second scapular set (shoulders down & back, elbows still straight). It moves the work from the biceps to the lats and fixes the "I can\'t feel my back" problem in a week.',
    how: 'Pull-ups, rows, hanging leg raises. Treat the scap set as rep 0.',
    ref: 'FORGE method',
  },
  {
    tag: 'forge', title: 'Ratio, not weight: the waist-first V',
    body: 'The look people chase is a shoulder-to-waist ratio near 1.6. Build the numerator (side delts, lats, upper chest) and protect the denominator: no heavy weighted side bends or loaded obliques; train anti-extension and vacuums instead.',
    how: 'Use the ratio tool below. Measure every 2 weeks, same morning conditions.',
    ref: 'FORGE method · classic physique tradition',
  },
  {
    tag: 'forge', title: 'Mechanical drop ladders',
    body: 'No weights to strip? Change leverage instead. When you fail a hard variation, drop instantly to an easier one and keep going: decline push-up → floor → incline; pull-up → chin-up → 5 s negatives.',
    how: 'Last set only, once per exercise, phase 3.',
    ref: 'FORGE method',
  },
  {
    tag: 'forge', title: 'Breath-count rest',
    body: 'Rest by 12 slow nasal breaths (4 s in, 6 s out ≈ 2 min) instead of a clock. The long exhale drops heart rate faster, you start the next set calmer, and you stop doom-scrolling between sets.',
    how: '12 breaths for compounds, 6 for isolation. Myo-rep mini-rests stay on the clock (15 s).',
    ref: 'FORGE method',
  },
  {
    tag: 'craft', title: 'Grease the groove',
    body: 'Strength is a skill. Several easy sets of ~40–50% of your max spread through the day (never to fatigue) build pull-up and push-up numbers fast without adding fatigue to your sessions.',
    how: 'Off days only: 5–8 sets of 2–3 pull-ups, hours apart.',
    ref: 'Calisthenics / kettlebell coaching tradition',
  },
  {
    tag: 'craft', title: 'Weighted stretch finisher',
    body: 'Holding a loaded stretch at the end of the last set (bottom of a dip, deep split squat, dead hang) adds time under tension at long muscle length for almost no recovery cost. Trials that grew calf muscle used about an hour of stretching a day, so treat short holds as a promising extra, not a proven one.',
    how: '20–30 s, only in positions that feel safe. Never bounce.',
    ref: 'Inspired by Warneke et al. 2023 (long-duration stretching)',
  },
  {
    tag: 'forge', title: 'Protein first, plate last',
    body: 'Eat the protein part of every meal first. Protein is the most filling macro; front-loading it means the rest of the plate shrinks on its own. Aim for 40 g+ at the first meal.',
    how: 'Lean meat, eggs, Greek yogurt, whey, tofu — then vegetables — then starch.',
    ref: 'FORGE method · protein-leverage research',
  },
  {
    tag: 'craft', title: 'The truth about Hollywood transformations',
    body: 'Film physiques use months of coaching, private chefs, a camera-day peak (pump circuits, dehydration, lighting, tan) and sometimes drugs. Copy the sustainable part — high protein, consistent deficit, hard training, sleep — and skip the dehydration.',
    how: 'Photo day: a 15-min pump circuit (push-ups, pull-aparts, lateral raises) is all you need.',
    ref: 'Industry practice, as described by trainers',
  },
  {
    tag: 'forge', title: 'Ribs down: the 2-second waist',
    body: 'A flared ribcage and an anteriorly tilted pelvis make the waist look several cm wider. Cue "ribs down, belt-buckle up" in every exercise — it is also the brace that protects the lower back.',
    how: 'Check side-on in a mirror. Hollow body hold trains exactly this.',
    ref: 'FORGE method',
  },
];
