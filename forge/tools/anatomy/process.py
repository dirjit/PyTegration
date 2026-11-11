"""
process.py — step 2 of the anatomy asset pipeline.

Input : the per-structure buffers written by extract.mjs plus the data
        release's manifest + name dictionaries (Z-Anatomy, CC BY-SA 4.0).
Output: <out>/{group}.npz arrays for pack.mjs and <out>/anatomy.json.

What it does
  1. Classifies structures (muscle, fascia/aponeurosis, bone, eye, skin) and
     drops internal structures that are never visible in a musculoskeletal
     teaching view (bursae, tendon sheaths, laryngeal muscles, ...).
  2. Derives an anatomically placed skeleton from the bones themselves:
     sphere fits to the humeral and femoral heads, condyle and malleolus
     centres, vertebral levels, sternoclavicular joints.
  3. Skin weights: every soft-tissue vertex is weighted to nearby skeletal
     segments by distance to actual bone surface, restricted to kinematic
     neighbours, then smoothed over the mesh so there are no seams.
  4. Per muscle: origin / insertion centroids from the atlas' attachment
     patches; per vertex fibre direction (converging on the attachments),
     axial position t, distance from the line of action r, tendon factor.
"""

# Matrix-style names (P, N, I, J, W, D, A, O/I for origin/insertion) follow
# the maths they implement; keep them rather than spelling everything out.
# ruff: noqa: N802, N803, N806, N816, E741
import json
import re
import sys

import numpy as np
from scipy import sparse
from scipy.sparse import csgraph  # noqa: F401  (registers sparse.csgraph)
from scipy.spatial import cKDTree

WORK, REL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]


def load_json(path):
    with open(path) as f:
        return json.load(f)


def dump_json(obj, path):
    with open(path, "w") as f:
        json.dump(obj, f)


idx = load_json(f"{WORK}/index.json")
P = np.fromfile(f"{WORK}/positions.f32", dtype=np.float32).reshape(-1, 3).astype(np.float64)
N = np.fromfile(f"{WORK}/normals.f32", dtype=np.float32).reshape(-1, 3).astype(np.float64)
I = np.fromfile(f"{WORK}/indices.u32", dtype=np.uint32)
man = load_json(f"{REL}/manifest.json")
EN = load_json(f"{REL}/names/en.json")["entries"]
LA = load_json(f"{REL}/names/la.json")["entries"]
SMETA = {s["id"]: s for s in man["structures"]}


def name(sid):
    return (EN.get(sid) or {}).get("name") or sid


def latin(sid):
    return (LA.get(sid) or {}).get("name")


def side(sid):
    s = SMETA.get(sid, {}).get("side")
    return "L" if s == "left" else "R" if s == "right" else ""


def parent(sid):
    return SMETA.get(sid, {}).get("parent") or ""


# ----------------------------------------------------------------------------- classification
DROP_MUSCLE_PARENTS = (
    "bursae",
    "tendon_sheath",
    "extra_ocular",
    "laryngeal",
    "pharyngeal",
    "soft_palate",
    "tongue",
    "levator_ani",
    "pelvic_diaphragm",
    "perineal",
    "endo_abdominal",
)
DROP_MUSCLE_NAMES = (
    "innermost intercostal",
    "internal intercostal",
    "transversus thoracis",
    "diaphragm",
    "intertransversarii",
    "rotatores",
    "interspinales",
    "levatores costarum",
    "subcostal",
)
FASCIA_KEEP = (
    "iliotibial tract",
    "posterior layer of thoracolumbar fascia",
    "palmar aponeurosis",
    "plantar aponeurosis",
    "retinaculum",
    "linea alba",
    "superficial transverse metacarpal",
    "superficial transverse metatarsal",
    "bicipital aponeurosis",
)
BONE_DROP = (
    "tooth",
    "incisor",
    "canine",
    "molar",
    "premolar",
    "incus",
    "malleus",
    "stapes",
    "sinus of",
    "cells of ethmoid",
    "arytenoid",
    "corniculate",
    "concha",
    "vomer",
    "ethmoid bone",
    "palatine",
    "lacrimal",
    "sphenoid",
)
EYE_KEEP = ("posterior segment of eyeball", "iris")


def classify(e):
    sid, sysn = e["id"], e["system"]
    if sid is None:
        return None
    n = name(sid).lower()
    p = parent(sid).lower()
    if sysn == "skeletal":
        return None if any(k in n for k in BONE_DROP) else "bone"
    if sysn == "muscular":
        if "fasci" in p or "linea alba" in n or "aponeurosis" in n or "retinacul" in n:
            return "fascia" if any(k in n for k in FASCIA_KEEP) else None
        if any(k in p for k in DROP_MUSCLE_PARENTS) or any(k in n for k in DROP_MUSCLE_NAMES):
            return None
        return "muscle"
    if sysn in ("visceral", "nervous"):
        return "eye" if any(k in n for k in EYE_KEEP) else None
    if sysn == "regions":
        # Only the digits: they need soft-tissue volume, the rest stays skinless.
        keep = ("palm", "surfaces of digits of hand", "nail plate", "surfaces of digits of foot")
        return "digits" if any(k in n for k in keep) else None
    if sysn == "insertions":
        return "insertion"
    return None


for e in idx:
    e["cls"] = classify(e)


def verts(e):
    return P[e["v0"] : e["v0"] + e["vn"]]


# ----------------------------------------------------------------------------- skeleton segments
SEGS = [
    "root",
    "spine",
    "chest",
    "neck",
    "head",
    "scapL",
    "scapR",
    "shoulderL",
    "shoulderR",
    "elbowL",
    "elbowR",
    "wristL",
    "wristR",
    "hipL",
    "hipR",
    "kneeL",
    "kneeR",
    "ankleL",
    "ankleR",
]
# fingers: f<digit><side><joint>; digit 1 = thumb (joint 1 = CMC / first metacarpal)
for _s in ("L", "R"):
    for _f in range(1, 6):
        for _j in range(1, 4):
            SEGS.append(f"f{_f}{_s}{_j}")
# forearm twist segments (pronation/supination is shared along the forearm)
for _s in ("L", "R"):
    for _k in (1, 2, 3):
        SEGS.append(f"tw{_k}{_s}")
PARENT = {
    "spine": "root",
    "chest": "spine",
    "neck": "chest",
    "head": "neck",
    "scapL": "chest",
    "scapR": "chest",
    "shoulderL": "scapL",
    "shoulderR": "scapR",
    "elbowL": "shoulderL",
    "elbowR": "shoulderR",
    "wristL": "elbowL",
    "wristR": "elbowR",
    "hipL": "root",
    "hipR": "root",
    "kneeL": "hipL",
    "kneeR": "hipR",
    "ankleL": "kneeL",
    "ankleR": "kneeR",
}
for _s in ("L", "R"):
    for _f in range(1, 6):
        PARENT[f"f{_f}{_s}1"] = "wrist" + _s
        PARENT[f"f{_f}{_s}2"] = f"f{_f}{_s}1"
        PARENT[f"f{_f}{_s}3"] = f"f{_f}{_s}2"
    for _k in (1, 2, 3):
        PARENT[f"tw{_k}{_s}"] = "elbow" + _s
SI = {s: i for i, s in enumerate(SEGS)}
NEIGH = {s: {s} for s in SEGS}
for c, p in PARENT.items():
    NEIGH[c].add(p)
    NEIGH[p].add(c)


def bone_segment(sid):
    n = name(sid).lower()
    s = side(sid)
    if re.search(r"vertebra l[45]|sacrum|coccyx|hip bone", n):
        return "root"
    if re.search(r"vertebra l[123]", n):
        return "spine"
    if re.search(r"vertebra t\d|rib|sternum|xiphoid|manubrium|costal", n):
        return "chest"
    if re.search(r"vertebra c[3-7]|axis|hyoid|thyroid|cricoid", n):
        return "neck"
    if re.search(
        r"atlas|frontal|parietal|occipital|temporal|zygomatic|maxilla|mandible|nasal|alar|septal|tooth|incisor|canine|molar|premolar",
        n,
    ):
        return "head"
    if re.search(r"scapula|clavicle", n):
        return "scap" + s
    if "humerus" in n:
        return "shoulder" + s
    if re.search(r"radius|ulna", n):
        return "elbow" + s
    m = re.search(
        r"(proximal|middle|distal) phalanx of (first|second|third|fourth|fifth) finger of hand", n
    )
    if m:
        digit = ["first", "second", "third", "fourth", "fifth"].index(m.group(2)) + 1
        level = {"proximal": 1, "middle": 2, "distal": 3}[m.group(1)]
        if digit == 1:  # thumb: metacarpal is joint 1, phalanges 2 and 3
            level = {"proximal": 2, "distal": 3}[m.group(1)]
        return f"f{digit}{s}{level}"
    if "first metacarpal" in n:
        return f"f1{s}1"
    if re.search(
        r"of hand|carpal|scaphoid|lunate|triquetrum|pisiform|trapez|capitate|hamate|metacarpal", n
    ):
        return "wrist" + s
    if "femur" in n or "patella" in n:
        return "hip" + s
    if re.search(r"tibia|fibula", n):
        return "knee" + s
    if re.search(r"of foot|talus|calcaneus|navicular|cuboid|cuneiform|metatarsal|sesamoid", n):
        return "ankle" + s
    return None


bones = [e for e in idx if e["cls"] == "bone"]
for e in bones:
    e["seg"] = bone_segment(e["id"])
unassigned = [name(e["id"]) for e in bones if e["seg"] is None]
if unassigned:
    print("WARN unassigned bones", sorted(set(unassigned))[:20])
bones = [e for e in bones if e["seg"]]


def B(nm_re, s=None):
    """Vertices of all bones whose name matches (and side)."""
    vs = [
        verts(e)
        for e in bones
        if re.search(nm_re, name(e["id"]).lower()) and (s is None or side(e["id"]) == s)
    ]
    if not vs:
        raise SystemExit(f"no bone matching {nm_re} {s}")
    return np.concatenate(vs)


def sphere_fit(pts):
    A = np.c_[2 * pts, np.ones(len(pts))]
    f = (pts**2).sum(1)
    c, *_ = np.linalg.lstsq(A, f, rcond=None)
    return c[:3]


J = {}
for s, k in (("L", 1), ("R", -1)):
    fem = B("^femur$", s)
    top = fem[fem[:, 1] > fem[:, 1].max() - 0.06]
    med = top[(top[:, 0] * k) < np.median(top[:, 0] * k)]  # head is medial
    J["hip" + s] = sphere_fit(med)
    bot = fem[fem[:, 1] < fem[:, 1].min() + 0.04]
    J["knee" + s] = np.r_[bot[:, 0].mean(), fem[:, 1].min() + 0.025, bot[:, 2].mean()]
    tib = B("^tibia$", s)
    fib = B("^fibula$", s)
    mm = tib[tib[:, 1] < tib[:, 1].min() + 0.006].mean(0)
    lm = fib[fib[:, 1] < fib[:, 1].min() + 0.006].mean(0)
    J["ankle" + s] = (mm + lm) / 2 + np.r_[0, 0.008, 0]
    hum = B("^humerus$", s)
    htop = hum[hum[:, 1] > hum[:, 1].max() - 0.045]
    hmed = htop[(htop[:, 0] * k) < np.median(htop[:, 0] * k)]
    J["shoulder" + s] = sphere_fit(hmed)
    hb = hum[hum[:, 1] < hum[:, 1].min() + 0.03]
    J["elbow" + s] = np.r_[hb[:, 0].mean(), hum[:, 1].min() + 0.012, hb[:, 2].mean()]
    rad = B("^radius$", s)
    lun = B("^lunate bone$", s)
    rb = rad[rad[:, 1] < rad[:, 1].min() + 0.012].mean(0)
    J["wrist" + s] = (rb + lun.mean(0)) / 2
    cla = B("^clavicle$", s)
    medial_x = cla[:, 0] * k
    J["scap" + s] = cla[medial_x < medial_x.min() + 0.012].mean(0)

J["root"] = (J["hipL"] + J["hipR"]) / 2
J["spine"] = B(r"^vertebra l3$").mean(0)
J["chest"] = (B(r"^vertebra t12$").mean(0) + B(r"^vertebra l1$").mean(0)) / 2
J["neck"] = (B(r"^vertebra c7$").mean(0) + B(r"^vertebra t1$").mean(0)) / 2
J["head"] = B(r"^atlas").mean(0) + np.r_[0, 0.012, 0]
# keep the joint chain symmetric about x=0
for a in ("hip", "knee", "ankle", "shoulder", "elbow", "wrist", "scap"):
    left, right = J[a + "L"], J[a + "R"]
    m = (left + right * np.r_[-1, 1, 1]) / 2
    J[a + "L"] = m
    J[a + "R"] = m * np.r_[-1, 1, 1]
for c in ("root", "spine", "chest", "neck", "head"):
    J[c][0] = 0.0

# Finger joints: proximal end of each phalanx (and of the first metacarpal).
# Flexion axis = finger direction x palm normal, so a positive rotation curls
# the finger toward the palm.
FINGERS = {}
for s in ("L", "R"):
    mc = B("metacarpal", s)
    palm_regions = [
        verts(e)
        for e in idx
        if e["cls"] == "digits" and name(e["id"]).lower() == "palm" and side(e["id"]) == s
    ]
    palm_n = (
        (np.concatenate(palm_regions).mean(0) - mc.mean(0)) if palm_regions else np.r_[0, 0, 1.0]
    )
    palm_n /= np.linalg.norm(palm_n)
    for f in range(1, 6):
        pts = {}
        for jn in (1, 2, 3):
            seg = f"f{f}{s}{jn}"
            vs = [verts(e) for e in bones if e["seg"] == seg]
            if not vs:
                continue
            v = np.concatenate(vs)
            c = v.mean(0)
            _, _, vt = np.linalg.svd(v - c, full_matrices=False)
            ax = vt[0]
            if np.dot(ax, c - J["wrist" + s]) < 0:
                ax = -ax  # point distally
            proj = (v - c) @ ax
            prox = v[proj < np.quantile(proj, 0.1)].mean(0)
            dist = v[proj > np.quantile(proj, 0.9)].mean(0)
            pts[jn] = (prox, dist)
        for jn, (prox, dist) in pts.items():
            seg = f"f{f}{s}{jn}"
            J[seg] = prox
            d = dist - prox
            d /= np.linalg.norm(d)
            toward = palm_n
            if f == 1:
                # thumb opposition: curl across the palm toward the index finger
                idx_mcp = np.concatenate([verts(e) for e in bones if e["seg"] == f"f2{s}1"]).mean(0)
                across = idx_mcp - prox
                across /= np.linalg.norm(across)
                toward = 0.55 * palm_n + 0.75 * across
            axis = np.cross(d, toward)
            axis /= np.linalg.norm(axis) + 1e-9
            FINGERS[seg] = {"axis": np.round(axis, 4).tolist(), "dir": np.round(d, 4).tolist()}
    mcp = np.mean([J[f"f{f}{s}1"] for f in range(2, 6)], axis=0)
    J["grip" + s] = 0.5 * (mc.mean(0) + mcp) + palm_n * 0.018
for s in ("L", "R"):
    for k in (1, 2, 3):
        J[f"tw{k}{s}"] = J["elbow" + s] + (J["wrist" + s] - J["elbow" + s]) * k / 4


def split_forearm(v, W):
    """Spread elbow-segment weight along the forearm: elbow, tw1-3, wrist."""
    for s in ("L", "R"):
        e = SI["elbow" + s]
        we = W[:, e].copy()  # copy: the column is zeroed below
        if not we.any():
            continue
        ax = J["wrist" + s] - J["elbow" + s]
        ln = np.linalg.norm(ax)
        t = np.clip(((v - J["elbow" + s]) @ ax) / (ln * ln), 0, 1)
        knots = [e, SI[f"tw1{s}"], SI[f"tw2{s}"], SI[f"tw3{s}"], SI["wrist" + s]]
        k = np.minimum((t * 4).astype(int), 3)
        f = t * 4 - k
        W[:, e] = 0
        for i in range(4):
            sel = k == i
            W[sel, knots[i]] += we[sel] * (1 - f[sel])
            W[sel, knots[i + 1]] += we[sel] * f[sel]
    return W


missing = [sg for sg in SEGS if sg not in J]
if missing:
    raise SystemExit(f"missing joints {missing}")
print("joints", {k: np.round(v, 3).tolist() for k, v in J.items()})

# ----------------------------------------------------------------------------- skin weights
seg_pts = {}
for e in bones:
    seg_pts.setdefault(e["seg"], []).append(verts(e))
TREES = {s: cKDTree(np.concatenate(v)[::2]) for s, v in seg_pts.items()}


def adjacency_of(tri, n):
    r = np.r_[tri[:, 0], tri[:, 1], tri[:, 2], tri[:, 1], tri[:, 2], tri[:, 0]]
    c = np.r_[tri[:, 1], tri[:, 2], tri[:, 0], tri[:, 0], tri[:, 1], tri[:, 2]]
    A = sparse.coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)).tocsr()
    A.data[:] = 1
    deg = np.asarray(A.sum(1)).ravel()
    deg[deg == 0] = 1
    return sparse.diags(1 / deg) @ A


def adjacency(e):
    tri = I[e["i0"] : e["i0"] + e["in"]].reshape(-1, 3).astype(np.int64)
    return adjacency_of(tri, e["vn"])


SIGMA = 0.018


def bone_weights(v, soft=1.0):
    """
    Unsmoothed weights from distance to the bone surfaces of each segment.
    `soft` widens the blend between segments (the skin lies further from the
    bones than the muscles do and has to stretch across joints in one piece).
    """
    D = np.full((len(v), len(SEGS)), np.inf)
    for s, t in TREES.items():
        D[:, SI[s]] = t.query(v, k=1, distance_upper_bound=0.35)[0]
    nearest = D.argmin(1)
    W = np.zeros_like(D)
    for si in np.unique(nearest):
        rows = nearest == si
        allowed = [SI[x] for x in NEIGH[SEGS[si]]]
        d0 = D[rows, si][:, None]
        # Short finger bones need tight blending so digits hinge at the joints
        # instead of bending like rubber; the palm blends a little wider.
        seg_name = SEGS[si]
        sigma = (
            0.005 if seg_name[0] == "f" else 0.009 if seg_name.startswith("wrist") else SIGMA * soft
        )
        sub = np.exp(-(D[rows][:, allowed] - d0) / sigma)
        sub[~np.isfinite(sub)] = 0
        W[np.ix_(np.where(rows)[0], allowed)] = sub
    W /= W.sum(1, keepdims=True)
    return W


def soft_weights(e, smooth_iters=8):
    W = bone_weights(verts(e))
    if smooth_iters and e["vn"] > 3:
        A = adjacency(e)
        for _ in range(smooth_iters):
            W = 0.5 * W + 0.5 * (A @ W)
    return W


def top4(W):
    order = np.argsort(-W, axis=1)[:, :4]
    w = np.take_along_axis(W, order, 1)
    w[w < 0.01] = 0
    tot = w.sum(1, keepdims=True)
    if (tot <= 0).any() or not np.isfinite(tot).all():
        raise SystemExit("vertex with no skin weight")
    w /= tot
    return order.astype(np.uint8), w.astype(np.float32)


# ----------------------------------------------------------------------------- muscle groups / layers
GROUPS = [
    ("chest", r"pectoralis major"),
    ("delts", r"deltoid"),
    ("biceps", r"biceps brachii|brachialis muscle|coracobrachialis"),
    ("triceps", r"triceps brachii|anconeus"),
    (
        "forearms",
        r"brachioradialis|carpi|digitorum superficialis|digitorum profundus|palmaris|pronator|supinator|pollicis longus|extensor digitorum muscle|digiti minimi muscle$|extensor indicis",
    ),
    ("lats", r"latissimus dorsi"),
    ("traps", r"trapezius|levator scapulae"),
    ("upperback", r"rhomboid|infraspinatus|supraspinatus|teres|subscapularis"),
    ("abs", r"rectus abdominis|pyramidalis|linea alba"),
    ("obliques", r"oblique|transversus abdominis|serratus anterior"),
    (
        "lowerback",
        r"iliocostalis|longissimus|spinalis|multifidus|quadratus lumborum|thoracolumbar|semispinalis",
    ),
    ("glutes", r"gluteus|tensor fasciae latae|iliotibial"),
    ("quads", r"rectus femoris|vastus|articularis genus"),
    ("hams", r"biceps femoris|semitendinosus|semimembranosus"),
    ("calves", r"gastrocnemius|soleus|plantaris|calcane"),
    ("adductors", r"adductor (longus|brevis|magnus|minimus)|gracilis|pectineus"),
]
SUPERFICIAL = r"pectoralis major|deltoid|trapezius|latissimus|external abdominal oblique|rectus abdominis|sternocleidomastoid|platysma|gluteus maximus|tensor fasciae|sartorius|rectus femoris|gracilis|biceps brachii|long head of triceps|lateral head of triceps|brachioradialis|flexor carpi|palmaris longus|extensor carpi|extensor digitorum muscle|gastrocnemius|long head of biceps femoris|semitendinosus|serratus anterior|iliotibial|thoracolumbar|aponeurosis|retinacul|linea alba|transverse meta"


# Extra belly thickness (metres) for a trained, muscular build.
HYPERTROPHY = {
    "chest": 0.019,
    "delts": 0.02,
    "biceps": 0.015,
    "triceps": 0.015,
    "forearms": 0.007,
    "lats": 0.016,
    "traps": 0.012,
    "upperback": 0.006,
    "abs": 0.004,
    "obliques": 0.002,
    "lowerback": 0.003,
    "glutes": 0.009,
    "quads": 0.014,
    "hams": 0.011,
    "calves": 0.011,
    "adductors": 0.003,
}


def group_of(n):
    n = n.lower()
    for g, rx in GROUPS:
        if re.search(rx, n):
            return g
    return None


# attachment patches: insertions.<key>_(origin|insertion)[_n]_<side> -> muscular.<key>_<side>
attach = {}
for e in idx:
    if e["cls"] != "insertion" or not e["id"]:
        continue
    m = re.match(r"insertions\.(.+?)_(origin|insertion)(?:_\d+)?_([lr])$", e["id"])
    if not m:
        continue
    key, kind, sd = m.groups()
    attach.setdefault(f"muscular.{key}_{sd}", {}).setdefault(kind, []).append(verts(e))

# ----------------------------------------------------------------------------- build outputs
out = {
    g: {"P": [], "N": [], "I": [], "J": [], "W": [], "S": [], "F": [], "M": []}
    for g in ("muscle", "fascia", "bone", "eye", "digits")
}
structs = []
voff = dict.fromkeys(out, 0)
skipped = 0
for e in idx:
    cls = e["cls"]
    if cls not in out or e["vn"] < 3:
        continue
    sid = len(structs)
    v = verts(e)
    n = N[e["v0"] : e["v0"] + e["vn"]]
    tri = I[e["i0"] : e["i0"] + e["in"]].astype(np.int64) + voff[cls]
    nm = name(e["id"])
    rec = {
        "sid": sid,
        "id": e["id"],
        "name": nm,
        "latin": latin(e["id"]),
        "type": cls,
        "side": side(e["id"]),
        "parent": parent(e["id"]),
    }
    if cls == "bone" and e["seg"].startswith("elbow"):
        # radius and ulna twist with the forearm
        seg = e["seg"]
        Wd = np.zeros((len(v), len(SEGS)))
        Wd[:, SI[seg]] = 1
        j, w = top4(split_forearm(v, Wd))
        rec["seg"] = seg
    elif cls == "bone":
        seg = e["seg"]
        j = np.zeros((len(v), 4), np.uint8)
        j[:, 0] = SI[seg]
        w = np.zeros((len(v), 4), np.float32)
        w[:, 0] = 1
        if "patella" in nm.lower():  # the patella rides between femur and tibia
            j[:, 1] = SI["knee" + side(e["id"])]
            w[:, 0] = 0.4
            w[:, 1] = 0.6
        rec["seg"] = seg
    else:
        near_hand = verts(e)[:, 1].mean() < 0.95 and abs(verts(e)[:, 0].mean()) > 0.2
        W = soft_weights(e, smooth_iters=3 if cls == "digits" or near_hand else 8)
        j, w = top4(split_forearm(v, W))
        rec["seg"] = SEGS[int(np.bincount(j[:, 0], minlength=len(SEGS)).argmax())]
    F = np.zeros((len(v), 3), np.float32)
    M = np.zeros((len(v), 4), np.float32)
    if cls in ("muscle", "fascia"):
        g = group_of(nm)
        rec["group"] = g
        rec["superficial"] = bool(re.search(SUPERFICIAL, nm.lower()))
        at = attach.get(e["id"], {})
        # principal-axis extremes of the belly, used where the atlas has no patch
        c = v.mean(0)
        u, s_, vt = np.linalg.svd(v - c, full_matrices=False)
        ax = vt[0]
        proj = (v - c) @ ax
        lo = v[proj < np.quantile(proj, 0.04)].mean(0)
        hi = v[proj > np.quantile(proj, 0.96)].mean(0)
        O = np.concatenate(at["origin"]).mean(0) if "origin" in at else None
        Ins = np.concatenate(at["insertion"]).mean(0) if "insertion" in at else None
        if O is None and Ins is None:
            O, Ins = lo, hi
        elif O is None:
            O = lo if np.linalg.norm(lo - Ins) > np.linalg.norm(hi - Ins) else hi
        elif Ins is None:
            Ins = lo if np.linalg.norm(lo - O) > np.linalg.norm(hi - O) else hi
        rec["attach"] = (
            "atlas" if ("origin" in at and "insertion" in at) else ("partial" if at else "pca")
        )
        L = np.linalg.norm(Ins - O) + 1e-6
        axis = (Ins - O) / L
        # fibres converge on both attachments
        dI = Ins - v
        dO = O - v
        f = dI / (np.linalg.norm(dI, axis=1, keepdims=True) + 1e-6) - dO / (
            np.linalg.norm(dO, axis=1, keepdims=True) + 1e-6
        )
        f /= np.linalg.norm(f, axis=1, keepdims=True) + 1e-9
        F = f.astype(np.float32)
        t = np.clip(((v - O) @ axis) / L, 0, 1)
        foot = O + np.outer(t * L, axis)
        r = np.linalg.norm(v - foot, axis=1)
        rmax = np.quantile(r, 0.95) + 1e-6
        # Tendon / aponeurosis: tissue that is THIN (distance to the opposite
        # surface of the same structure) and lies NEAR an attachment.
        tree_s = cKDTree(v)
        nb_d, nb_i = tree_s.query(v, k=min(24, len(v)), distance_upper_bound=0.02)
        thick = np.full(len(v), 0.02)
        valid = np.isfinite(nb_d)
        nb_i = np.where(valid, nb_i, 0)
        opp = (np.einsum("ij,ikj->ik", n, n[nb_i]) < -0.3) & valid
        dd = np.where(opp, nb_d, np.inf).min(1)
        thick = np.where(np.isfinite(dd), dd, 0.02)
        thin = np.clip((0.0075 - thick) / 0.004, 0, 1)
        patches = [np.concatenate(at[k]) for k in ("origin", "insertion") if k in at]
        if patches:
            dpatch = cKDTree(np.concatenate(patches)).query(v, k=1)[0]
            near = np.clip(1 - (dpatch - 0.012) / 0.05, 0, 1)
        else:
            near = np.clip((np.abs(t - 0.5) - 0.3) / 0.15, 0, 1)
        tendon = thin * near
        # smooth the mask over the surface so tendon edges are soft
        A = adjacency(e)
        for _ in range(4):
            tendon = 0.5 * tendon + 0.5 * (A @ tendon)
        if cls == "fascia":
            tendon[:] = 1
        M = np.c_[t, np.clip(r / 0.08, 0, 1), tendon, np.zeros(len(v))].astype(np.float32)
        # Trained build: thicken the bellies of the muscles the programme
        # trains (never the tendons), so the figure reads as an athlete.
        grow = HYPERTROPHY.get(g, 0.0)
        if grow and cls == "muscle":
            belly = np.sin(np.pi * t) ** 1.3 * (1 - tendon)
            v = v + n * (grow * belly)[:, None]
        rec["O"] = np.round(O, 5).tolist()
        rec["I"] = np.round(Ins, 5).tolist()
        rec["L0"] = round(float(L), 5)
        # which skeletal segment each attachment rides on
        segO = SEGS[int(np.argmin([TREES[s].query(O)[0] if s in TREES else 9 for s in SEGS]))]
        segI = SEGS[int(np.argmin([TREES[s].query(Ins)[0] if s in TREES else 9 for s in SEGS]))]
        rec["segO"] = segO
        rec["segI"] = segI
    o = out[cls]
    o["P"].append(v.astype(np.float32))
    o["N"].append(n.astype(np.float32))
    o["I"].append(tri.astype(np.uint32))
    o["J"].append(j)
    o["W"].append(w)
    o["S"].append(np.full(len(v), sid, np.uint16))
    o["F"].append(F)
    o["M"].append(M)
    voff[cls] += len(v)
    if cls == "digits" and "nail" in nm.lower():
        rec["nail"] = True
    rec["mesh"] = cls
    structs.append(rec)

# ----------------------------------------------------------------------------- skin: the athlete
# The atlas' skin regions, welded into one surface and drawn tight over the
# (thickened) muscles: subcutaneous fat is removed by pulling every skin vertex
# down to a thin layer above the nearest muscle, fascia or bone, so the muscle
# relief shows through. Head, hands and feet keep the atlas surface. Each skin
# vertex remembers the muscle beneath it, which is how activation, contraction
# and picking reach the skin at runtime.
SKIN_T = 0.0028  # skin + fascia thickness left above the muscles
SHORTS_T = 0.0075  # fabric stands a little further off
HAIR_RX = r"^hairs of (head|eyebrow)|^eyelashes"
HAND_RX = r"of hand$|^palm$|^nail plate$|^perionyx$"
FOOT_RX = (
    r"of foot|^sole$|^heel region$|malleol|\(foot\)|hallucial|metatarsal region|region of ankle"
)
ARM_RX = (
    r"hand|forearm|wrist|elbow|cubital|region of arm|^palm$|nail plate$|perionyx$|foveola|bicipital"
)


def chain(sid):
    out_ = []
    while sid:
        out_.append(sid)
        sid = parent(sid)
    return " ".join(out_)


def vertex_normals(V, T):
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    nv = np.zeros_like(V)
    for k in range(3):
        np.add.at(nv, T[:, k], fn)
    return nv / (np.linalg.norm(nv, axis=1, keepdims=True) + 1e-12)


def diffuse(A, x, iters, keep=None):
    for _ in range(iters):
        y = 0.5 * x + 0.5 * (A @ x)
        x = y if keep is None else np.where(keep if x.ndim == 1 else keep[:, None], x, y)
    return x


def outer_sheet(v, tri, depth):
    """
    Faces of the outer sheet of a closed slab. A ray cast into the slab from
    each face finds the sheet opposite; walls (long or oblique crossings) are
    dropped, the remaining faces fall into connected sheets, and a sheet is the
    outer one when it lies further from the muscles than what it faces.
    """
    key = np.round(v / 2e-5).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    tw = inv.ravel()[tri]
    a, b, c = v[tri[:, 0]], v[tri[:, 1]], v[tri[:, 2]]
    fn = np.cross(b - a, c - a)
    area = np.linalg.norm(fn, axis=1) + 1e-12
    fn /= area[:, None]
    cen = (a + b + c) / 3
    e1, e2 = b - a, c - a
    nf = len(tri)
    hit_t = np.full(nf, np.inf)
    hit_f = np.full(nf, -1)
    for lo in range(0, nf, 256):  # Moller-Trumbore, rays x triangles
        o = cen[lo : lo + 256, None, :]
        d = -fn[lo : lo + 256, None, :]
        p = np.cross(d, e2[None])
        det = (e1[None] * p).sum(2)
        ok = np.abs(det) > 1e-14
        inv_det = 1 / np.where(ok, det, 1)
        tv = o - a[None]
        u = (tv * p).sum(2) * inv_det
        q = np.cross(tv, e1[None])
        w = (d * q).sum(2) * inv_det
        t = (e2[None] * q).sum(2) * inv_det
        ok &= (u >= -1e-6) & (w >= -1e-6) & (u + w <= 1 + 1e-6) & (t > 1e-6)
        ok[np.arange(o.shape[0]), np.arange(lo, lo + o.shape[0])] = False
        t = np.where(ok, t, np.inf)
        hit_f[lo : lo + 256] = t.argmin(1)
        hit_t[lo : lo + 256] = t.min(1)
    found = np.isfinite(hit_t)
    thick = np.median(hit_t[found]) if found.any() else 0.0
    sheet = found & (hit_t < 3 * thick + 1e-4) & ((fn * fn[hit_f]).sum(1) < -0.5)
    across = cen - fn * np.where(found, hit_t, 0)[:, None]
    score = np.where(sheet, depth(cen) - depth(across), 0) * area
    # connected sheets: faces that share an edge and face the same way. (The two
    # sheets of a slab can touch along a knife edge; there they face opposite.)
    fi = np.where(sheet)[0]
    if not len(fi):
        return np.zeros(nf, bool)
    tf = tw[fi]
    und = np.sort(np.concatenate([tf[:, [0, 1]], tf[:, [1, 2]], tf[:, [2, 0]]]), axis=1)
    owner = np.tile(np.arange(len(fi)), 3)
    _, eid = np.unique(und, axis=0, return_inverse=True)
    order = np.argsort(eid.ravel(), kind="stable")
    eo, fo = eid.ravel()[order], owner[order]
    same = eo[1:] == eo[:-1]
    p, q = fo[:-1][same], fo[1:][same]
    agree = (fn[fi[p]] * fn[fi[q]]).sum(1) > 0.2
    g = sparse.coo_matrix((np.ones(agree.sum()), (p[agree], q[agree])), shape=(len(fi), len(fi)))
    _, lab = sparse.csgraph.connected_components(g, directed=False)
    total = np.bincount(lab, weights=score[fi])
    keep = np.zeros(nf, bool)
    keep[fi] = total[lab] > 0
    return keep


def open_edges(T):
    """Directed edges that belong to one face only (the rim of a gap)."""
    he = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    und = np.sort(he, axis=1)
    _, inv, cnt = np.unique(und, axis=0, return_inverse=True, return_counts=True)
    return he[cnt[inv.ravel()] == 1]


def stitch(V, T, ok_vert, eps=0.003):
    """
    Neighbouring regions meet along the same curve but with different vertices.
    Wherever a rim vertex of one face lies on the rim edge of another, split
    that edge there, so both sides share every vertex along the seam.
    """
    he = open_edges(T)
    he = he[ok_vert[he].all(1)]
    if not len(he):
        return T
    rim = np.unique(he)
    tree = cKDTree(V[rim])
    und = np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), axis=1)
    face_of = {
        (int(a), int(b)): f for f, (a, b) in zip(np.tile(np.arange(len(T)), 3), und, strict=True)
    }
    split = {}
    for a, b in he:
        pa, pb = V[a], V[b]
        ab = pb - pa
        ln = np.linalg.norm(ab)
        if ln < 1e-9:
            continue
        near = rim[tree.query_ball_point((pa + pb) / 2, ln / 2 + eps)]
        near = near[(near != a) & (near != b)]
        if not len(near):
            continue
        t = ((V[near] - pa) @ ab) / (ln * ln)
        off = np.linalg.norm(V[near] - (pa + np.outer(t, ab)), axis=1)
        ok = (t * ln > eps) & ((1 - t) * ln > eps) & (off < eps)
        if ok.any():
            order = np.argsort(t[ok])
            f = face_of[(min(int(a), int(b)), max(int(a), int(b)))]
            split.setdefault(f, []).append((int(a), int(b), near[ok][order].tolist()))
    if not split:
        return T
    keep = np.ones(len(T), bool)
    new = []
    for f, cuts in split.items():
        keep[f] = False
        poly = [int(x) for x in T[f]]
        for a, b, pts in cuts:  # insert the points between a and b on the face's outline
            i = poly.index(a)
            if poly[(i + 1) % len(poly)] == b:
                poly[i + 1 : i + 1] = pts
        # fan from the corner that touches the fewest split edges
        apex = max(T[f], key=lambda x: sum(x not in (a, b) for a, b, _ in cuts))
        k = poly.index(int(apex))
        poly = poly[k:] + poly[:k]
        for i in range(1, len(poly) - 1):
            new.append((poly[0], poly[i], poly[i + 1]))
    T = np.concatenate([T[keep], np.array(new, dtype=T.dtype)])
    return T[(T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])]


def close_gaps(V, T, flags, ok_vert, snap=0.003, max_size=0.06, big_at=None, big_size=0.25):
    """
    The outer sheets of neighbouring regions do not tile exactly. Zip rims that
    run side by side (snap their vertices together), then fan-fill the small
    gaps that remain (and the one large gap around `big_at`, where a region was
    left out on purpose). Returns the new vertices, faces and per-vertex flags.
    """
    rim = np.unique(open_edges(T))
    rim = rim[ok_vert[rim]]
    pairs = cKDTree(V[rim]).query_pairs(snap, output_type="ndarray")
    if len(pairs):
        g = sparse.coo_matrix(
            (np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(rim), len(rim))
        )
        _, lab = sparse.csgraph.connected_components(g, directed=False)
        first = np.full(lab.max() + 1, -1)
        first[lab[::-1]] = rim[::-1]
        to = np.arange(len(V))
        to[rim] = first[lab]
        T = to[T]
        T = T[(T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])]
    he = open_edges(T)
    he = he[ok_vert[he].all(1)]
    newV, newT, newF = [], [], []
    if len(he):
        rim, loc = np.unique(he, return_inverse=True)
        loc = loc.reshape(-1, 2)
        g = sparse.coo_matrix(
            (np.ones(len(loc)), (loc[:, 0], loc[:, 1])), shape=(len(rim), len(rim))
        )
        _, lab = sparse.csgraph.connected_components(g, directed=False)
        for k in range(lab.max() + 1):
            ed = he[lab[loc[:, 0]] == k]
            pts = V[np.unique(ed)]
            c = pts.mean(0)
            size = np.linalg.norm(np.ptp(pts, axis=0))
            limit = (
                big_size if big_at is not None and np.linalg.norm(c - big_at) < 0.09 else max_size
            )
            if len(ed) < 3 or size > limit:
                continue
            ci = len(V) + len(newV)
            newV.append(c)
            newF.append(flags[np.unique(ed)].min(0))
            for a, b in ed:  # the rim runs a->b on its face, so the fill runs b->a
                newT.append((b, a, ci))
    if newV:
        V = np.concatenate([V, np.array(newV)])
        T = np.concatenate([T, np.array(newT)])
        flags = np.concatenate([flags, np.array(newF)])
    used = np.unique(T)
    remap = np.full(len(V), -1)
    remap[used] = np.arange(len(used))
    return V[used], remap[T], flags[used]


def subdivide(V, T, flags, which):
    """Split the chosen faces 1 -> 4 (edge midpoints); the rest stay as they are."""
    Ts = T[which]
    und = np.sort(np.concatenate([Ts[:, [0, 1]], Ts[:, [1, 2]], Ts[:, [2, 0]]]), axis=1)
    edges, inv = np.unique(und, axis=0, return_inverse=True)
    mid = len(V) + inv.ravel().reshape(3, -1).T  # per face: midpoints of ab, bc, ca
    a, b, c = Ts[:, 0], Ts[:, 1], Ts[:, 2]
    ab, bc, ca = mid[:, 0], mid[:, 1], mid[:, 2]
    T4 = np.concatenate([np.c_[a, ab, ca], np.c_[ab, b, bc], np.c_[ca, bc, c], np.c_[ab, bc, ca]])
    V = np.concatenate([V, V[edges].mean(1)])
    flags = np.concatenate([flags, flags[edges].mean(1)])
    return V, np.concatenate([T[~which], T4]), flags


def build_skin():
    parts = [
        e
        for e in idx
        if e["system"] == "regions" and e["id"] and e["vn"] >= 3 and "pubic" not in e["id"]
    ]
    uro = np.concatenate([verts(e) for e in parts if "urogenital" in e["id"]])
    parts = [e for e in parts if "urogenital" not in e["id"]]  # closed over, under the shorts
    surf = [e for e in parts if not re.search(HAIR_RX, name(e["id"]).lower())]
    hair = [e for e in parts if re.search(HAIR_RX, name(e["id"]).lower())]

    # ---- weld the regions into one surface
    # Every atlas region is a closed slab (outer face, inner face, side walls).
    # On the body only the outer faces are kept, so the regions join into one
    # sheet; head, hands and feet keep their slabs (ears and digits are thin).
    core = cKDTree(np.concatenate([verts(e) for e in idx if e["cls"] in ("muscle", "bone")]))
    regions = []
    for e in surf:
        nm = name(e["id"]).lower()
        v = verts(e)
        tri = I[e["i0"] : e["i0"] + e["in"]].astype(np.int64).reshape(-1, 3)
        # mirrored (left) regions come inside-out: make every slab face outward
        vn = N[e["v0"] : e["v0"] + e["vn"]]
        if np.einsum("ij,ij->i", v[tri[:, 0]], np.cross(v[tri[:, 1]], v[tri[:, 2]])).sum() < 0:
            tri = tri[:, ::-1]
            vn = -vn
        head = "regions_of_head" in chain(e["id"])
        hand = bool(re.search(HAND_RX, nm))
        foot = bool(re.search(FOOT_RX, nm))
        slab = head or hand or foot
        keep = np.ones(len(tri), bool) if slab else outer_sheet(v, tri, lambda p: core.query(p)[0])
        regions.append({"e": e, "nm": nm, "v": v, "vn": vn, "tri": tri, "keep": keep, "slab": slab})
        regions[-1]["flags"] = (head, hand, foot)

    # Second pass: faces next to the outer sheet that continue it (same level,
    # same facing) belong to it too. This closes the corners where regions meet
    # and recovers regions whose slab is too thin to split by ray casting.
    body = [r for r in regions if not r["slab"]]
    cen = np.concatenate([r["v"][r["tri"]].mean(1) for r in body])
    fnr = np.concatenate(
        [
            np.cross(
                r["v"][r["tri"][:, 1]] - r["v"][r["tri"][:, 0]],
                r["v"][r["tri"][:, 2]] - r["v"][r["tri"][:, 0]],
            )
            for r in body
        ]
    )
    fnr /= np.linalg.norm(fnr, axis=1, keepdims=True) + 1e-12
    acc = np.concatenate([r["keep"] for r in body])
    for _ in range(8):
        todo = np.where(~acc)[0]
        d, qi = cKDTree(cen[acc]).query(cen[todo], distance_upper_bound=0.02)
        ok = np.isfinite(d)
        qa = np.where(acc)[0][np.where(ok, qi, 0)]
        level = ((cen[todo] - cen[qa]) * fnr[qa]).sum(1)
        ok &= ((fnr[todo] * fnr[qa]).sum(1) > 0.6) & (level > -0.0015) & (level < 0.004)
        if not ok.any():
            break
        acc[todo[ok]] = True
    k = 0
    for r in body:
        r["keep"] = acc[k : k + len(r["tri"])]
        k += len(r["tri"])

    Vs, T0, flags0 = [], [], []
    off = 0
    for r in regions:
        e, nm, v, tri = r["e"], r["nm"], r["v"], r["tri"][r["keep"]]
        head, hand, foot = r["flags"]
        if not len(tri):
            continue
        used = np.unique(tri)
        remap = np.full(len(v), -1)
        remap[used] = np.arange(len(used))
        Vs.append(v[used])
        T0.append(remap[tri] + off)
        fl = np.zeros((len(used), 6))
        fl[:, 5] = "urogenital" in e["id"]
        fl[:, 0] = head
        fl[:, 1] = hand
        fl[:, 2] = foot
        fl[:, 3] = not re.search(ARM_RX, nm)  # may carry the shorts
        fl[:, 4] = "nail plate" in nm
        flags0.append(fl)
        off += len(used)
    V0 = np.concatenate(Vs)
    T0 = np.concatenate(T0)
    flags0 = np.concatenate(flags0)
    key = np.round(V0 / 2e-5).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    V = V0[first]
    T = inv[T0]
    T = T[(T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])]
    FL = np.zeros((len(V), 7))
    np.maximum.at(FL[:, :5], inv, flags0[:, :5])
    FL[:, 5:] = 1
    np.minimum.at(FL[:, 5], inv, flags0[:, 4])  # nail only where every copy is nail
    np.minimum.at(FL[:, 6], inv, flags0[:, 5])  # strictly inside the urogenital region
    T = T[np.unique(np.sort(T, axis=1), axis=0, return_index=True)[1]]  # overlaid sub-regions
    before = len(open_edges(T))
    slabby = np.clip(FL[:, 0] + FL[:, 1] + FL[:, 2], 0, 1) > 0
    for _ in range(3):
        T = stitch(V, T, ~slabby)
    V, T, FL = close_gaps(V, T, FL, ~slabby, big_at=uro.mean(0))
    # finer mesh on the body, so the skin can follow the muscle relief
    slabby = np.clip(FL[:, 0] + FL[:, 1] + FL[:, 2], 0, 1) > 0
    V, T, FL = subdivide(V, T, FL, ~slabby[T].all(1))
    nv = len(V)
    nail = (FL[:, 5] > 0.99).astype(float)
    slabby_sub = np.clip(FL[:, 0] + FL[:, 1] + FL[:, 2], 0, 1) > 0
    A = adjacency_of(T, nv)
    oe = open_edges(T)
    oe = oe[~slabby_sub[oe].any(1)]
    print("skin", nv, "verts", len(T), "tris; open edges on the body", before, "->", len(oe))

    # ---- what lies underneath: muscles (as built above), fasciae, bones
    def cloud_of(g):
        Pg = np.concatenate(out[g]["P"]).astype(np.float64)
        Tg = np.concatenate(out[g]["I"]).reshape(-1, 3)
        return np.concatenate([Pg, Pg[Tg].mean(1)])

    cloud = np.concatenate([cloud_of(g) for g in ("muscle", "fascia", "bone")])
    tree = cKDTree(cloud)

    # ---- shorts band (bind-space heights)
    navel = np.concatenate([verts(e) for e in surf if "umbilicus" in e["id"]])
    crotch = float(np.quantile(uro[:, 1], 0.05))
    waist = float(navel[:, 1].mean() - 0.045)
    hem = crotch - 0.11
    elig = FL[:, 3] > 0.5
    in_band = elig & (V[:, 1] > hem) & (V[:, 1] < waist)
    band = diffuse(A, in_band.astype(float), 3)

    # ---- draw the skin tight
    lean = (np.clip(FL[:, 0] + FL[:, 1] + FL[:, 2], 0, 1) == 0).astype(float)
    lean = diffuse(A, lean, 16, keep=lean == 0)  # ease out toward head/hands/feet
    thick = SKIN_T + (SHORTS_T - SKIN_T) * band

    def wrap(V, amount):
        nrm = vertex_normals(V, T)
        d, qi = tree.query(V, workers=-1)
        to = cloud[qi] - V
        d = np.maximum(d, 1e-6)
        along = (to * nrm).sum(1)
        pull = to * (1 - thick / d)[:, None]  # down to the thin layer / back out of it
        under = (along > 0) & (d < 0.03)  # the muscle now stands proud of the old skin
        pull[under] = nrm[under] * (along[under] + thick[under])[:, None]
        ln = np.linalg.norm(pull, axis=1, keepdims=True)
        pull *= np.minimum(1, 0.05 / (ln + 1e-9))
        return V + pull * (amount * lean)[:, None]

    # smoothing reaches one edge per pass: finer meshes need more passes
    # for the same result (counts below are for 5 mm edges)
    bt = T[lean[T].min(1) > 0.5]
    edge = np.linalg.norm(V[bt[:, 0]] - V[bt[:, 1]], axis=1).mean()
    fine = (0.005 / edge) ** 2

    def relax(V, iters, w):
        for _ in range(max(1, round(iters * fine))):
            V = V + (A @ V - V) * (0.5 * w)[:, None]
        return V

    body = lean * (1 - band)
    V = wrap(V, 1.0)
    V = relax(V, 3, body)
    V = wrap(V, 0.9)
    V = relax(V, 2, 0.7 * body)
    V = wrap(V, 0.6)
    V = relax(V, 2, 0.5 * body)
    # fabric: smooth the band into a plain garment, then stand it off the body
    V = relax(V, 40, band)
    V = wrap(V, 0.7 * band)
    V = relax(V, 10, band)
    nrm = vertex_normals(V, T)
    # Head, hands and feet keep the atlas' own shading normals. A welded vertex
    # on a slab's rim has several (sheet, wall); take the one facing outward.
    sv = np.concatenate([r["v"] for r in regions if r["slab"]])
    sn = np.concatenate([r["vn"] for r in regions if r["slab"]])
    still = np.where(slabby_sub)[0]
    dn, qn = cKDTree(sv).query(V[still], k=8, distance_upper_bound=3e-5)
    cand = sn[np.minimum(qn, len(sn) - 1)]
    dots = np.where(np.isfinite(dn), np.einsum("ikj,ij->ik", cand, nrm[still]), -2)
    best = dots.argmax(1)
    found = dots.max(1) > -1.5
    nrm[still[found]] = cand[np.arange(len(still)), best][found]

    # ---- skinning (same bone-distance scheme as the muscles)
    W = bone_weights(V, soft=1.8)
    handy = np.clip(FL[:, 1] + FL[:, 4], 0, 1) > 0
    W = diffuse(A, W, 4)
    W = diffuse(A, W, round(36 * fine), keep=handy)
    W /= W.sum(1, keepdims=True)
    j, w = top4(split_forearm(V, W))

    # ---- the muscle beneath each vertex
    mP = np.concatenate(out["muscle"]["P"]).astype(np.float64)
    mS = np.concatenate(out["muscle"]["S"])
    mM = np.concatenate(out["muscle"]["M"])
    md, mi = cKDTree(mP).query(V, workers=-1)
    S = mS[mi].astype(np.uint16)
    cover = np.clip(1 - (md - 0.012) / 0.014, 0, 1) * lean
    cover = diffuse(A, cover, 1)
    # how far inside its muscle's patch a vertex is: 0 on the border, 1 inside
    Ac = A.tocoo()
    same = np.bincount(Ac.row, weights=Ac.data * (S[Ac.row] == S[Ac.col]), minlength=nv)
    inside = np.clip((A @ same - 0.55) / 0.4, 0, 1)
    # swelling with contraction: the belly only, fading out toward the borders
    # so neighbouring muscles in different states never step against each other
    belly = np.clip(np.sin(np.pi * mM[mi, 0]), 0, 1) ** 1.3 * (1 - mM[mi, 2])
    swell = diffuse(A, np.minimum(mM[mi, 1], 0.3) / 0.3 * belly * inside * cover, 1)
    M = np.c_[mM[mi, 0], swell, mM[mi, 2], cover * (0.5 + 0.5 * inside)].astype(np.float32)

    # ---- shading helpers: occlusion (armpits, between the legs) and relief
    # (creases between muscles darken, bellies stay bright)
    tree_s = cKDTree(V)
    occ = np.zeros(nv)
    for dist_, wgt in ((0.012, 0.4), (0.03, 0.35), (0.06, 0.25)):
        dd, _ = tree_s.query(V + nrm * dist_, workers=-1)
        occ += wgt * np.clip(1 - dd / (0.8 * dist_), 0, 1)
    ao = np.clip(1 - 0.8 * occ, 0.3, 1)
    # relief at a fixed physical scale (about 1.5 cm), whatever the mesh density
    wide = diffuse(A, V, max(2, round(6 * fine)))
    relief = diffuse(A, np.clip(0.5 - ((wide - V) * nrm).sum(1) / 0.004, 0, 1), 1)
    F = np.c_[FL[:, 3], np.zeros(nv), nail * FL[:, 4]].astype(np.float32)

    o = out["skin"]
    o["P"].append(V.astype(np.float32))
    o["N"].append(nrm.astype(np.float32))
    o["I"].append(T.astype(np.uint32).ravel())
    o["J"].append(j)
    o["W"].append(w)
    o["S"].append(S)
    o["F"].append(F)
    o["M"].append(M)
    o["A"] = [np.c_[ao, relief].astype(np.float32)]
    base = nv

    # ---- hair, eyebrows, lashes ride on the head
    for e in hair:
        hv = verts(e)
        o["P"].append(hv.astype(np.float32))
        o["N"].append(N[e["v0"] : e["v0"] + e["vn"]].astype(np.float32))
        o["I"].append(I[e["i0"] : e["i0"] + e["in"]].astype(np.uint32) + base)
        hj = np.zeros((len(hv), 4), np.uint8)
        hj[:, 0] = SI["head"]
        hw = np.zeros((len(hv), 4), np.float32)
        hw[:, 0] = 1
        o["J"].append(hj)
        o["W"].append(hw)
        o["S"].append(np.full(len(hv), S[cKDTree(V).query(hv.mean(0))[1]], np.uint16))
        o["F"].append(np.tile(np.float32([0, 1, 0]), (len(hv), 1)))
        o["M"].append(np.zeros((len(hv), 4), np.float32))
        o["A"].append(np.ones((len(hv), 2), np.float32) * np.float32([1, 0.5]))
        base += len(hv)
    o["A"] = [np.concatenate(o["A"])]
    voff["skin"] = base
    return {"waist": round(waist, 4), "hem": round(hem, 4), "crotch": round(crotch, 4)}


out["skin"] = {k: [] for k in ("P", "N", "I", "J", "W", "S", "F", "M")}
SKIN_META = build_skin()

# ----------------------------------------------------------------------------- baked ambient occlusion
# Probe points just above each vertex along its normal; a probe that lands
# close to other geometry means the surface is tucked under a neighbour.
# Two variants: with every structure, and with superficial muscles removed
# (used by the "deep muscles" layer).
render = [g for g in ("muscle", "fascia", "bone", "eye", "digits") if out[g]["P"]]
allP = np.concatenate([np.concatenate(out[g]["P"]) for g in render])
allS = np.concatenate([np.concatenate(out[g]["S"]) for g in render])
superficial_sid = np.array([bool(st.get("superficial")) for st in structs])
deep_mask = ~superficial_sid[allS]
tree_all = cKDTree(allP)
tree_deep = cKDTree(allP[deep_mask])
PROBES = ((0.003, 0.45), (0.007, 0.35), (0.015, 0.2))
for g in render:
    Pg = np.concatenate(out[g]["P"]).astype(np.float64)
    Ng = np.concatenate(out[g]["N"]).astype(np.float64)
    aos = []
    for tree in (tree_all, tree_deep):
        occ = np.zeros(len(Pg))
        for d, w in PROBES:
            dist, _ = tree.query(Pg + Ng * d, k=1, workers=-1)
            occ += w * np.clip(1 - dist / (0.75 * d), 0, 1)
        aos.append(np.clip(1 - 0.85 * occ, 0.25, 1))
    ao = np.c_[aos[0], aos[1]].astype(np.float32)
    out[g]["A"] = [ao]

for g, o in out.items():
    if not o["P"]:
        continue
    spec = {}
    for k, vv in o.items():
        arr = np.ascontiguousarray(np.concatenate(vv))
        arr.tofile(f"{OUT}/{g}.{k}.bin")
        spec[k] = {"dtype": str(arr.dtype), "shape": list(arr.shape)}
    dump_json(spec, f"{OUT}/{g}.spec.json")
    print(g, "verts", voff[g], "tris", sum(len(x) for x in o["I"]) // 3)


# ----------------------------------------------------------------------------- markers (bind space)
def segverts(seg, types=("muscle", "fascia", "bone")):
    arrs = [
        verts(e)
        for e in idx
        if e["cls"] in types and (bone_segment(e["id"]) if e["cls"] == "bone" else None) == seg
    ]
    return np.concatenate(arrs) if arrs else None


allsoft = np.concatenate([verts(e) for e in idx if e["cls"] in ("muscle", "fascia")])
allbone = np.concatenate([verts(e) for e in bones])
everything = np.concatenate([allsoft, allbone])
mk = {}
for s, k in (("L", 1), ("R", -1)):
    foot = everything[
        (everything[:, 1] < J["ankle" + s][1] + 0.02)
        & (np.abs(everything[:, 0] - J["ankle" + s][0]) < 0.09)
    ]
    sole = foot[:, 1].min()
    mk["toe" + s] = [J["ankle" + s][0] + 0.012 * k, sole, foot[:, 2].max()]
    mk["heel" + s] = [B("^calcaneus$", s)[:, 0].mean(), sole, foot[:, 2].min() + 0.012]
    mk["ball" + s] = [B("metatarsal", s)[:, 0].mean(), sole, B("metatarsal", s)[:, 2].max() - 0.008]
    mk["instep" + s] = (B("^navicular", s).mean(0) + np.r_[0, 0.02, 0]).tolist()
    mc = B("metacarpal", s)
    mk["hand" + s] = J["grip" + s].tolist()  # grip / palm-contact point
    mk["palm" + s] = J["grip" + s].tolist()
    pat = B("^patella$", s)
    mk["kneeCap" + s] = pat[pat[:, 2] > pat[:, 2].max() - 0.004].mean(0).tolist()
    gl = [
        verts(e)
        for e in idx
        if e["cls"] == "muscle"
        and name(e["id"]).lower().startswith("gluteus maximus")
        and side(e["id"]) == s
    ]
    g = np.concatenate(gl)
    mk["glute" + s] = g[g[:, 2] < g[:, 2].min() + 0.004].mean(0).tolist()
    sc = B("^scapula$", s).mean(0)
    near = allsoft[(np.abs(allsoft[:, 0] - sc[0]) < 0.03) & (np.abs(allsoft[:, 1] - sc[1]) < 0.03)]
    mk["scap" + s] = [sc[0], sc[1], near[:, 2].min()]


def back_surface(y, xw=0.035):
    near = allsoft[(np.abs(allsoft[:, 0]) < xw) & (np.abs(allsoft[:, 1] - y) < 0.02)]
    return [0.0, y, float(near[:, 2].min())]


def front_surface(y, xw=0.03):
    near = everything[(np.abs(everything[:, 0]) < xw) & (np.abs(everything[:, 1] - y) < 0.02)]
    return [0.0, y, float(near[:, 2].max())]


skull = B("frontal|parietal|occipital|temporal")
mk["headTop"] = [
    0.0,
    float(skull[:, 1].max()),
    float(skull[skull[:, 1] > skull[:, 1].max() - 0.01][:, 2].mean()),
]
occ = B("occipital")
mk["occiput"] = [0.0, float(occ[:, 1].mean()), float(occ[:, 2].min())]
mand = B("mandible")
mk["chin"] = mand[mand[:, 2] > mand[:, 2].max() - 0.006].mean(0).tolist()
eyes = [verts(e) for e in idx if e["cls"] == "eye"]
mk["eyes"] = (np.concatenate(eyes).mean(0) if eyes else J["head"] + np.r_[0, 0.07, 0.07]).tolist()
st = B("body of sternum")
mk["sternum"] = st[st[:, 2] > st[:, 2].max() - 0.004].mean(0).tolist()
mk["chestMid"] = ((st.mean(0) + B(r"^vertebra t6$").mean(0)) / 2).tolist()
mk["upperBack"] = back_surface(float(B(r"^vertebra t4$").mean(0)[1]))
mk["lumbar"] = back_surface(float(J["spine"][1]))
sac = B("sacrum")
mk["sacrum"] = [0.0, float(sac[:, 1].mean()), float(sac[:, 2].min())]
mk["pelvis"] = J["root"].tolist()

MARKER_SEG = {
    "toe": "ankle",
    "heel": "ankle",
    "ball": "ankle",
    "instep": "ankle",
    "hand": "wrist",
    "palm": "wrist",
    "kneeCap": "hip",
    "glute": "root",
    "scap": "scap",
    "headTop": "head",
    "occiput": "head",
    "chin": "head",
    "eyes": "head",
    "sternum": "chest",
    "chestMid": "chest",
    "upperBack": "chest",
    "lumbar": "spine",
    "sacrum": "root",
    "pelvis": "root",
}
markers = {}
for k, p in mk.items():
    base = re.sub(r"[LR]$", "", k)
    sd = k[-1] if k[-1] in "LR" and base != k else ""
    seg = MARKER_SEG[base] + (sd if MARKER_SEG[base] in ("ankle", "wrist", "hip", "scap") else "")
    markers[k] = {"seg": seg, "p": [round(float(x), 5) for x in p]}

dump_json(
    {
        "source": {
            "title": "Z-Anatomy — The libre 3D atlas of anatomy",
            "license": "CC BY-SA 4.0",
            "via": "@authorod/svitylo-3d-anatomy-data 1.2.0 (adult-male)",
            "upstream": "BodyParts3D © The Database Center for Life Science (DBCLS), CC BY 4.0",
        },
        "segments": SEGS,
        "parent": PARENT,
        "joints": {k: [round(float(x), 5) for x in v] for k, v in J.items() if k in SEGS},
        "fingers": FINGERS,
        "markers": markers,
        "skin": SKIN_META,
        "structures": structs,
    },
    f"{OUT}/anatomy.json",
)
print(
    "structures",
    len(structs),
    "muscles",
    sum(1 for s in structs if s["type"] == "muscle"),
    "attachments atlas/partial/pca",
    [sum(1 for s in structs if s.get("attach") == k) for k in ("atlas", "partial", "pca")],
)
