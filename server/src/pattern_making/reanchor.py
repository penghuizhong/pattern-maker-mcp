#!/usr/bin/env python3
"""Re-anchor user-defined segments onto a new DXF version.

# numbers are volatile across versions (adding a line or deleting a
notch renumbers them; v2->v3 of the women's block kept only 4 of 52 #
in place). Segments the user defined must therefore be anchored by
POSITION, not by # number: each segment endpoint is stored as a
block-local coordinate (cm) in an anchors JSON
(`segments-anchors.json`, produced when the user first defines the
segments). This tool matches each anchor to the nearest # point in the
new file (same block-local position, within tolerance), re-derives the
segment's # definition, and re-measures it along the net outline
(curved, polyline arc length) or as a straight line (internal lines).

Library: reanchor(anchors_path, dxf_path, out_json=None,
                   tolerance_cm=0.3, decode_gbk=True, unit_factor=1)
  -> {"segments": [...], "unmatched": [...], "out": ...}.
CLI: `pattern reanchor --anchors segments-anchors.json --in new.dxf
  [--out reanchored.json] [--tolerance 0.3]`.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

import ezdxf

DEFAULT_TOLERANCE_CM = 0.3


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _read_piece(dxf_path):
    """Read AAMA pieces: numbered points + net outlines, block-local cm.

    Returns (points, outlines) where points maps # int -> (x, y, layer)
    and outlines is a list of ordered layer-14 polyline vertex lists
    (cm) — one per piece. A file may hold several pieces in one block
    (front + back) or in several blocks (one INSERT per piece, e.g.
    tshirt-165-96 v0.2: front/back/sleeve/collar); all INSERT blocks
    are read and merged. # numbers are assumed globally unique across
    the file. Block-local coords are the anchor space: the INSERT
    offset is removed, so the same geometry keeps the same coords
    even when the modelspace placement moves between versions.
    """
    doc = ezdxf.readfile(dxf_path)
    blks = []
    for ins in doc.modelspace():
        if ins.dxftype() == "INSERT":
            blks.append(doc.blocks[ins.dxf.name])
    if not blks:
        raise ValueError("no INSERT block found in " + str(dxf_path))

    def T(p):
        # Block entities are already block-local (file units = mm);
        # anchor space is block-local cm, so just convert mm -> cm.
        # Do NOT subtract the INSERT offset: that offset places the
        # block in modelspace, and subtracting it here would shift
        # every point by the placement and break anchor matching.
        return (p[0] / 10.0, p[1] / 10.0)

    pts = []      # ((x, y), layer)
    texts = []    # ((x, y), layer, num)
    outlines = []  # one vertex list per layer-14 polyline (per piece)
    for blk in blks:
        for e in blk:
            t = e.dxftype()
            layer = str(e.dxf.layer)
            if t == "POINT" and layer in ("2", "4", "13"):
                pts.append((T(e.dxf.location), layer))
            elif t == "TEXT" and layer in ("2", "4", "13"):
                m = re.search(r"#\s*(\d+)", e.dxf.text)
                if m:
                    texts.append((T(e.dxf.insert), layer, int(m.group(1))))
            elif t == "POLYLINE" and layer == "14":
                outlines.append([T((v.dxf.location.x, v.dxf.location.y)) for v in e.vertices])
    # Resolve each # label to its POINT (same layer first, else nearest).
    points = {}
    for (tx, ty), tlayer, num in texts:
        best = None
        for (px, py), player in pts:
            d2 = (px - tx) ** 2 + (py - ty) ** 2
            key = (0 if player == tlayer else 1, d2)
            if best is None or key < best[0]:
                best = (key, (px, py), player)
        if best is None:
            anchor, player = (tx, ty), tlayer
        else:
            anchor, player = best[1], best[2]
        points[num] = (anchor[0], anchor[1], player)
    return points, outlines


def _outline_index(outlines, points):
    """Map # -> (outline_idx, arclength_cm, dist_cm) on the net outlines.

    A # is indexed on the outline it projects onto: the nearest point
    on the outline's segments (not just a vertex), recorded as the
    arclength from the outline's first vertex. A # may sit on the CUT
    outline (layer 1) rather than the NET outline (layer 14) — e.g.
    this file numbers the neckline/armhole turn points on the cut —
    so the match tolerance is 2.0 cm, covering the 1.0 cm seam
    allowance plus curve offset; the projection lands on the NET
    outline, which is what gets measured. A block may hold several
    pieces (several layer-14 outlines); a # belongs to the outline
    it projects onto most closely.
    """
    idx = {}
    for oi, outline in enumerate(outlines):
        # cumulative arclength at each vertex
        cum = [0.0]
        for i in range(len(outline)):
            a, b = outline[i], outline[(i + 1) % len(outline)]
            cum.append(cum[-1] + _dist(a, b))
        for n, (x, y, _layer) in points.items():
            if n in idx:
                continue
            best = None
            for i in range(len(outline)):
                a, b = outline[i], outline[(i + 1) % len(outline)]
                vx, vy = b[0] - a[0], b[1] - a[1]
                L2 = vx * vx + vy * vy
                t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - a[0]) * vx + (y - a[1]) * vy) / L2))
                qx, qy = a[0] + t * vx, a[1] + t * vy
                d = _dist((x, y), (qx, qy))
                if best is None or d < best[0]:
                    best = (d, cum[i] + t * math.sqrt(L2))
            if best is not None and best[0] <= 2.0:
                idx[n] = (oi, best[1], best[0])
    return idx


def _point_in_polygon(pt, poly):
    """Ray-casting point-in-polygon test."""
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _frac_inside(p0, p1, poly, n=11):
    """Fraction of the straight chord p0->p1 lying inside the polygon."""
    cnt = 0
    for k in range(n):
        t = k / (n - 1)
        x = p0[0] + t * (p1[0] - p0[0])
        y = p0[1] + t * (p1[1] - p0[1])
        if _point_in_polygon((x, y), poly):
            cnt += 1
    return cnt / n


def _outline_len(outline, a_arc, b_arc):
    """Shorter polyline arc length between two arclength positions."""
    total = 0.0
    for i in range(len(outline)):
        total += _dist(outline[i], outline[(i + 1) % len(outline)])
    d = abs(b_arc - a_arc)
    return min(d, total - d)


def _choose_method(outline, a_arc, b_arc, p0, p1):
    """Decide outline vs straight for a segment whose endpoints project
    onto the same outline (fallback when the anchors file stores no
    method). A boundary curve (neckline, armhole) has its straight
    chord mostly OUTSIDE the piece (in the neck / arm opening), so
    the chord is not the measurement — use the outline. A chord
    across the piece (chest/waist/back width) has its straight line
    mostly INSIDE, so use straight — even when the outline arc is
    only slightly longer (back width: the arc over the neckline is
    1.1x the straight). The arc/straight ratio alone cannot tell
    these apart (deep neckline 1.58x vs back width 1.10x), so the
    inside fraction decides."""
    straight = _dist(p0, p1)
    arc = _outline_len(outline, a_arc, b_arc)
    frac = _frac_inside(p0, p1, outline)
    if frac < 0.5:
        return arc, "outline"
    # Chord mostly inside the piece: straight. A shallow boundary
    # curve (e.g. sleeve cap) also has its chord inside, so this
    # fallback under-measures it — that is why segments carry a
    # stored method in the anchors file, which wins over this
    # heuristic. Preferring straight here avoids the worse error:
    # measuring a width chord along the outline goes the long way
    # round the piece (chest line 82 vs 48).
    return straight, "straight"


def reanchor(anchors_path, dxf_path, out_json=None, tolerance_cm=DEFAULT_TOLERANCE_CM,
             decode_gbk=True, unit_factor=1):
    """Match stored segment anchors to a new DXF and re-measure them.

    anchors_path: the segments-anchors.json written when the user
    defined the segments (block-local cm anchor coords per endpoint).
    Returns {"segments": [{name, parts: [{from_num, to_num, length_cm,
    method}], length_cm}], "unmatched": [{segment, endpoint, anchor_cm,
    nearest_dist_cm}], "out": out_json or None}. Unmatched anchors
    (moved or deleted geometry) are reported, never silently dropped.
    """
    anchors = json.loads(Path(anchors_path).read_text(encoding="utf-8"))
    points, outlines = _read_piece(dxf_path)
    idx = _outline_index(outlines, points)
    # Aliases: # numbers sharing a location (same geometric point).
    def aliases(n):
        x, y, _ = points[n]
        return sorted(m for m, (mx, my, _ml) in points.items()
                      if _dist((mx, my), (x, y)) < 0.05)

    def resolve(num):
        """# in the new file for an anchor given by an old # number."""
        if num in points:
            return num, points[num]
        return None, None

    def match_anchor(anchor_cm):
        best = None
        for n, (x, y, layer) in points.items():
            d = _dist((x, y), tuple(anchor_cm))
            if best is None or d < best[0]:
                best = (d, n, layer)
        if best is None or best[0] > tolerance_cm:
            return None, (best[0] if best else None)
        return best[1], best[0]

    segments = []
    unmatched = []
    for name, spec in anchors["segments"].items():
        parts = []
        total = 0.0
        ok = True
        for part in spec["parts"]:
            a_num = b_num = None
            a_dist = b_dist = None
            for end, key in (("from", "a"), ("to", "b")):
                anchor = part[end]["anchor_cm"]
                num, d = match_anchor(anchor)
                if num is None:
                    ok = False
                    unmatched.append({"segment": name, "endpoint": end,
                                      "anchor_cm": anchor,
                                      "nearest_dist_cm": (round(d, 2) if d is not None else None)})
                if key == "a":
                    a_num, a_dist = num, d
                else:
                    b_num, b_dist = num, d
            if a_num is None or b_num is None:
                continue
            # Measure: along the net outline if both endpoints project
            # onto the SAME outline (resolving aliases), else straight.
            # The projection covers # numbered on the cut outline too:
            # they land on the net outline 1.0 cm in, which is what
            # gets measured (the sew line, not the cut edge).
            # A stored method in the anchors file wins (the user defined
            # the segment, so its method is known); otherwise decide by
            # _choose_method (chord-inside test + arc/straight ratio).
            def on_outline(n):
                if n in idx:
                    return idx[n]
                for m in aliases(n):
                    if m in idx:
                        return idx[m]
                return None
            ia, ib = on_outline(a_num), on_outline(b_num)
            straight = _dist(points[a_num][:2], points[b_num][:2])
            stored = spec.get("method")
            if stored in ("outline", "straight") and ia is not None and ib is not None and ia[0] == ib[0]:
                if stored == "outline":
                    length = _outline_len(outlines[ia[0]], ia[1], ib[1])
                else:
                    length = straight
                method = stored
            elif (ia is not None and ib is not None and ia[0] == ib[0]):
                length, method = _choose_method(
                    outlines[ia[0]], ia[1], ib[1],
                    points[a_num][:2], points[b_num][:2])
            else:
                length, method = straight, "straight"
            total += length
            parts.append({"from_num": a_num, "to_num": b_num,
                          "length_cm": round(length, 2), "method": method})
        segments.append({"name": name, "parts": parts,
                         "length_cm": round(total, 2) if ok else None,
                         "complete": ok})
    result = {"anchors": str(anchors_path), "dxf": str(dxf_path),
              "tolerance_cm": tolerance_cm,
              "segments": segments, "unmatched": unmatched}
    if out_json is not None:
        Path(out_json).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        result["out"] = str(out_json)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchors", required=True)
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE_CM)
    ap.add_argument("--decode-gbk", action="store_true", default=True)
    ap.add_argument("--unit-factor", type=float, default=1)
    args = ap.parse_args(argv)
    result = reanchor(args.anchors, args.src, args.out, args.tolerance,
                      args.decode_gbk, args.unit_factor)
    for s in result["segments"]:
        status = "OK " if s["complete"] else "INCOMPLETE "
        desc = " + ".join(f"#{p['from_num']}-#{p['to_num']} {p['length_cm']}"
                          for p in s["parts"])
        print(f"{status}{s['name']}: {s['length_cm']} cm   |   {desc}")
    for u in result["unmatched"]:
        print(f"UNMATCHED {u['segment']} {u['endpoint']} anchor {u['anchor_cm']} "
              f"(nearest {u['nearest_dist_cm']} cm)")
    if result.get("out"):
        print("saved", result["out"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
