#!/usr/bin/env python3
"""Parametric drafting: measurements + options -> new .apattern.

Takes a quantified base pattern (.apattern, one style+size) and a target
measurement set, and drafts a new size from it. This is NOT grading
(size-label deltas) and NOT scaling (uniform stretch): it re-derives the
geometry from the target measurements, point by point, then re-measures
and re-runs the pairing checks.

Method (v2, T-shirt) -- rules from the user (the pattern master),
2026-11-07. One size = 4 cm garment-chest. All rules are driven by
chest_delta = target garment chest - base garment chest:

- Shoulder: +1 cm per size (chest_delta/4). The shoulder seam
  (tip -> joint) lengthens by that amount and KEEPS ITS SLOPE: the
  joint is placed at new_tip + (base seam length + inc) along the
  base seam direction.
- Back width / front chest width: +15% of chest_delta each.
  (back_w / chest_w points move out in x by half the increment.)
- Armhole depth: +20% of chest_delta. The armpit y is set so the
  depth (shoulder_joint y - armpit y) hits the target depth.
- Back neck width / front neck width: +10% of chest_delta each.
  (shoulder_tip points move out in x by half the increment.)
- Back neck depth: FIXED (base value). The back neckline_c y is set
  so the depth (shoulder_tip y - neckline_c y) stays at the base.
- Front neck depth: +10% of chest_delta. The front neckline_c
  moves down by the increment.
- Sleeve width (sleeve fullness): +chest_delta/2. cap_l / cap_r
  move out in x by a quarter of chest_delta each.
- Sleeve cap height: re-derived to match the new armhole (cap =
  front armhole + back armhole + 0.05, knit, no ease); the user
  observes it typically rises 0.2-0.35 per size.
- Cuff: same as sleeve width (+chest_delta/2).

Widths that have no user rule yet (waist, hem) scale with the chest
ratio, as in v1. Lengths move the hem in y (see below). Armhole and
neckline are RESULTS, not inputs: they are re-measured from the
rebuilt outline after the points move. The sleeve cap and collar
are re-derived to match them. The outline is rebuilt by
interpolating every outline vertex between its two bracketing named
points (by arclength), so the curves keep their shape while their
control points move.

The rules above are the user's rules. They are explicit and
documented here so he can correct them; the tool never invents a
rule silently. If a target cannot be met (e.g. checks fail), the
tool reports it and stops, it does not fudge the numbers.
"""
import json
import math
from pathlib import Path

# Base pattern this engine drafts from (165-96 M). The ratios below are
# read from the base pattern itself at runtime, not hardcoded here --
# except the front/back chest split, which is a property of the style
# and is recorded in the base .apattern's lineage. We read it from the
# base file so a different base still works.
EASE = {"slim": 4.0, "regular": 6.0, "loose": 10.0}
COLLAR_FACTOR = 0.82   # ribbed collar negative ease
CAP_EASE = 0.05        # knit sleeve cap ease (~0)
# User's per-size rules (one size = 4 cm garment chest), as fractions
# of chest_delta. See the module docstring.
SHOULDER_PER_SIZE = 1.0      # cm per size
BACK_WIDTH_F = 0.15          # back width inc = chest_delta * 0.15
CHEST_WIDTH_F = 0.15         # front chest width inc = chest_delta * 0.15
ARMHOLE_DEPTH_F = 0.20       # armhole depth inc = chest_delta * 0.20
NECK_WIDTH_F = 0.10          # back/front neck width inc = chest_delta * 0.10
FRONT_NECK_DEPTH_F = 0.10    # front neck depth inc = chest_delta * 0.10


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _poly_len(poly):
    return sum(_dist(poly[i], poly[i + 1]) for i in range(len(poly) - 1))


def _arc_len_along_outline(outline, p_from, p_to):
    """Arc length along a closed outline from point p_from to p_to.

    outline is the closed polyline (last point == first point, or
    treated as closed). p_from / p_to are [x, y] points on it.
    Returns the shorter arc (the outline is a single closed loop, so
    the caller must ensure the two points are on the intended side --
    for armhole/neckline they are adjacent along the loop).
    """
    # find nearest vertex index for each point
    def nearest(p):
        return min(range(len(outline)),
                   key=lambda i: _dist(outline[i], p))
    i0, i1 = nearest(p_from), nearest(p_to)
    n = len(outline)
    # walk forward i0 -> i1
    fwd = 0.0
    i = i0
    while i != i1:
        j = (i + 1) % n
        fwd += _dist(outline[i], outline[j])
        i = j
    # walk backward i0 -> i1 (the other way)
    bwd = 0.0
    i = i0
    while i != i1:
        j = (i - 1) % n
        bwd += _dist(outline[i], outline[j])
        i = j
    return min(fwd, bwd)


def compute_targets(base, measurements, options):
    """Target garment segment lengths from body measurements + options.

    measurements: {chest (body), height, shoulder?, waist?}
    options: {fit, neckline, sleeve, length}
    Returns {piece: {segment: target_length}} plus the derived inputs.
    """
    fit = options.get("fit", "regular")
    ease = EASE.get(fit, 6.0)
    body_chest = float(measurements["chest"])
    height = float(measurements["height"])
    garment_chest = body_chest + ease

    bp = base["pieces"]
    base_front_chest = bp["front"]["segments"]["chest"]["length"]
    base_back_chest = bp["back"]["segments"]["chest"]["length"]
    base_garment_chest = base_front_chest + base_back_chest
    front_ratio = base_front_chest / base_garment_chest
    back_ratio = base_back_chest / base_garment_chest

    # widths scale with the chest unless the user gave an explicit value
    def scaled(base_len, explicit=None):
        if explicit is not None:
            return float(explicit)
        return base_len * garment_chest / base_garment_chest

    front_chest = garment_chest * front_ratio
    back_chest = garment_chest * back_ratio
    front_waist = scaled(bp["front"]["segments"]["waist"]["length"],
                         measurements.get("waist_front"))
    back_waist = scaled(bp["back"]["segments"]["waist"]["length"],
                        measurements.get("waist_back"))
    # waist override: a single body waist -> garment waist split by base ratio
    if measurements.get("waist") is not None and measurements.get("waist_front") is None:
        garment_waist = float(measurements["waist"]) + ease
        bw = bp["front"]["segments"]["waist"]["length"] + bp["back"]["segments"]["waist"]["length"]
        front_waist = garment_waist * bp["front"]["segments"]["waist"]["length"] / bw
        back_waist = garment_waist * bp["back"]["segments"]["waist"]["length"] / bw
    front_hem = scaled(bp["front"]["segments"]["hem"]["length"])
    back_hem = scaled(bp["back"]["segments"]["hem"]["length"])

    # lengths: centre length from height (base 165 -> base centre length)
    base_height = 165.0
    base_cl = bp["back"]["segments"]["center_length"]["length"]
    height_delta = height - base_height
    # +1 cm length per +5 cm height (rule of thumb, documented)
    center_length = base_cl + height_delta / 5.0
    if measurements.get("center_length") is not None:
        center_length = float(measurements["center_length"])
    sleeve_length = {"short": 21.0, "long": 58.0}.get(
        options.get("sleeve", "short"), 21.0)
    if measurements.get("sleeve_length") is not None:
        sleeve_length = float(measurements["sleeve_length"])

    # User's per-size rules, driven by chest_delta (garment chest
    # increase over the base). One size = 4 cm chest.
    chest_delta = garment_chest - base_garment_chest
    size_steps = chest_delta / 4.0
    rules = {
        "chest_delta": chest_delta,
        "size_steps": size_steps,
        # shoulder seam lengthens 1 cm per size, slope kept
        "shoulder_inc": size_steps * SHOULDER_PER_SIZE,
        "back_width_inc": chest_delta * BACK_WIDTH_F,
        "chest_width_inc": chest_delta * CHEST_WIDTH_F,
        "armhole_depth_inc": chest_delta * ARMHOLE_DEPTH_F,
        "neck_width_inc": chest_delta * NECK_WIDTH_F,
        "front_neck_depth_inc": chest_delta * FRONT_NECK_DEPTH_F,
        # sleeve width and cuff: chest_delta / 2
        "sleeve_width_inc": chest_delta / 2.0,
        "cuff_inc": chest_delta / 2.0,
    }

    targets = {
        "front": {"chest": front_chest, "waist": front_waist, "hem": front_hem},
        "back": {"chest": back_chest, "waist": back_waist, "hem": back_hem,
                 "center_length": center_length},
        "sleeve": {"sleeve_length": sleeve_length},
        "rules": rules,
        "meta": {"garment_chest": garment_chest, "ease": ease,
                 "body_chest": body_chest, "height": height, "fit": fit},
    }
    return targets


def _piece_centre_x(points):
    """Centre x of a symmetric piece: midpoint of the two armpits
    (front/back), of the two cuff ends (sleeve), or of the two collar
    ends (collar)."""
    if "armpit_l" in points and "armpit_r" in points:
        return (points["armpit_l"][0] + points["armpit_r"][0]) / 2.0
    if "cuff_l" in points and "cuff_r" in points:
        return (points["cuff_l"][0] + points["cuff_r"][0]) / 2.0
    if "collar_l" in points and "collar_r" in points:
        return (points["collar_l"][0] + points["collar_r"][0]) / 2.0
    xs = [p[0] for p in points.values()]
    return (min(xs) + max(xs)) / 2.0


def _set_width(points, centre_x, left_key, right_key, target):
    """Set a width segment by moving its two endpoints to
    centre +/- target/2. Keeps their y."""
    points[left_key] = [centre_x - target / 2.0, points[left_key][1]]
    points[right_key] = [centre_x + target / 2.0, points[right_key][1]]


def _move_y(points, key, dy):
    points[key] = [points[key][0], points[key][1] + dy]


def adjust_body(piece, targets, is_front, rules):
    """Move a front/back piece's named points by the user's rules.

    Order matters: neck width moves the shoulder_tip in x first,
    then the shoulder joint is placed from the new tip along the
    base seam direction (slope kept, seam lengthened by the shoulder
    rule), then the armpit y is set from the armhole-depth rule.
    Chest/waist/hem widths are set by direct targeting
    (centre +/- target/2). Length (back only) moves the hem down.
    Returns the moved points dict.
    """
    points = {k: list(v) for k, v in piece["points"].items()}
    base_points = piece["points"]
    cx = _piece_centre_x(points)

    # chest / waist / hem widths by direct targeting
    _set_width(points, cx, "armpit_l", "armpit_r", targets["chest"])
    _set_width(points, cx, "waist_l", "waist_r", targets["waist"])
    _set_width(points, cx, "hem_l", "hem_r", targets["hem"])

    # neck width: shoulder_tip moves out in x by half the increment
    neck_half = rules["neck_width_inc"] / 2.0
    for side in ("l", "r"):
        sign = -1.0 if side == "l" else 1.0
        points["shoulder_tip_" + side][0] += sign * neck_half

    # shoulder: joint placed from the NEW tip along the BASE seam
    # direction, so the slope is kept and the seam lengthens by the
    # shoulder rule.
    for side in ("l", "r"):
        tip0 = base_points["shoulder_tip_" + side]
        joint0 = base_points["shoulder_joint_" + side]
        vec = [joint0[0] - tip0[0], joint0[1] - tip0[1]]
        base_len = math.hypot(vec[0], vec[1])
        ux, uy = vec[0] / base_len, vec[1] / base_len
        new_len = base_len + rules["shoulder_inc"]
        tip = points["shoulder_tip_" + side]
        points["shoulder_joint_" + side] = [tip[0] + ux * new_len,
                                             tip[1] + uy * new_len]

    # neckline depth
    if is_front:
        # front neck depth grows by the rule: neckline_c moves down
        points["neckline_c"][1] -= rules["front_neck_depth_inc"]
    else:
        # back neck depth is FIXED (base value): neckline_c y is set
        # so the depth (shoulder_tip y - neckline_c y) stays at base.
        base_depth = (base_points["shoulder_tip_l"][1] -
                      base_points["neckline_c"][1])
        points["neckline_c"][1] = points["shoulder_tip_l"][1] - base_depth

    # armhole depth: armpit y set so the depth (shoulder_joint y -
    # armpit y) hits base depth + the rule increment.
    base_depth = (base_points["shoulder_joint_l"][1] -
                  base_points["armpit_l"][1])
    target_depth = base_depth + rules["armhole_depth_inc"]
    for side in ("l", "r"):
        points["armpit_" + side][1] = points["shoulder_joint_" + side][1] - target_depth

    # chest width (front) / back width (back): points move out in x
    # by half the increment.
    if is_front:
        half = rules["chest_width_inc"] / 2.0
        for side in ("l", "r"):
            sign = -1.0 if side == "l" else 1.0
            points["chest_w_" + side][0] += sign * half
    else:
        half = rules["back_width_inc"] / 2.0
        for side in ("l", "r"):
            sign = -1.0 if side == "l" else 1.0
            points["back_w_" + side][0] += sign * half

    if not is_front and "center_length" in targets:
        # centre length: the hem moves DOWN by the length delta
        # (y is up, so the hem y decreases); the waist moves half
        # (keeps its relative position); above the waist nothing
        # moves in y.
        base_cl = piece["segments"]["center_length"]["length"]
        dy = -(targets["center_length"] - base_cl)
        for k in ("hem_l", "hem_r", "center_hem"):
            _move_y(points, k, dy)
        for k in ("waist_l", "waist_r"):
            _move_y(points, k, dy / 2.0)
    return points


def adjust_front_length(piece, dy_y):
    """Move a front piece's hem by dy_y in y (negative = longer).
    Same length change as the back."""
    points = {k: list(v) for k, v in piece["points"].items()}
    for k in ("hem_l", "hem_r"):
        _move_y(points, k, dy_y)
    for k in ("waist_l", "waist_r"):
        _move_y(points, k, dy_y / 2.0)
    return points


def rebuild_outline(piece, new_points):
    """Rebuild a piece's closed outline after its named points moved.

    Every outline vertex is moved by interpolating the displacement of
    its two bracketing named points (by arclength along the outline),
    so the curves keep their shape while their control points move.
    Named points not on the outline (back-width points) are skipped.
    Returns the new outline (list of [x, y], closed).
    """
    outline = piece["outline"]
    old_points = piece["points"]
    # displacement per named point
    disp = {}
    for k, new in new_points.items():
        old = old_points[k]
        disp[k] = (new[0] - old[0], new[1] - old[1])
    # arclength of each outline vertex, and of each named point
    n = len(outline)
    cum = [0.0]
    for i in range(n):
        cum.append(cum[-1] + _dist(outline[i], outline[(i + 1) % n]))
    total = cum[-1]
    # named point arclength (nearest outline vertex)
    named_arc = {}
    for k, p in old_points.items():
        j = min(range(n), key=lambda i: _dist(outline[i], p))
        if _dist(outline[j], p) > 0.05:
            continue  # not on the outline (e.g. back-width points)
        named_arc[k] = cum[j]
    if not named_arc:
        return [list(p) for p in outline]
    # sort named points by arclength; duplicate the list shifted by
    # total so interpolation wraps around the closed loop
    items = sorted(named_arc.items(), key=lambda kv: kv[1])
    arcs = [a for _, a in items]
    keys = [k for k, _ in items]
    new_outline = []
    for i, p in enumerate(outline):
        a = cum[i]
        # find bracketing named points
        # (linear scan; outline is < 1000 pts, fine)
        k0, k1, a0, a1 = None, None, None, None
        for j in range(len(items)):
            if arcs[j] <= a:
                k0, a0 = keys[j], arcs[j]
            if arcs[j] >= a and k1 is None:
                k1, a1 = keys[j], arcs[j]
        if k0 is None:
            k0, a0 = keys[-1], arcs[-1] - total
        if k1 is None:
            k1, a1 = keys[0], arcs[0] + total
        if a1 == a0:
            t = 0.0
        else:
            t = (a - a0) / (a1 - a0)
        d0, d1 = disp[k0], disp[k1]
        dx = d0[0] + t * (d1[0] - d0[0])
        dy = d0[1] + t * (d1[1] - d0[1])
        new_outline.append([p[0] + dx, p[1] + dy])
    return new_outline


def _edge_arc(piece, edge):
    """Arc length of a named edge (its stored xy polyline)."""
    return _poly_len(edge["xy"])


def derive_sleeve_cap(base_sleeve, new_front_armhole, new_back_armhole,
                      sleeve_width_inc=0.0, cuff_inc=0.0):
    """Re-derive the sleeve cap to match the new armhole.

    Target cap = front armhole + back armhole + CAP_EASE. The cap
    shape is kept: cap_l / cap_r move out by the sleeve width rule
    (total +sleeve_width_inc), cap_top height is iterated until the
    cap arc hits the target. The outline is rebuilt by a direct
    transform of the base outline -- x scaled about the sleeve
    centre (sleeve width rule), cap-region y scaled about the cuff
    line (cap height) -- so the iterated cap length and the final
    measured cap are the same geometry (no interpolation drift).
    Returns (new_points, new_outline, target).
    """
    target = new_front_armhole + new_back_armhole + CAP_EASE
    pts = {k: list(v) for k, v in base_sleeve["points"].items()}
    outline = base_sleeve["outline"]
    cap_edge = base_sleeve["edges"]["cap"]
    # sleeve width + cuff rules: cap_l/cap_r and cuff_l/cuff_r move
    # out in x by half the increment each
    pts["cap_l"][0] -= sleeve_width_inc / 2.0
    pts["cap_r"][0] += sleeve_width_inc / 2.0
    pts["cuff_l"][0] -= cuff_inc / 2.0
    pts["cuff_r"][0] += cuff_inc / 2.0
    cap_top_y0 = pts["cap_top"][1]
    cuff_y = pts["cuff_c"][1]
    # x-scale: new width / base width about the sleeve centre
    base_w = (base_sleeve["points"]["cap_r"][0] -
              base_sleeve["points"]["cap_l"][0])
    new_w = pts["cap_r"][0] - pts["cap_l"][0]
    x_scale = new_w / base_w if base_w else 1.0
    centre_x = (pts["cap_l"][0] + pts["cap_r"][0]) / 2.0

    def xform_xy(xy, y_scale):
        return [[centre_x + (p[0] - centre_x) * x_scale,
                 cuff_y + (p[1] - cuff_y) * y_scale] for p in xy]

    def cap_len_at(top_y):
        y_scale = (top_y - cuff_y) / (cap_top_y0 - cuff_y) if cap_top_y0 != cuff_y else 1.0
        return _poly_len(xform_xy(cap_edge["xy"], y_scale))

    # bisect on cap_top y (cap arc grows monotonically with it)
    lo, hi = cuff_y + 1.0, cuff_y + 60.0
    for _ in range(40):
        mid = (lo + hi) / 2.0
        if cap_len_at(mid) < target:
            lo = mid
        else:
            hi = mid
    top_y = (lo + hi) / 2.0
    y_scale = (top_y - cuff_y) / (cap_top_y0 - cuff_y) if cap_top_y0 != cuff_y else 1.0
    pts["cap_top"] = [pts["cap_top"][0], top_y]
    for k in ("cap_l", "cap_r"):
        pts[k] = [pts[k][0], cuff_y + (pts[k][1] - cuff_y) * y_scale]
    new_outline = xform_xy(outline, y_scale)
    return pts, new_outline, target


def derive_collar(base_collar, new_front_neckline, new_back_neckline):
    """Re-derive the collar band to match the new neckline.

    Target collar length = (front neckline + back neckline) *
    COLLAR_FACTOR. The band is scaled in x about its centre to hit
    the target; its width (4.0) is unchanged."""
    target = (new_front_neckline + new_back_neckline) * COLLAR_FACTOR
    pts = {k: list(v) for k, v in base_collar["points"].items()}
    outline = base_collar["outline"]
    base_len = base_collar["segments"]["length"]["length"]
    cx = _piece_centre_x(pts)
    scale = target / base_len if base_len else 1.0
    new_pts = {}
    for k, p in pts.items():
        new_pts[k] = [cx + (p[0] - cx) * scale, p[1]]
    new_outline = [[cx + (p[0] - cx) * scale, p[1]] for p in outline]
    return new_pts, new_outline, target


def _measure_segment(piece_points, outline, segment):
    """Re-measure one segment from the new geometry.

    segment: {points: [names], method: outline|straight}. For
    'outline', the length is the arc along the piece outline between
    the named points (chained per part); for 'straight', the
    straight-line distance."""
    pts = segment["points"]
    if segment["method"] == "straight":
        a = piece_points[pts[0]]
        b = piece_points[pts[-1]]
        return _dist(a, b)
    # outline: chain the arc between consecutive named points
    total = 0.0
    for i in range(len(pts) - 1):
        total += _arc_len_along_outline(
            outline, piece_points[pts[i]], piece_points[pts[i + 1]])
    return total


def draft(base_path, measurements, options, out_path):
    """Draft a new size from a base .apattern.

    Returns the new .apattern dict. Raises ValueError on a failed
    check (with the numbers), never silently fudging them.
    """
    base = json.loads(Path(base_path).read_text(encoding="utf-8"))
    targets = compute_targets(base, measurements, options)

    # 1. move the body pieces (user's rules)
    new_pieces = {}
    front = base["pieces"]["front"]
    back = base["pieces"]["back"]
    rules = targets["rules"]
    # hem y-delta (negative = longer, y is up)
    back_dy_y = -(targets["back"]["center_length"] - back["segments"]["center_length"]["length"])
    front_pts = adjust_front_length(front, back_dy_y)
    # front widths + rules
    front_pts = adjust_body({**front, "points": front_pts}, targets["front"], True, rules)
    back_pts = adjust_body(back, targets["back"], False, rules)
    front_outline = rebuild_outline(front, front_pts)
    back_outline = rebuild_outline(back, back_pts)

    # 2. re-measure armhole + neckline (results, not inputs)
    def seg_len(points, outline, name, piece):
        seg = piece["segments"][name]
        return _measure_segment(points, outline, seg)
    new_front_armhole = seg_len(front_pts, front_outline, "armhole_l", front)
    new_back_armhole = seg_len(back_pts, back_outline, "armhole_l", back)
    new_front_neck = seg_len(front_pts, front_outline, "neckline", front)
    new_back_neck = seg_len(back_pts, back_outline, "neckline", back)

    # 3. re-derive sleeve cap + collar
    # (sleeve width / cuff rules are applied inside derive_sleeve_cap,
    # which needs the base width to compute the x-scale)
    sleeve = base["pieces"]["sleeve"]
    sleeve_pts, sleeve_outline, cap_target = derive_sleeve_cap(
        sleeve, new_front_armhole, new_back_armhole,
        rules["sleeve_width_inc"], rules["cuff_inc"])
    # sleeve length: re-measure after the cap move (cap_top moved),
    # then move the cuff so cap_top -> cuff_c hits the target.
    cur_sl = _dist(sleeve_pts["cap_top"], sleeve_pts["cuff_c"])
    sl_dy = targets["sleeve"]["sleeve_length"] - cur_sl
    # cuff moves DOWN by sl_dy (y is up, so cuff y decreases to lengthen);
    # the outline's cuff-edge vertices (the bottom arc from cuff_l to
    # cuff_r) move with it -- not just the vertices exactly at cuff_y,
    # the base cuff edge is not perfectly straight. Find the arc
    # BEFORE moving the points (they still match the outline).
    cuff_arc_idx = _outline_arc_indices(sleeve_outline, sleeve_pts["cuff_l"],
                                        sleeve_pts["cuff_r"])
    for k in ("cuff_l", "cuff_c", "cuff_r"):
        sleeve_pts[k] = [sleeve_pts[k][0], sleeve_pts[k][1] - sl_dy]
    sleeve_outline = [[p[0], p[1] - sl_dy if i in cuff_arc_idx else p[1]]
                      for i, p in enumerate(sleeve_outline)]
    collar = base["pieces"]["collar"]
    collar_pts, collar_outline, collar_target = derive_collar(
        collar, new_front_neck, new_back_neck)

    # 4. assemble the new .apattern (same structure as the base)
    def build_piece(base_piece, new_pts, new_outline):
        segs = {}
        for name, seg in base_piece["segments"].items():
            segs[name] = {"points": seg["points"], "method": seg["method"],
                          "length": round(_measure_segment(new_pts, new_outline, seg), 2)}
        # edges: rebuild by mapping the edge's named points to the new
        # outline (the edge xy is re-derived from the outline arc)
        edges = {}
        for ename, edge in base_piece.get("edges", {}).items():
            # find the edge's endpoints on the new outline by arclength
            # (the edge is the outline arc between its first/last point)
            p0 = new_pts[edge["points"][0]]
            p1 = new_pts[edge["points"][-1]]
            # extract the outline arc between p0 and p1
            edges[ename] = {"points": edge["points"], "xy": _outline_arc(new_outline, p0, p1)}
        return {
            "label": base_piece["label"], "material": base_piece.get("material", ""),
            "quantity": base_piece.get("quantity", 1),
            "symmetric": base_piece.get("symmetric", True),
            "sa": base_piece.get("sa", {}),
            "points": {k: [round(v[0], 2), round(v[1], 2)] for k, v in new_pts.items()},
            "outline": [[round(p[0], 2), round(p[1], 2)] for p in new_outline],
            "edges": edges,
            "segments": segs,
            "grainline": base_piece.get("grainline"),
            "notches": base_piece.get("notches", []),
        }

    new_pieces["front"] = build_piece(front, front_pts, front_outline)
    new_pieces["back"] = build_piece(back, back_pts, back_outline)
    new_pieces["sleeve"] = build_piece(sleeve, sleeve_pts, sleeve_outline)
    new_pieces["collar"] = build_piece(collar, collar_pts, collar_outline)

    # 5. checks (same rules as the base)
    checks = []
    cap = new_pieces["sleeve"]["segments"]["cap"]["length"]
    arm = (new_pieces["front"]["segments"]["armhole_l"]["length"] +
           new_pieces["back"]["segments"]["armhole_l"]["length"])
    checks.append({"rule": "sleeve.cap == front.armhole + back.armhole",
                   "value": cap, "expect": round(arm, 2),
                   "diff": round(cap - arm, 2), "pass": abs(cap - arm) <= 0.1})
    collar_len = new_pieces["collar"]["segments"]["length"]["length"]
    neck = (new_pieces["front"]["segments"]["neckline"]["length"] +
            new_pieces["back"]["segments"]["neckline"]["length"])
    checks.append({"rule": "collar.length == (front.neckline + back.neckline) * 0.82",
                   "value": collar_len, "expect": round(neck * COLLAR_FACTOR, 2),
                   "diff": round(collar_len - neck * COLLAR_FACTOR, 2),
                   "pass": abs(collar_len - neck * COLLAR_FACTOR) <= 0.2})

    failed = [c for c in checks if not c["pass"]]
    if failed:
        raise ValueError(f"draft checks failed: {failed}")

    size = measurements.get("size_label", "?")
    out = {
        "format": "apattern", "version": base.get("version", "0.1"),
        "style": base.get("style"), "size": size, "units": "cm",
        "source": {"dxf": base.get("source", {}).get("dxf", ""),
                   "note": f"drafted from {base.get('style')} {base.get('size')} "
                           f"(base .apattern {Path(base_path).name})"},
        "lineage": {"derived_from": f"{base.get('style')} {base.get('size')}",
                    "changes": [f"parametric draft (user rules v2): body chest {targets['meta']['body_chest']} "
                                f"+ ease {targets['meta']['ease']} = garment chest "
                                f"{targets['meta']['garment_chest']} (chest_delta {rules['chest_delta']:.1f}); "
                                f"height {targets['meta']['height']}; fit {targets['meta']['fit']}; "
                                f"shoulder +{rules['shoulder_inc']:.2f}, back/chest width "
                                f"+{rules['back_width_inc']:.2f}, armhole depth "
                                f"+{rules['armhole_depth_inc']:.2f}, neck width "
                                f"+{rules['neck_width_inc']:.2f}, front neck depth "
                                f"+{rules['front_neck_depth_inc']:.2f}, sleeve/cuff "
                                f"+{rules['sleeve_width_inc']:.2f}"]},
        "pieces": new_pieces,
        "checks": checks,
    }
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    return out


def _outline_arc_indices(outline, p_from, p_to):
    """Indices of the outline vertices on the shorter arc from
    p_from to p_to (inclusive of both endpoints)."""
    n = len(outline)
    def nearest(p):
        return min(range(n), key=lambda i: _dist(outline[i], p))
    i0, i1 = nearest(p_from), nearest(p_to)
    # forward arc indices
    fwd = [i0]
    i = i0
    while i != i1:
        i = (i + 1) % n
        fwd.append(i)
    # backward arc indices
    bwd = [i0]
    i = i0
    while i != i1:
        i = (i - 1) % n
        bwd.append(i)
    fwd_len = sum(_dist(outline[fwd[k]], outline[fwd[k + 1]]) for k in range(len(fwd) - 1))
    bwd_len = sum(_dist(outline[bwd[k]], outline[bwd[k + 1]]) for k in range(len(bwd) - 1))
    return set(fwd if fwd_len <= bwd_len else bwd)


def _outline_arc(outline, p_from, p_to):
    """The outline polyline between two points on it (shorter arc).

    Returns the list of [x, y] vertices along that arc, in order."""
    n = len(outline)
    def nearest(p):
        return min(range(n), key=lambda i: _dist(outline[i], p))
    i0, i1 = nearest(p_from), nearest(p_to)
    # forward arc
    fwd = [list(outline[i0])]
    i = i0
    while i != i1:
        i = (i + 1) % n
        fwd.append(list(outline[i]))
    # backward arc
    bwd = [list(outline[i0])]
    i = i0
    while i != i1:
        i = (i - 1) % n
        bwd.append(list(outline[i]))
    # pick the shorter
    fwd_len = _poly_len(fwd)
    bwd_len = _poly_len(bwd)
    return fwd if fwd_len <= bwd_len else bwd


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="base .apattern")
    ap.add_argument("--measurements", required=True, help="JSON measurements")
    ap.add_argument("--options", default="{}", help="JSON options")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    out = draft(args.base, json.loads(args.measurements),
                json.loads(args.options), args.out)
    print("drafted", out["style"], out["size"])
    for pid, p in out["pieces"].items():
        print(f"  {pid}: " + ", ".join(
            f"{k}={v['length']}" for k, v in p["segments"].items()))
    for c in out["checks"]:
        print(f"  {'PASS' if c['pass'] else 'FAIL'} {c['rule']}: "
              f"{c['value']} vs {c['expect']} (diff {c['diff']})")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
