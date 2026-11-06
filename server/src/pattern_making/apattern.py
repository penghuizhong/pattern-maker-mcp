#!/usr/bin/env python3
"""Convert a DXF-AAMA pattern (plus its user-defined segments) to .apattern.

.apattern is the agent-era pattern file: semantic-first JSON, one style +
one size per file (see references/apattern.md and apattern-schema.json).
Named points/edges/segments replace volatile DXF # numbers; DXF-AAMA
stays the production interchange format.

Library: dxf_to_apattern(dxf_path, anchors_path, quantified_path, names,
                         meta, out_path) -> dict (the .apattern data).
  names: {"points": {piece_id: {"#num": "name", ...}},
          "segments": {"Chinese segment name": "english_key", ...},
          "pieces": {piece_id: {"label": ..., "material": ...,
                                 "quantity": ..., "symmetric": ...}}}
  meta: {"style": ..., "size": ..., "source_dxf": ..., "source_note": ...,
         "derived_from": ..., "changes": [...]}
CLI: `pattern apattern --in source.dxf --anchors segments-anchors.json
  --quantified quantified.json --names names.json --meta meta.json
  --out tshirt-165-96-M.apattern`.

Point naming is a human decision (which # is the armpit, which is the
neckline center); the names file records it. The converter does not
invent names.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

import ezdxf

from pattern_making.reanchor import _outline_index, _read_piece

FORMAT_VERSION = "0.1"


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _round2(v):
    return round(float(v), 2)


def _decode_gbk(s):
    """Re-decode a GBK Chinese string that DXF declared as ANSI_1252.

    ezdxf returns mojibake for GBK text in these BUYI-TECH files
    (e.g. 前 becomes Ç°); re-encode cp1252 -> decode gbk restores it.
    Falls back to the original string when it is not valid GBK.
    """
    try:
        return s.encode("cp1252").decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _read_dxf_pieces(dxf_path, block_map):
    """Read DXF blocks separately, block-local cm, keyed by piece id.

    block_map maps a substring of the block name to a piece id, e.g.
    {"前": "front", "后": "back", "袖": "sleeve", "领": "collar"}.
    Returns {piece_id: {"points": {#: (x, y, layer)},
                        "net": [vertex list], "cut": [vertex list],
                        "grainline": [(x, y), (x, y)] or None,
                        "internal": [[vertex list], ...],
                        "notches": [(x, y), ...]}}.
    Coordinates are block-local cm (INSERT offset removed): the piece's
    own frame, so the same geometry keeps the same coords even when
    the modelspace placement moves between versions.
    """
    doc = ezdxf.readfile(dxf_path)
    pieces = {}
    for ins in doc.modelspace():
        if ins.dxftype() != "INSERT":
            continue
        blk = doc.blocks[ins.dxf.name]
        bname = _decode_gbk(blk.name)
        piece_id = None
        for key, pid in block_map.items():
            if key in bname:
                piece_id = pid
                break
        if piece_id is None:
            continue

        def T(p):
            return (p[0] / 10.0, p[1] / 10.0)

        pts, texts = [], []
        net, cut, internal = [], [], []
        grainline = None
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
                net.append([T((v.dxf.location.x, v.dxf.location.y)) for v in e.vertices])
            elif t == "POLYLINE" and layer == "1":
                cut.append([T((v.dxf.location.x, v.dxf.location.y)) for v in e.vertices])
            elif t == "LINE" and layer == "7":
                grainline = [T(e.dxf.start), T(e.dxf.end)]
            elif t == "POLYLINE" and layer == "7":
                vs = [T((v.dxf.location.x, v.dxf.location.y)) for v in e.vertices]
                if len(vs) >= 2:
                    grainline = [vs[0], vs[-1]]
            elif t == "POLYLINE" and layer == "8":
                internal.append([T((v.dxf.location.x, v.dxf.location.y)) for v in e.vertices])
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
        pieces[piece_id] = {
            "points": points,
            "net": net[0] if net else [],
            "cut": cut[0] if cut else [],
            "grainline": grainline,
            "internal": internal,
            "notches": [p[:2] for p in points.values() if p[2] == "4"],
        }
    return pieces


def _arc_vertices(outline, a_arc, b_arc, a_pt, b_pt):
    """Polyline vertices along the shorter arc from a_pt to b_pt.

    outline is a closed vertex list; a_arc/b_arc are arclength positions
    on it. Returns [a_pt, ...intermediate vertices..., b_pt] following
    the shorter of the two arcs. Coordinates are rounded to 2 decimals.
    """
    n = len(outline)
    cum = [0.0]
    for i in range(n):
        cum.append(cum[-1] + _dist(outline[i], outline[(i + 1) % n]))
    total = cum[-1]
    fwd = (b_arc - a_arc) % total
    if fwd <= total - fwd:
        start, span, direction = a_arc % total, fwd, 1
    else:
        start, span, direction = b_arc % total, total - fwd, -1
    verts = []
    for k in range(n):
        d = (cum[k] - start) % total
        if 0 < d < span:
            verts.append((d, outline[k]))
    verts.sort(key=lambda t: t[0])
    pts = [v for _, v in verts]
    if direction == -1:
        pts = list(reversed(pts))
    return [[_round2(a_pt[0]), _round2(a_pt[1])]] + \
        [[_round2(x), _round2(y)] for x, y in pts] + \
        [[_round2(b_pt[0]), _round2(b_pt[1])]]


def dxf_to_apattern(dxf_path, anchors_path, quantified_path, names, meta,
                    out_path=None, block_map=None):
    """Convert one DXF version to a .apattern dict (and write it).

    names: {"points": {piece: {"#num": "name"}},
            "segments": {"Chinese name": "english_key"},
            "pieces": {piece: {"label", "material", "quantity", "symmetric"}}}
    meta: {"style", "size", "source_dxf", "source_note",
           "derived_from", "changes"}.
    block_map: block-name substring -> piece id; default 前/后/袖/领.
    quantified_path supplies the seam-allowance stats per piece.
    Returns the .apattern dict. Lengths are re-measured (reanchor logic)
    and checked against the recorded anchors lengths; a mismatch over
    0.05 cm raises ValueError instead of silently writing wrong data.
    """
    block_map = block_map or {"前": "front", "后": "back", "袖": "sleeve", "领": "collar"}
    anchors = json.loads(Path(anchors_path).read_text(encoding="utf-8"))
    quantified = json.loads(Path(quantified_path).read_text(encoding="utf-8"))
    pieces_dxf = _read_dxf_pieces(dxf_path, block_map)

    # Seam allowance per piece, from the quantified stats (cm).
    sa_by_piece = {}
    for blk_name, p in quantified["pieces"].items():
        if blk_name.startswith("_"):
            continue
        pid = None
        for key, cand in block_map.items():
            if key in blk_name:
                pid = cand
                break
        if pid is None:
            continue
        sa = p["seam_allowance_mm"]
        med = _round2(sa["median_mm"] / 10.0)
        p90 = _round2(sa["p90_mm"] / 10.0)
        entry = {"default": med}
        if p90 > med:
            entry["hem"] = p90
        sa_by_piece[pid] = entry

    # Named points, from the anchors (block-local cm, the # positions).
    points_by_piece = {}
    for pid, mapping in names["points"].items():
        pts = {}
        for num_s, name in mapping.items():
            num = int(num_s)
            x, y, _layer = pieces_dxf[pid]["points"][num]
            pts[name] = [_round2(x), _round2(y)]
        points_by_piece[pid] = pts

    # Outline index (arclength) per piece, for edge extraction.
    data = {"format": "apattern", "version": FORMAT_VERSION,
            "style": meta["style"], "size": meta["size"], "units": "cm"}
    if meta.get("source_dxf") or meta.get("source_note"):
        data["source"] = {}
        if meta.get("source_dxf"):
            data["source"]["dxf"] = meta["source_dxf"]
        if meta.get("source_note"):
            data["source"]["note"] = meta["source_note"]
    if meta.get("derived_from") or meta.get("changes"):
        data["lineage"] = {}
        if meta.get("derived_from"):
            data["lineage"]["derived_from"] = meta["derived_from"]
        if meta.get("changes"):
            data["lineage"]["changes"] = meta["changes"]

    pieces_out = {}
    seg_values = {}  # (piece, english_key) -> length, for the checks
    for pid, pdata in pieces_dxf.items():
        pinfo = names.get("pieces", {}).get(pid, {})
        outline = pdata["net"]
        idx = _outline_index([outline], pdata["points"]) if outline else {}
        # arclength helper: outline_index keys are global #; here the
        # outline list has one entry, so idx[n] = (0, arc, dist).
        piece = {"label": pinfo.get("label", pid),
                 "points": points_by_piece.get(pid, {}),
                 "outline": [[_round2(x), _round2(y)] for x, y in outline]}
        if pinfo.get("material"):
            piece["material"] = pinfo["material"]
        if pinfo.get("quantity"):
            piece["quantity"] = pinfo["quantity"]
        if "symmetric" in pinfo:
            piece["symmetric"] = pinfo["symmetric"]
        if pid in sa_by_piece:
            piece["sa"] = sa_by_piece[pid]
        if pdata["grainline"]:
            piece["grainline"] = [[_round2(x), _round2(y)] for x, y in pdata["grainline"]]
        if pdata["notches"]:
            piece["notches"] = [[_round2(x), _round2(y)] for x, y in sorted(pdata["notches"])]

        # Segments + edges, from the anchors file.
        segments, edges = {}, {}
        name_by_num = {}
        for num_s, name in names["points"].get(pid, {}).items():
            name_by_num[int(num_s)] = name
        for zh_name, spec in anchors["segments"].items():
            parts = spec["parts"]
            if not all(part["from"]["piece"] == pid for part in parts) or \
               not all(part["to"]["piece"] == pid for part in parts):
                continue
            eng = names["segments"].get(zh_name, zh_name)
            method = spec.get("method", "straight")
            # endpoint names, in order (multi-part segments share the
            # middle point, e.g. neckline #15-#16-#17).
            pt_names = [name_by_num[parts[0]["from"]["num"]]]
            for part in parts:
                pt_names.append(name_by_num[part["to"]["num"]])
            length = _round2(spec["length_cm"])
            segments[eng] = {"points": pt_names, "method": method, "length": length}
            seg_values[(pid, eng)] = length
            if method == "outline" and outline:
                # Edge polyline: chain the arcs of each part in order.
                # Multi-part segments (e.g. neckline #15-#16-#17, sleeve
                # cap #97-#98-#99) must go THROUGH the via point; taking
                # the shorter arc from first to last endpoint would pick
                # the wrong side when the intended arc is the longer one
                # (sleeve cap 50.80 vs the 46.55 bottom arc).
                xy = []
                for part in parts:
                    a_num = part["from"]["num"]
                    b_num = part["to"]["num"]
                    if a_num not in idx or b_num not in idx:
                        xy = []
                        break
                    a_arc, b_arc = idx[a_num][1], idx[b_num][1]
                    a_pt = pdata["points"][a_num][:2]
                    b_pt = pdata["points"][b_num][:2]
                    arc = _arc_vertices(outline, a_arc, b_arc, a_pt, b_pt)
                    if xy:
                        xy.extend(arc[1:])  # drop the shared via point
                    else:
                        xy = arc
                if xy:
                    edges[eng] = {"points": pt_names, "xy": xy}
                    # Edge arc length must equal the segment length;
                    # a mismatch means the wrong arc was extracted.
                    arc_len = sum(_dist(xy[i], xy[i + 1]) for i in range(len(xy) - 1))
                    if abs(arc_len - length) > 0.05:
                        raise ValueError(
                            f"edge {pid}.{eng}: arc length {arc_len:.2f} cm "
                            f"!= segment length {length:.2f} cm")
        if edges:
            piece["edges"] = edges
        if segments:
            piece["segments"] = segments
        pieces_out[pid] = piece
    data["pieces"] = pieces_out

    # Production pairing checks, derived from this file's own segments.
    checks = []
    def _seg(pid, key):
        return seg_values.get((pid, key))
    cap = _seg("sleeve", "cap")
    fa = _seg("front", "armhole_l") or _seg("front", "armhole")
    ba = _seg("back", "armhole_l") or _seg("back", "armhole")
    if cap is not None and fa is not None and ba is not None:
        expect = _round2(fa + ba)
        checks.append({"rule": "sleeve.cap == front.armhole + back.armhole",
                       "value": cap, "expect": expect,
                       "diff": _round2(cap - expect),
                       "pass": abs(cap - expect) <= 0.5})
    cl = _seg("collar", "length")
    fn = _seg("front", "neckline")
    bn = _seg("back", "neckline")
    if cl is not None and fn is not None and bn is not None:
        expect = _round2((fn + bn) * 0.82)
        checks.append({"rule": "collar.length == (front.neckline + back.neckline) * 0.82",
                       "value": cl, "expect": expect,
                       "diff": _round2(cl - expect),
                       "pass": abs(cl - expect) <= 1.0})
    if checks:
        data["checks"] = checks

    # Consistency: re-measure every recorded segment with reanchor and
    # compare to the anchors file. Anything off by >0.05 cm is an error,
    # not a silent drift.
    from pattern_making.reanchor import reanchor
    remeasured = reanchor(anchors_path, dxf_path)
    recorded = {n: s["length_cm"] for n, s in anchors["segments"].items()}
    for s in remeasured["segments"]:
        rec = recorded.get(s["name"])
        if rec is None or s["length_cm"] is None:
            continue
        if abs(s["length_cm"] - rec) > 0.05:
            raise ValueError(
                f"segment {s['name']}: re-measured {s['length_cm']} cm "
                f"!= recorded {rec} cm")
    if remeasured["unmatched"]:
        raise ValueError(f"unmatched anchors: {remeasured['unmatched']}")

    # Consistency: each piece's outline perimeter must match the
    # quantified net perimeter (same DXF, same outline).
    for blk_name, p in quantified["pieces"].items():
        if blk_name.startswith("_"):
            continue
        pid = None
        for key, cand in block_map.items():
            if key in blk_name:
                pid = cand
                break
        if pid is None or pid not in pieces_out:
            continue
        ol = pieces_out[pid]["outline"]
        per = sum(_dist(ol[i], ol[(i + 1) % len(ol)]) for i in range(len(ol)))
        qper = p["layers"]["14"][0]["perimeter_mm"] / 10.0
        if abs(per - qper) > 0.1:
            raise ValueError(
                f"outline {pid}: perimeter {per:.2f} cm "
                f"!= quantified net {qper:.2f} cm")

    if out_path is not None:
        Path(out_path).write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def validate_apattern(data_or_path, schema_path=None):
    """Validate .apattern data (dict or path) against the JSON Schema.

    Returns a list of error strings (empty = valid). Uses the `jsonschema`
    package when installed; otherwise checks the required fields and
    the segment/edge point references by hand.
    """
    data = data_or_path
    if isinstance(data_or_path, (str, Path)):
        data = json.loads(Path(data_or_path).read_text(encoding="utf-8"))
    errors = []
    if schema_path is None:
        schema_path = Path(__file__).resolve().parent.parent.parent.parent / \
            "references" / "apattern-schema.json"
    try:
        import jsonschema
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        for err in sorted(jsonschema.Draft7Validator(schema).iter_errors(data),
                          key=lambda e: list(e.path)):
            errors.append(".".join(str(p) for p in err.path) + ": " + err.message)
        return errors
    except ImportError:
        pass
    # Fallback: required fields + cross-references by hand.
    for field in ("format", "version", "style", "size", "units", "pieces"):
        if field not in data:
            errors.append(f"missing required field: {field}")
    if data.get("format") != "apattern":
        errors.append("format must be 'apattern'")
    if data.get("units") != "cm":
        errors.append("units must be 'cm'")
    for pid, piece in data.get("pieces", {}).items():
        pts = piece.get("points", {})
        for eng, seg in piece.get("segments", {}).items():
            for name in seg.get("points", []):
                if name not in pts:
                    errors.append(f"{pid}.segments.{eng}: unknown point '{name}'")
            if seg.get("method") not in ("outline", "straight"):
                errors.append(f"{pid}.segments.{eng}: bad method {seg.get('method')}")
        for eng, edge in piece.get("edges", {}).items():
            for name in edge.get("points", []):
                if name not in pts:
                    errors.append(f"{pid}.edges.{eng}: unknown point '{name}'")
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--anchors", required=True)
    ap.add_argument("--quantified", required=True)
    ap.add_argument("--names", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--block-map", default=None,
                    help="JSON mapping block-name substring -> piece id")
    args = ap.parse_args(argv)
    names = json.loads(Path(args.names).read_text(encoding="utf-8"))
    meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    block_map = None
    if args.block_map:
        block_map = json.loads(Path(args.block_map).read_text(encoding="utf-8"))
    data = dxf_to_apattern(args.src, args.anchors, args.quantified,
                           names, meta, args.out, block_map)
    errors = validate_apattern(data)
    if errors:
        print("SCHEMA ERRORS:")
        for e in errors:
            print("  " + e)
        return 1
    npts = sum(len(p["points"]) for p in data["pieces"].values())
    nseg = sum(len(p.get("segments", {})) for p in data["pieces"].values())
    nedge = sum(len(p.get("edges", {})) for p in data["pieces"].values())
    print(f"wrote {args.out}: {len(data['pieces'])} pieces, {npts} named points, "
          f"{nseg} segments, {nedge} edges, "
          f"{len(data.get('checks', []))} checks")
    for c in data.get("checks", []):
        print(f"  {'PASS' if c['pass'] else 'FAIL'} {c['rule']}: "
              f"value {c['value']} expect {c['expect']} diff {c['diff']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
