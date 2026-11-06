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
    """Read one AAMA piece: numbered points + net outline, block-local cm.

    Returns (points, outline) where points maps # int -> (x, y, layer)
    and outline is the ordered layer-14 polyline vertex list (cm).
    Block-local coords are the anchor space: the INSERT offset is
    removed, so the same geometry keeps the same coords even when the
    modelspace placement moves between versions.
    """
    doc = ezdxf.readfile(dxf_path)
    blk = None
    for ins in doc.modelspace():
        if ins.dxftype() == "INSERT":
            blk = doc.blocks[ins.dxf.name]
            break
    if blk is None:
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
    outline = []
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
            outline = [T((v.dxf.location.x, v.dxf.location.y)) for v in e.vertices]
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
    return points, outline


def _outline_index(outline, points):
    """Map # -> first vertex index on the net outline (nearest point)."""
    idx = {}
    for i, pt in enumerate(outline):
        best = None
        for n, (x, y, _layer) in points.items():
            d = _dist(pt, (x, y))
            if best is None or d < best[0]:
                best = (d, n)
        if best is not None and best[0] < 0.05 and best[1] not in idx:
            idx[best[1]] = i
    return idx


def _outline_len(outline, i, j):
    """Shorter polyline arc length between vertex indices i and j."""
    n = len(outline)
    f = 0.0
    k = i
    while k != j:
        f += _dist(outline[k], outline[(k + 1) % n])
        k = (k + 1) % n
    b = 0.0
    k = i
    while k != j:
        b += _dist(outline[k], outline[(k - 1) % n])
        k = (k - 1) % n
    return min(f, b)


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
    points, outline = _read_piece(dxf_path)
    idx = _outline_index(outline, points)
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
            # Measure: along the net outline if both endpoints sit on
            # it (resolving aliases), else straight distance.
            def on_outline(n):
                if n in idx:
                    return idx[n]
                for m in aliases(n):
                    if m in idx:
                        return idx[m]
                return None
            ia, ib = on_outline(a_num), on_outline(b_num)
            if ia is not None and ib is not None:
                length = _outline_len(outline, ia, ib)
                method = "outline"
            else:
                length = _dist(points[a_num][:2], points[b_num][:2])
                method = "straight"
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
