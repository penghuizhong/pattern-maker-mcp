#!/usr/bin/env python3
"""Quantify a garment DXF: read outlines, seams, notches, grainlines, texts
and save structured data (JSON) for later drafting, grading or checking.

The agent never invents coordinates: every number in the output is measured
from entities actually present in the file. Entities the reader cannot
measure are listed under `unsupported`, never silently dropped.

Supported: LWPOLYLINE, POLYLINE, LINE, ARC, CIRCLE, SPLINE (flattened),
TEXT, MTEXT. INSERT (block references) are counted but not expanded.

Library: quantify(inp, out=None, by_block=False, decode_gbk=False,
unit_factor=None) -> the output dict (written to `out` when given).
CLI: `pattern quantify --in pattern.dxf --out quantified.json [--by-block]
[--decode-gbk] [--unit-factor N]`

Layer convention (best effort, not required):
  <PIECE>_SEAM, <PIECE>_SA, <PIECE>_NOTCH, <PIECE>_GRAINLINE, <PIECE>_TEXT
  e.g. FRONT_SEAM, SLEEVE_NOTCH. Layers without that shape are reported
  under their own name, so a CAD export with different layer names still
  quantifies -- piece assignment for such files is reported per layer and
  must be confirmed by the user before it is treated as piece data.
"""
import argparse
import json
import math
import sys

UNIT_TO_MM = {0: None, 1: 25.4, 2: 304.8, 3: 1609344.0, 4: 1.0, 5: 10.0, 6: 1000.0}


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def poly_metrics(pts, closed):
    per = sum(dist(a, b) for a, b in zip(pts, pts[1:]))
    if closed and len(pts) > 1:
        per += dist(pts[-1], pts[0])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    area = None
    if closed and len(pts) > 2:
        s = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))
        area = abs(s) / 2.0
    return {
        "points": len(pts),
        "closed": closed,
        "perimeter_mm": round(per, 1),
        "bbox_mm": {"width": round(max(xs) - min(xs), 1), "height": round(max(ys) - min(ys), 1),
                    "min": [round(min(xs), 1), round(min(ys), 1)],
                    "max": [round(max(xs), 1), round(max(ys), 1)]},
        "area_mm2": round(area, 1) if area is not None else None,
    }


def decode_gbk(s):
    """BUYI-TECH style AAMA files store Chinese text as GBK bytes but declare
    ANSI_1252, so ezdxf returns mojibake. Re-decode cp1252 -> GBK when the
    result actually contains CJK characters."""
    if not s or not isinstance(s, str):
        return s
    try:
        fixed = s.encode("cp1252").decode("gbk")
    except Exception:
        return s
    if any("\u4e00" <= ch <= "\u9fff" for ch in fixed):
        return fixed
    return s


def flatten_entity(e):
    """Return (kind, points, closed, text) for one entity, or None if unsupported."""
    t = e.dxftype()
    if t in ("LWPOLYLINE", "POLYLINE"):
        if hasattr(e, "get_points"):
            pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
            return ("polyline", pts, bool(e.closed), None)
        # Legacy R12 POLYLINE: vertices are separate VERTEX entities
        pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in e.vertices]
        return ("polyline", pts, bool(e.is_closed), None)
    if t == "LINE":
        s, en = e.dxf.start, e.dxf.end
        return ("polyline", [(float(s.x), float(s.y)), (float(en.x), float(en.y))], False, None)
    if t == "ARC":
        c, r = e.dxf.center, float(e.dxf.radius)
        a0, a1 = math.radians(float(e.dxf.start_angle)), math.radians(float(e.dxf.end_angle))
        if a1 <= a0:
            a1 += 2 * math.pi
        n = max(8, int(r * (a1 - a0) / 2))
        pts = [(float(c.x) + r * math.cos(a0 + (a1 - a0) * i / n),
                float(c.y) + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
        return ("polyline", pts, False, None)
    if t == "CIRCLE":
        c, r = e.dxf.center, float(e.dxf.radius)
        pts = [(float(c.x) + r * math.cos(2 * math.pi * i / 64),
                float(c.y) + r * math.sin(2 * math.pi * i / 64)) for i in range(65)]
        return ("polyline", pts, True, None)
    if t == "SPLINE":
        try:
            pts = [(float(p.x), float(p.y)) for p in e.flattening(distance=1.0)]
            return ("polyline", pts, bool(e.closed), None)
        except Exception:
            pts = [(float(p[0]), float(p[1])) for p in e.control_points]
            return ("polyline", pts, bool(e.closed), None)
    if t in ("TEXT", "MTEXT"):
        ins = e.dxf.insert
        txt = e.dxf.text if t == "TEXT" else e.text
        return ("text", [(float(ins.x), float(ins.y))], False, txt)
    return None


def nearest_on_polyline(pt, pts):
    best = 1e18
    for a, b in zip(pts, pts[1:]):
        vx, vy = b[0] - a[0], b[1] - a[1]
        L2 = vx * vx + vy * vy
        tt = 0 if L2 == 0 else max(0, min(1, ((pt[0] - a[0]) * vx + (pt[1] - a[1]) * vy) / L2))
        best = min(best, dist(pt, (a[0] + tt * vx, a[1] + tt * vy)))
    return best


def quantify_by_block(doc, factor, use_gbk):
    """Apparel-CAD (AAMA) mode: modelspace holds one INSERT per pattern piece,
    the geometry lives inside the block. Returns pieces keyed by block name,
    with per-layer metrics inside each piece."""
    import math as _math
    pieces, unsupported = {}, []
    for e in doc.modelspace():
        if e.dxftype() == "INSERT":
            bname = decode_gbk(e.dxf.name) if use_gbk else e.dxf.name
            try:
                block = doc.blocks[e.dxf.name]
            except Exception:
                unsupported.append({"layer": e.dxf.layer, "type": "INSERT", "detail": bname})
                continue
            ang = _math.radians(float(e.dxf.rotation or 0))
            ca, sa = _math.cos(ang), _math.sin(ang)
            sx, sy = float(e.dxf.xscale or 1), float(e.dxf.yscale or 1)
            ix, iy = float(e.dxf.insert.x), float(e.dxf.insert.y)

            def xf(px, py):
                return (ix + (px * sx * ca - py * sy * sa) * factor,
                        iy + (px * sx * sa + py * sy * ca) * factor)

            piece = pieces.setdefault(bname, {"layers": {}, "texts": [], "point_count": 0})
            for be in block:
                bt = be.dxftype()
                if bt == "POINT":
                    piece["point_count"] += 1
                    continue
                flat = flatten_entity(be)
                if flat is None:
                    unsupported.append({"layer": be.dxf.layer, "type": bt, "detail": bname})
                    continue
                kind, pts, closed, text = flat
                pts = [xf(x, y) for x, y in pts]
                if kind == "text":
                    t = decode_gbk(text) if use_gbk else text
                    if t:
                        piece["texts"].append(t)
                elif kind == "polyline":
                    m = poly_metrics(pts, closed)
                    m["outline_points"] = [[round(x, 1), round(y, 1)] for x, y in pts]
                    piece["layers"].setdefault(be.dxf.layer, []).append(m)
        elif e.dxftype() == "TEXT":
            t = decode_gbk(e.dxf.text) if use_gbk else e.dxf.text
            pieces.setdefault("_MODELSPACE_TEXT", {"layers": {}, "texts": [], "point_count": 0})["texts"].append(t)
        else:
            flat = flatten_entity(e)
            if flat is None:
                unsupported.append({"layer": e.dxf.layer, "type": e.dxftype(), "detail": ""})
    for piece, p in pieces.items():
        for layer, ms in p["layers"].items():
            for m in ms:
                m["outline_points"] = m.get("outline_points", [])
    return pieces, unsupported


def quantify(inp, out=None, by_block=False, decode_gbk_flag=False, unit_factor=None):
    """Quantify a DXF file. Returns the output dict; writes it to `out` when given."""
    import ezdxf
    doc = ezdxf.readfile(inp)
    insunits = int(doc.header.get("$INSUNITS", 0))
    factor = UNIT_TO_MM.get(insunits)
    assumed = factor is None
    factor = factor or 1.0
    if unit_factor is not None:
        factor = unit_factor
        assumed = False
    if by_block:
        pieces, unsupported = quantify_by_block(doc, factor, decode_gbk_flag)
        result = {"source": inp, "units": {"insunits": insunits, "to_mm": factor, "assumed_mm": assumed},
                  "mode": "by-block", "pieces": pieces, "unsupported": unsupported}
        if out:
            with open(out, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=1)
        return result
    layers = {}
    unsupported = []
    for e in doc.modelspace():
        layer = e.dxf.layer
        flat = flatten_entity(e)
        if flat is None:
            unsupported.append({"layer": layer, "type": e.dxftype(),
                                "detail": getattr(e.dxf, "name", "") or ""})
            continue
        kind, pts, closed, text = flat
        pts = [(x * factor, y * factor) for x, y in pts]
        layers.setdefault(layer, []).append({"kind": kind, "points": pts, "closed": closed, "text": text})
    pieces = {}
    for layer, items in layers.items():
        parts = layer.split("_", 1)
        piece = parts[0] if len(parts) == 2 and parts[1] in ("SEAM", "SA", "NOTCH", "GRAINLINE", "TEXT") else layer
        role = parts[1] if len(parts) == 2 and parts[1] in ("SEAM", "SA", "NOTCH", "GRAINLINE", "TEXT") else "OTHER"
        p = pieces.setdefault(piece, {"layers": {}, "notches": [], "texts": [], "grainlines": []})
        if role in ("SEAM", "SA"):
            for it in items:
                if it["kind"] == "polyline":
                    m = poly_metrics(it["points"], it["closed"])
                    m["outline_points"] = [[round(x, 1), round(y, 1)] for x, y in it["points"]]
                    p["layers"].setdefault(role, []).append(m)
        elif role == "NOTCH":
            for it in items:
                if it["kind"] == "polyline" and len(it["points"]) >= 2:
                    mid = ((it["points"][0][0] + it["points"][-1][0]) / 2,
                           (it["points"][0][1] + it["points"][-1][1]) / 2)
                    p["notches"].append({"midpoint_mm": [round(mid[0], 1), round(mid[1], 1)],
                                        "length_mm": round(dist(it["points"][0], it["points"][-1]), 1)})
        elif role == "GRAINLINE":
            for it in items:
                if it["kind"] == "polyline" and len(it["points"]) >= 2:
                    a, b = it["points"][0], it["points"][-1]
                    ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180
                    if dist(a, b) > 20:  # main line, not arrowhead barbs
                        p["grainlines"].append({"from_mm": [round(a[0], 1), round(a[1], 1)],
                                               "to_mm": [round(b[0], 1), round(b[1], 1)],
                                               "angle_deg": round(ang, 1)})
        elif role == "TEXT":
            for it in items:
                if it["text"]:
                    p["texts"].append(it["text"])
        else:
            for it in items:
                if it["kind"] == "polyline":
                    p["layers"].setdefault("OTHER", []).append(poly_metrics(it["points"], it["closed"]))
                elif it["text"]:
                    p["texts"].append(it["text"])
    # Checks: every notch should sit on its piece's seam outline
    checks = []
    for piece, p in pieces.items():
        seams = [m for m in p["layers"].get("SEAM", [])]
        if seams and p["notches"]:
            outline = seams[0]["outline_points"]
            for n in p["notches"]:
                d = nearest_on_polyline(tuple(n["midpoint_mm"]), [tuple(q) for q in outline])
                checks.append({"piece": piece, "check": "notch_on_seam",
                               "notch_mm": n["midpoint_mm"], "distance_to_seam_mm": round(d, 2),
                               "pass": d <= 1.0})
    result = {"source": inp, "units": {"insunits": insunits, "to_mm": factor, "assumed_mm": assumed},
              "layers": sorted(layers), "pieces": pieces, "checks": checks, "unsupported": unsupported}
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
    return result


def _print_summary(result, out):
    if result.get("mode") == "by-block":
        for piece, p in result["pieces"].items():
            print(f"== {piece}")
            for layer, ms in sorted(p["layers"].items()):
                for m in ms:
                    print(f"   layer {layer}: perimeter {m['perimeter_mm']} mm, bbox {m['bbox_mm']['width']} x {m['bbox_mm']['height']} mm"
                          + (f", area {m['area_mm2']} mm2" if m["area_mm2"] else "") + f", closed={m['closed']}")
            print(f"   texts: {p['texts'][:8]}  point_count: {p['point_count']}")
    else:
        pieces = result["pieces"]
        print(f"pieces: {sorted(pieces)}")
        for piece, p in pieces.items():
            for role, ms in p["layers"].items():
                for m in ms:
                    print(f"{piece} {role}: perimeter {m['perimeter_mm']} mm, bbox {m['bbox_mm']['width']} x {m['bbox_mm']['height']} mm"
                          + (f", area {m['area_mm2']} mm2" if m["area_mm2"] else ""))
            print(f"{piece} notches: {len(p['notches'])}, grainlines: {len(p['grainlines'])}, texts: {p['texts']}")
        for c in result["checks"]:
            print(f"check {c['piece']} notch_on_seam: {c['distance_to_seam_mm']} mm -> {'pass' if c['pass'] else 'FAIL'}")
    if result["unsupported"]:
        print(f"unsupported (counted, not measured): {result['unsupported']}")
    if out:
        print(f"saved {out}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--by-block", action="store_true", help="group by block (INSERT) instead of by layer")
    ap.add_argument("--decode-gbk", action="store_true", help="re-decode GBK Chinese text declared as ANSI_1252")
    ap.add_argument("--unit-factor", type=float, default=None, help="override $INSUNITS conversion to mm (e.g. 1 when the file's units are mm despite the header)")
    args = ap.parse_args(argv)
    result = quantify(args.inp, args.out, args.by_block, args.decode_gbk, args.unit_factor)
    _print_summary(result, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
