"""AAMA-normalized DXF writer (v3).

Reads FreeSewing native paths dumped as JSON (dump-json-v2.mjs format:
{stack: {paths: {seam, sa, grainline?}, notches: [{name, def, x, y}], title}})
and writes a standard DXF-AAMA file (R12 / AC1009):

- HEADER: $ACADVER AC1009, $INSUNITS 4 (mm), $EXTMIN/$EXTMAX, 999 DXF-AAMA
- One BLOCK per piece (name Style.Piece.Size) + INSERT in modelspace, 50 mm gaps
- Layers (AAMA/ASTM D6673 table):
    1  piece boundary (cut line = SA outline, closed; fold edge closes it)
    14 sew line (net = seam outline, closed)
    7  grainline (+ arrowhead)
    6  mirror line (fold edge, front/back only)
    8  internal lines (none in Teagan data; supported, empty here)
    11 internal cut lines (none in Teagan data; supported, empty here)
    2  turn points (POINT + "# n" TEXT, height 10)
    3  curve points (POINT, no text)
    4  notch points (POINT + "# n" TEXT, height 10) + 12 mm tick LINEs
        across the CUT line (for CADs that do not read notch POINTs;
        ETCAD behaviour observed 2026-11-05: layer-4 POINTs dropped,
        tick LINEs read back)
- # numbering: per piece, seam walk then SA walk, turn and notch points
  interleaved in outline order (mirrors ETCAD creation order); one global
  sequence per piece, pieces in FRONT, BACK, SLEEVE order.
- Piece metadata as TEXT on layer 1 (height 10), mirroring the ETCAD
  AAMA dialect: STYLE NAME / CREATION DATE / AUTHOR / SAMPLE SIZE /
  GRADE RULE TABLE / UNITS in modelspace; Piece Name / Size / Annotation /
  Quantity / Material / Category inside each block.
- Grade rules are NOT in the DXF (AAMA keeps them in a separate .rul
  file); the file only names the table ("none" here: single size).

Closed polylines carry BOTH the closed flag AND an explicit closing
vertex (first point repeated at the end), the iwase-dialect storage that
survives read-back best (2026-11-05 dialect study).

SA corners: FreeSewing's SA offset joins sharp corners with a bevel (a
short straight segment cutting across the corner). Garment-CAD convention
is a miter (sharp point). With --miter, each bevel segment is replaced by
the intersection of the two adjacent offset edges' tangent lines
(v3.1: 12 bevels, see the miter report printed on run). Without --miter
the SA path is written exactly as FreeSewing produced it (v3).

Usage:
    python3 to-dxf-v3.py [--input teagan-paths-v2.json] [--output teagan-fitted-v3.dxf] [--miter]
"""
import argparse
import json
import math

import ezdxf
from ezdxf.enums import TextEntityAlignment

# --- Teagan example defaults (override via CLI / edit for another style) ---
STYLE = "Teagan"
STYLE_NAME = "Teagan Fitted Tee"
SIZE = "M"
MATERIAL = "KNIT"
AUTHOR = "Muse"
CREATED = "2026/11/05"
GRADE_TABLE = "none"
SA_MM = 10.0
TEXT_H = 10.0
GAP = 50.0
PIECE_ORDER = ["FRONT", "BACK", "SLEEVE"]
PIECE_LABEL = {
    "FRONT": ("Front", "1"),
    "BACK": ("Back", "1"),
    "SLEEVE": ("Sleeve", "2"),
}
LAYER_COLORS = {"1": 7, "2": 7, "3": 7, "4": 1, "6": 5, "7": 4, "8": 8, "11": 3, "14": 30}


def cubic(p0, p1, p2, p3, n):
    # Subdivision points EXCLUDING t=1 (the endpoint is appended separately
    # as a turn point by flatten_flags; including it here would make dedupe
    # drop the turn flag).
    pts = []
    for i in range(1, n):
        t = i / n
        mt = 1 - t
        pts.append((
            mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
            mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1],
        ))
    return pts


def flatten_flags(ops):
    """Flatten path ops to [(x, y, is_turn)]. 'close' only marks closed."""
    pts, cur, closed = [], None, False
    for op in ops:
        t = op["type"]
        if t == "move":
            cur = (op["to"]["x"], op["to"]["y"])
            pts.append((cur[0], cur[1], True))
        elif t == "line":
            cur = (op["to"]["x"], op["to"]["y"])
            pts.append((cur[0], cur[1], True))
        elif t == "curve":
            p0 = cur
            p1 = (op["cp1"]["x"], op["cp1"]["y"])
            p2 = (op["cp2"]["x"], op["cp2"]["y"])
            p3 = (op["to"]["x"], op["to"]["y"])
            est = (sum(abs(a - b) for a, b in zip(p1, p0))
                   + sum(abs(a - b) for a, b in zip(p2, p1))
                   + sum(abs(a - b) for a, b in zip(p3, p2)))
            for x, y in cubic(p0, p1, p2, p3, max(8, min(64, int(est / 2)))):
                pts.append((x, y, False))
            pts.append((p3[0], p3[1], True))
            cur = p3
        elif t == "close":
            closed = True
    return pts, closed


def dedupe_consecutive(pts, tol=0.01):
    out = []
    for p in pts:
        if out and math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) < tol:
            continue
        out.append(p)
    return out


def nearest_on_polyline(px, py, poly):
    """Nearest point on polyline (closed or open). Returns (x, y, seg_idx, dist)."""
    best = None
    n = len(poly)
    for i in range(n - 1):
        a, b = poly[i], poly[i + 1]
        vx, vy = b[0] - a[0], b[1] - a[1]
        L2 = vx * vx + vy * vy
        t = 0 if L2 == 0 else max(0.0, min(1.0, ((px - a[0]) * vx + (py - a[1]) * vy) / L2))
        qx, qy = a[0] + t * vx, a[1] + t * vy
        d = math.hypot(px - qx, py - qy)
        if best is None or d < best[3]:
            best = (qx, qy, i, d)
    return best


def tangent_at(poly, seg_idx):
    a, b = poly[seg_idx], poly[seg_idx + 1]
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    return ((b[0] - a[0]) / L, (b[1] - a[1]) / L)


def _unit(v):
    L = math.hypot(v[0], v[1])
    return (v[0] / L, v[1] / L) if L else (0.0, 0.0)


def _end_tangent(ops, ends, i):
    """Unit tangent at the END of ops[i] (arriving at ends[i])."""
    op = ops[i]
    if op["type"] == "curve":
        return _unit((op["to"]["x"] - op["cp2"]["x"], op["to"]["y"] - op["cp2"]["y"]))
    return _unit((ends[i][0] - ends[i - 1][0], ends[i][1] - ends[i - 1][1]))


def _start_tangent(ops, ends, i):
    """Unit tangent at the START of ops[i] (leaving ends[i-1])."""
    op = ops[i]
    if op["type"] == "curve":
        return _unit((op["cp1"]["x"] - ends[i - 1][0], op["cp1"]["y"] - ends[i - 1][1]))
    return _unit((ends[i][0] - ends[i - 1][0], ends[i][1] - ends[i - 1][1]))


def _line_intersect(p1, d1, p2, d2):
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-9:
        return None
    t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
    return (p1[0] + t * d1[0], p1[1] + t * d1[1])


def miter_sa(ops):
    """Replace bevel joins in an SA path with miter (sharp) corners.

    FreeSewing's SA offset joins sharp corners with a bevel: a short straight
    segment cutting across the corner. Garment-CAD convention is a miter: the
    two offset edges extended to meet at a sharp point. A bevel is a 'line'
    op that is short (5-35 mm), not on the fold, and turns sharply (>10 deg)
    at both ends. Each bevel A->B is replaced by two line ops A->M and M->B,
    where M is the intersection of the adjacent edges' tangent lines; both
    legs are tangent-continuous with their edges, so the only corner is the
    sharp point at M. Returns (new_ops, report) with report =
    [(bevel_len_mm, stick_out_mm), ...] per replaced segment.
    """
    ends = [None] * len(ops)
    for i, op in enumerate(ops):
        if op["type"] in ("move", "line", "curve"):
            ends[i] = (op["to"]["x"], op["to"]["y"])
    new_ops, report = [], []
    for i, op in enumerate(ops):
        if op["type"] != "line" or i == 0 or ends[i] is None or ends[i - 1] is None:
            new_ops.append(op)
            continue
        a, b = ends[i - 1], ends[i]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if not (5.0 <= L <= 35.0):
            new_ops.append(op)
            continue
        if abs(a[0]) < 0.01 and abs(b[0]) < 0.01:
            new_ops.append(op)  # fold edge, not a bevel
            continue
        if ops[i - 1]["type"] not in ("line", "curve"):
            new_ops.append(op)
            continue
        din = _end_tangent(ops, ends, i - 1)
        # outgoing edge: next op; if it is 'close', the loop wraps to ops[1]
        j = i + 1
        if j >= len(ops) or ops[j]["type"] == "close":
            j = 1  # first edge after the move (closed loop wraps around)
        if ops[j]["type"] not in ("line", "curve"):
            new_ops.append(op)
            continue
        dout = _start_tangent(ops, ends, j)
        dline = _unit((b[0] - a[0], b[1] - a[1]))

        def angle(u, v):
            return math.degrees(math.acos(max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))))
        if angle(din, dline) <= 10.0 or angle(dline, dout) <= 10.0:
            new_ops.append(op)
            continue
        m = _line_intersect(a, din, b, dout)
        if m is None:
            new_ops.append(op)
            continue
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        stick = math.hypot(m[0] - mid[0], m[1] - mid[1])
        assert stick <= 25.0, (f"miter stick-out {stick:.1f}mm too large", a, b, m)
        new_ops.append({"type": "line",
                        "from": {"x": a[0], "y": a[1]},
                        "to": {"x": m[0], "y": m[1]}})
        new_ops.append({"type": "line",
                        "from": {"x": m[0], "y": m[1]},
                        "to": {"x": b[0], "y": b[1]}})
        report.append((L, stick))
    return new_ops, report


def build_piece(sname, d, miter=False):
    piece = sname.split(".")[1].upper()
    # --- flatten seam + SA in local coords, y flipped (CAD: neck up) ---
    sa_ops = d["paths"]["sa"]
    miter_report = []
    if miter:
        sa_ops, miter_report = miter_sa(sa_ops)
    seam_flat, seam_closed = flatten_flags(d["paths"]["seam"])
    sa_flat, sa_closed = flatten_flags(sa_ops)
    flip = lambda pts: [(x, -y, f) for (x, y, f) in pts]
    seam = dedupe_consecutive(flip(seam_flat))
    sa = dedupe_consecutive(flip(sa_flat))
    seam_xy = [(x, y) for x, y, _ in seam]
    sa_xy = [(x, y) for x, y, _ in sa]
    # SA closes over the fold edge for front/back (start/end both on x=0).
    # The fold edge spans the FULL cut piece: from the last SA point (neck
    # SA) to the second SA point (hem SA); the first point (hem centre) lies
    # on it in between. v3 drew only the closing segment (last -> first),
    # 30 mm short at the hem; v3.1 draws the whole fold edge.
    fold = None
    if not sa_closed:
        assert abs(sa_xy[0][0] - sa_xy[-1][0]) < 0.01, (piece, "SA ends not on fold", sa_xy[0], sa_xy[-1])
        assert abs(sa_xy[0][0]) < 0.01, (piece, "fold not at x=0", sa_xy[0])
        assert abs(sa_xy[1][0]) < 0.01, (piece, "fold 2nd point not on x=0", sa_xy[1])
        fold = (sa_xy[-1], sa_xy[1])
        sa_closed = True
    # --- turn / curve points per path ---
    def split_points(flat):
        turn = [(x, y) for x, y, f in flat if f]
        curve = [(x, y) for x, y, f in flat if not f]
        # drop closing duplicate (== first point) from turn list
        if len(turn) > 1 and math.hypot(turn[0][0] - turn[-1][0], turn[0][1] - turn[-1][1]) < 0.01:
            turn = turn[:-1]
        return turn, curve
    seam_turn, seam_curve = split_points(seam)
    sa_turn, sa_curve = split_points(sa)
    # --- notches: seam anchor (FreeSewing snippet) + cut-line projection ---
    notches = []  # (name, def, seam_pt, cut_pt, cut_dist)
    for n in d.get("notches", []):
        sp = (n["x"], -n["y"])
        # must lie on the seam
        qx, qy, _, dist = nearest_on_polyline(sp[0], sp[1], seam_xy + [seam_xy[0]])
        assert dist < 0.01, (piece, n, "notch off seam", dist)
        cx, cy, _, cdist = nearest_on_polyline(sp[0], sp[1], sa_xy + [sa_xy[0]])
        assert 5.0 <= cdist <= 15.0, (piece, n, "cut notch offset unexpected", cdist)
        notches.append({"name": n["name"], "def": n["def"], "seam": sp, "cut": (cx, cy), "cut_dist": cdist})
    # --- numbering: seam walk then SA walk, turn + notch interleaved ---
    def order_points(turn_pts, flat_xy, notch_pts):
        """Return [(x, y, kind)] in outline order. notch_pts: [(x, y)]."""
        seq = []
        # position of each turn point in flat order
        turn_idx = []
        used = set()
        for tp in turn_pts:
            for i, (x, y) in enumerate(flat_xy):
                if i in used:
                    continue
                if math.hypot(x - tp[0], y - tp[1]) < 0.01:
                    turn_idx.append(i)
                    used.add(i)
                    break
        order = sorted(zip(turn_idx, turn_pts))
        # notch insertion: after last turn point at/before its segment
        events = [(i, 0, tp, "turn") for i, tp in order]  # (flat idx, kind 0=turn, point, kind)
        for np_ in notch_pts:
            _, _, seg, _ = nearest_on_polyline(np_[0], np_[1], flat_xy + [flat_xy[0]])
            # last turn at flat idx <= seg
            before = [i for i, _ in order if i <= seg]
            pos = max(before) if before else -1
            events.append((pos, 1, np_, "notch"))
        events.sort(key=lambda e: (e[0], e[1]))
        return [(p[0], p[1], kind) for _, _, p, kind in events]
    seam_seq = order_points(seam_turn, seam_xy, [n["seam"] for n in notches])
    sa_seq = order_points(sa_turn, sa_xy, [n["cut"] for n in notches])
    # --- grainline ---
    if "grainline" in d["paths"]:
        g = flatten_flags(d["paths"]["grainline"])[0]
        (x1, y1, _), (x2, y2, _) = g[0], g[-1]
        gl = ((x1, -y1), (x2, -y2))
    else:
        xs = [p[0] for p in seam_xy]
        ys = [p[1] for p in seam_xy]
        cx = (min(xs) + max(xs)) / 2
        gl = ((cx, max(ys) - 120), (cx, min(ys) + 120))  # arrow at neck side
    # arrowhead at gl end
    (ax, ay), (bx, by) = gl
    vx, vy = bx - ax, by - ay
    L = math.hypot(vx, vy)
    ux, uy = vx / L, vy / L
    arrow = []
    for sgn in (1, -1):
        ang = math.atan2(uy, ux) + sgn * math.radians(150)
        arrow.append((bx, by, bx + 12 * math.cos(ang), by + 12 * math.sin(ang)))
    # --- title point for piece texts ---
    if piece == "SLEEVE":
        xs = [p[0] for p in seam_xy]
        ys = [p[1] for p in seam_xy]
        tx, ty = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    else:
        tx, ty = d["title"]["x"], -d["title"]["y"]
    return {
        "piece": piece, "seam": seam_xy, "sa": sa_xy,
        "seam_closed": seam_closed, "sa_closed": sa_closed,
        "seam_turn": seam_turn, "seam_curve": seam_curve,
        "sa_turn": sa_turn, "sa_curve": sa_curve,
        "seam_seq": seam_seq, "sa_seq": sa_seq,
        "notches": notches, "grainline": gl, "arrow": arrow,
        "fold": fold, "title": (tx, ty), "miter_report": miter_report,
    }


def main():
    ap = argparse.ArgumentParser(description="Write a DXF-AAMA file (R12) from FreeSewing JSON paths.")
    ap.add_argument("--input", default="teagan-paths-v2.json")
    ap.add_argument("--output", default="teagan-fitted-v3.dxf")
    ap.add_argument("--miter", action="store_true",
                    help="replace FreeSewing SA bevel joins with miter (sharp) corners")
    args = ap.parse_args()
    data = json.load(open(args.input))
    geos = {}
    for sname in data:
        piece = sname.split(".")[1].upper()
        if piece not in PIECE_ORDER:
            continue
        geos[piece] = build_piece(sname, data[sname], miter=args.miter)
    # --- global # numbering: FRONT, BACK, SLEEVE; seam walk then SA walk ---
    # Numbers live on the sequence entries themselves (same coordinates can
    # occur on both seam and SA, e.g. the shared neck point, so a coordinate
    # key would collide and duplicate a number).
    nxt = 1
    for piece in PIECE_ORDER:
        g = geos[piece]
        for seq_key in ("seam_seq", "sa_seq"):
            numbered_seq = []
            for (x, y, kind) in g[seq_key]:
                numbered_seq.append((x, y, kind, nxt))
                nxt += 1
            g[seq_key + "_num"] = numbered_seq
    total_numbers = nxt - 1
    # --- layout: FRONT left, BACK right, SLEEVE below FRONT, 50 mm gaps ---
    def bbox(pts):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), max(xs), min(ys), max(ys)
    offs = {}
    fx0, fx1, fy0, fy1 = bbox(geos["FRONT"]["sa"])
    offs["FRONT"] = (-fx0, -fy1)
    bx0, bx1, by0, by1 = bbox(geos["BACK"]["sa"])
    offs["BACK"] = (fx1 - fx0 + GAP - bx0, -by1)
    sx0, sx1, sy0, sy1 = bbox(geos["SLEEVE"]["sa"])
    offs["SLEEVE"] = (-sx0, fy0 - GAP - sy1)
    # --- build R12 doc ---
    doc = ezdxf.new("R12", setup=True)
    doc.header["$INSUNITS"] = 4
    for ln, color in LAYER_COLORS.items():
        try:
            doc.layers.add(ln, color=color)
        except Exception:
            pass
    msp = doc.modelspace()
    allx, ally = [], []
    for piece in PIECE_ORDER:
        g = geos[piece]
        label, qty = PIECE_LABEL[piece]
        bname = f"{STYLE}.{label}.{SIZE}"
        blk = doc.blocks.new(bname)
        ox, oy = offs[piece]
        # boundary (1) + sew line (14): closed flag + explicit closing vertex
        for layer, pts in (("1", g["sa"]), ("14", g["seam"])):
            closed_pts = pts + [pts[0]]
            pl = blk.add_polyline2d(closed_pts, dxfattribs={"layer": layer})
            pl.close(True)
            allx += [p[0] + ox for p in closed_pts]
            ally += [p[1] + oy for p in closed_pts]
        # mirror line (6): fold edge (block-local coords; the INSERT offset
        # applies at the blockref, never inside the block)
        if g["fold"]:
            a, b = g["fold"]
            blk.add_line(a, b, dxfattribs={"layer": "6"})
        # grainline (7) + arrowhead
        (gx1, gy1), (gx2, gy2) = g["grainline"]
        blk.add_line((gx1, gy1), (gx2, gy2), dxfattribs={"layer": "7"})
        for x1, y1, x2, y2 in g["arrow"]:
            blk.add_line((x1, y1), (x2, y2), dxfattribs={"layer": "7"})
        # curve points (3) only; turn/notch POINTs come from the numbering
        # loop below (emitting them here too would duplicate layer 2)
        for (x, y) in g["seam_curve"] + g["sa_curve"]:
            blk.add_point((x, y), dxfattribs={"layer": "3"})
        # notch points (4) + # TEXTs (2/4) + ticks across the cut line (4)
        for (x, y, kind, num) in g["seam_seq_num"] + g["sa_seq_num"]:
            layer = "4" if kind == "notch" else "2"
            blk.add_point((x, y), dxfattribs={"layer": layer})
            t = blk.add_text(f"# {num}", dxfattribs={"layer": layer, "height": TEXT_H})
            t.set_placement((x, y), align=TextEntityAlignment.LEFT)
        for n in g["notches"]:
            cx, cy = n["cut"]
            # tick across the cut line: 12 mm along the SA normal at the cut notch
            _, _, seg, _ = nearest_on_polyline(cx, cy, g["sa"] + [g["sa"][0]])
            tx, ty = tangent_at(g["sa"] + [g["sa"][0]], seg)
            nx, ny = -ty, tx
            blk.add_line((cx - 6 * nx, cy - 6 * ny), (cx + 6 * nx, cy + 6 * ny),
                         dxfattribs={"layer": "4"})
        # piece metadata TEXTs on layer 1 (height 10)
        tx, ty = g["title"]
        meta = [
            f"Piece Name: {bname}",
            f"Size: {SIZE}",
            "Annotation: ",
            f"Quantity: {qty}",
            f"Material: {MATERIAL}",
            "Category: 0",
        ]
        for i, line in enumerate(meta):
            t = blk.add_text(line, dxfattribs={"layer": "1", "height": TEXT_H})
            t.set_placement((tx, ty - i * 15), align=TextEntityAlignment.LEFT)
        msp.add_blockref(bname, (ox, oy), dxfattribs={"layer": "1"})
    # header texts in modelspace (layer 1, height 10)
    hx0, hx1 = min(allx), max(allx)
    hy0, hy1 = min(ally), max(ally)
    header_lines = [
        f"STYLE NAME: {STYLE_NAME}",
        f"CREATION DATE: {CREATED}",
        f"AUTHOR: {AUTHOR}",
        f"SAMPLE SIZE: {SIZE}",
        f"GRADE RULE TABLE: {GRADE_TABLE}",
        "UNITS: METRIC",
    ]
    for i, line in enumerate(header_lines):
        t = msp.add_text(line, dxfattribs={"layer": "1", "height": TEXT_H})
        t.set_placement((hx0, hy1 + 20 + i * 15), align=TextEntityAlignment.LEFT)
    # ezdxf writes $EXTMIN/$EXTMAX for R12 but only as 1e20 sentinels, and it
    # does not export $INSUNITS for R12 at all. Both are fixed by text
    # post-processing below, in the exact form ETCAD writes them.
    doc.saveas(args.output)
    with open(args.output, "rb") as f:
        raw = f.read()
    eol = b"\r\n" if b"\r\n" in raw[:200] else b"\n"
    nl = eol.decode()
    text = raw.decode("ascii")
    # 1) $INSUNITS (mm) right after $ACADVER -- ezdxf omits it for R12.
    marker = "$ACADVER" + nl + "  1" + nl + "AC1009" + nl
    assert marker in text, "ACADVER header entry not found for INSUNITS injection"
    text = text.replace(
        marker,
        marker + "  9" + nl + "$INSUNITS" + nl + " 70" + nl + "     4" + nl, 1)
    # 2) Replace ezdxf's 1e20 sentinel $EXTMIN/$EXTMAX with real extents.
    extmax_y = hy1 + 20 + 5 * 15 + TEXT_H  # topmost header glyph top
    for name, val in (("$EXTMIN", (hx0, hy0)), ("$EXTMAX", (hx1, extmax_y))):
        sentinel = ("  9" + nl + name + nl +
                    " 10" + nl + "1e+20" + nl + " 20" + nl + "1e+20" + nl +
                    " 30" + nl + "1e+20" + nl) if name == "$EXTMIN" else \
                   ("  9" + nl + name + nl +
                    " 10" + nl + "-1e+20" + nl + " 20" + nl + "-1e+20" + nl +
                    " 30" + nl + "-1e+20" + nl)
        real = ("  9" + nl + name + nl +
                " 10" + nl + f"{val[0]:.3f}" + nl +
                " 20" + nl + f"{val[1]:.3f}" + nl +
                " 30" + nl + "0.0" + nl)
        assert sentinel in text, f"sentinel {name} not found"
        text = text.replace(sentinel, real, 1)
    with open(args.output, "wb") as f:
        f.write(b"999" + eol + b"DXF-AAMA" + eol + text.encode("ascii"))
    print(f"wrote {args.output}: pieces={list(geos)} numbers=#1-#{total_numbers} "
          f"notches={sum(len(g['notches']) for g in geos.values())} "
          f"bbox x {hx0:.1f}..{hx1:.1f} y {hy0:.1f}..{hy1:.1f} mm")
    if args.miter:
        for piece in PIECE_ORDER:
            rep = geos[piece]["miter_report"]
            print(f"  miter {piece}: {len(rep)} bevels -> " +
                  ", ".join(f"{L:.1f}mm (+{s:.1f})" for L, s in rep))


if __name__ == "__main__":
    main()
