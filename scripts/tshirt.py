#!/usr/bin/env python3
"""Simple T-shirt net pattern. Standard library only.

The agent never draws coordinates by hand: it passes parameters, this
script computes the geometry, fits the sleeve cap to the armhole, and
writes an SVG + a verification report.

Usage:
  python3 scripts/tshirt.py --out tshirt-pattern-v1.svg --report verification.json
  python3 scripts/tshirt.py --input measurements.json --out out.svg --report out.json

Input (all cm, garment measurements for a basic straight T-shirt):
  chest_garment      garment chest circumference, e.g. 108
  length             body length, shoulder top to hem, e.g. 69
  shoulder           shoulder seam to seam, e.g. 46  (used as a sanity check)
  neck_width         neck opening width, e.g. 20
  neck_depth_front   front neck depth from the neck line, e.g. 9
  neck_depth_back    back neck depth, e.g. 3
  armhole_depth      shoulder tip to underarm, along the side, e.g. 21
  sleeve_length      underarm to sleeve hem, e.g. 20
  sleeve_hem         sleeve hem circumference, e.g. 38
  sleeve_cap_height  sleeve cap height, e.g. 13
  sleeve_ease        extra length allowed on the sleeve cap vs armhole, e.g. 1.5

Output is a NET pattern (no seam allowance drawn). Cut with 1 cm seam
allowance added around every edge, unless the user specifies otherwise.
v2 sleeve curve: the cap is a Catmull-Rom spline through drafting
points, not two quadratics meeting at a peak. That was the v1 defect:
two quadratics meet at the cap top with non-horizontal tangents, so
the cap came out pointed like a roof instead of a dome.
This is a basic T-shirt block only. It is NOT a tailored-suit block:
no lapel, no sleeve-cap tailoring, no half-canvas, no darted shaping.
"""
import argparse
import json
import math
import sys
from pathlib import Path

DEFAULTS = {
    "chest_garment": 108,
    "length": 69,
    "shoulder": 46,
    "neck_width": 20,
    "neck_depth_front": 9,
    "neck_depth_back": 3,
    "armhole_depth": 21,
    "sleeve_length": 20,
    "sleeve_hem": 38,
    "sleeve_cap_height": 13,
    "sleeve_ease": 1.5,
    "size": "M",
    "note": "Basic straight T-shirt, net pattern, seam allowance 1 cm to be added on cutting.",
}


def qbez(p0, p1, p2, n=200):
    """Sample a quadratic Bezier, return list of points and its length (mm)."""
    pts = []
    length = 0.0
    prev = None
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        pts.append((x, y))
        if prev is not None:
            length += math.hypot(x - prev[0], y - prev[1])
        prev = (x, y)
    return pts, length


def fmt(v):
    return f"{v:.1f}"


def cbez(p0, p1, p2, p3, n=100):
    """Sample a cubic Bezier, return points and length (mm)."""
    pts, length, prev = [], 0.0, None
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t**3 * p3[0]
        y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t**3 * p3[1]
        pts.append((x, y))
        if prev is not None:
            length += math.hypot(x - prev[0], y - prev[1])
        prev = (x, y)
    return pts, length


def catmull_rom_segments(points):
    """Convert drafting points into C1-continuous cubic segments.

    Each segment's control points come from its neighbours (Catmull-Rom),
    so the tangent at a shared point is the same from both sides: no
    peak, no kink. At the cap top the two neighbours are at the same
    height, so the tangent there is exactly horizontal.
    """
    segs = []
    for i in range(len(points) - 1):
        p0 = points[i - 1] if i > 0 else points[i]
        p1, p2 = points[i], points[i + 1]
        p3 = points[i + 2] if i + 2 < len(points) else points[i + 1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        segs.append((p1, c1, c2, p2))
    return segs


def spline_points_and_length(points):
    pts, length = [], 0.0
    for p0, c1, c2, p3 in catmull_rom_segments(points):
        seg_pts, seg_len = cbez(p0, c1, c2, p3)
        pts.extend(seg_pts[:-1])
        length += seg_len
    pts.append(points[-1])
    return pts, length


def spline_path(points):
    d = f"M {fmt(points[0][0])} {fmt(points[0][1])} "
    for p0, c1, c2, p3 in catmull_rom_segments(points):
        d += f"C {fmt(c1[0])} {fmt(c1[1])} {fmt(c2[0])} {fmt(c2[1])} {fmt(p3[0])} {fmt(p3[1])} "
    return d.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None, help="JSON file with cm parameters")
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    p = dict(DEFAULTS)
    if args.input:
        p.update(json.loads(Path(args.input).read_text(encoding="utf-8")))
    # cm -> mm
    cm = {k: float(v) for k, v in p.items() if isinstance(v, (int, float))}
    W = cm["chest_garment"] / 2 * 10          # body width, mm
    L = cm["length"] * 10                     # body length, mm
    neck_half = cm["neck_width"] / 2 * 10
    neck_y = 10.0
    shoulder_tip_y = 45.0
    underarm_y = shoulder_tip_y + cm["armhole_depth"] * 10
    if underarm_y >= L:
        raise SystemExit("armhole_depth too large for body length")
    cx = W / 2
    neck_l = (cx - neck_half, neck_y)
    neck_r = (cx + neck_half, neck_y)
    front_neck_c = (cx, neck_y + cm["neck_depth_front"] * 10)
    back_neck_c = (cx, neck_y + cm["neck_depth_back"] * 10)

    # Armholes: shoulder tip -> underarm, one quadratic each side.
    # Front curve is deeper (inset 55 mm), back curve is flatter (inset 40 mm).
    _, front_len_one = qbez((0, shoulder_tip_y), (55, 150), (0, underarm_y))
    _, back_len_one = qbez((0, shoulder_tip_y), (40, 150), (0, underarm_y))
    armhole_total = 2 * (front_len_one + back_len_one) / 2  # front+back, one side
    # Note: one sleeve serves one armhole = front curve + back curve.
    armhole_total = front_len_one + back_len_one
    target_cap = armhole_total + cm["sleeve_ease"] * 10

    # Sleeve cap v2: a smooth spline through drafting points, NOT two
    # quadratics meeting at the top (that is what made the v1 peak).
    # Points, left underarm -> cap top -> right underarm. The top point's
    # neighbours sit at the same height, so its tangent is horizontal:
    # a dome, not a roof. Near the underarm the curve steepens, as on a
    # real sleeve, instead of running straight into the side seam.
    # This block is symmetric (basic tee). Front/back cap asymmetry
    # and front/back notches are the next step, not faked here.
    cap_h = cm["sleeve_cap_height"] * 10

    def cap_points(width):
        # Nine drafting points, not seven: an extra point on each side
        # keeps the lower cap from collapsing into a straight diagonal.
        # The cap now bulges outwards on both sides before rounding over
        # the top, closer to a real sleeve cap than a triangle with a
        # rounded tip.
        return [
            (0, cap_h),
            (width * 0.08, cap_h * 0.82),
            (width * 0.20, cap_h * 0.48),
            (width * 0.34, cap_h * 0.20),
            (width * 0.50, 0),
            (width * 0.66, cap_h * 0.20),
            (width * 0.80, cap_h * 0.48),
            (width * 0.92, cap_h * 0.82),
            (width, cap_h),
        ]

    def cap_length(width):
        _, length = spline_points_and_length(cap_points(width))
        return length

    lo, hi = 200.0, 520.0
    if not (cap_length(lo) <= target_cap <= cap_length(hi)):
        raise SystemExit(
            f"sleeve cap target {target_cap:.1f} mm out of solvable range "
            f"({cap_length(lo):.1f}..{cap_length(hi):.1f} mm); adjust armhole/cap height"
        )
    for _ in range(50):
        mid = (lo + hi) / 2
        if cap_length(mid) < target_cap:
            lo = mid
        else:
            hi = mid
    sleeve_w = (lo + hi) / 2
    sleeve_cap = cap_length(sleeve_w)
    ease_actual = sleeve_cap - armhole_total

    hem_w = cm["sleeve_hem"] * 10
    sleeve_side = cm["sleeve_length"] * 10
    hem_lx = (sleeve_w - hem_w) / 2
    hem_rx = (sleeve_w + hem_w) / 2
    hem_y = cap_h + sleeve_side

    # ---- SVG layout ----
    gap = 80
    front_x, back_x = 0, W + gap
    sleeve_x = (W * 2 + gap) / 2 - sleeve_w / 2
    sleeve_y0 = L + gap
    total_w = W * 2 + gap
    total_h = sleeve_y0 + hem_y + 170

    def body_path(ox, neck_c, inset):
        # Full front/back body, net line. The neck curve is a quadratic whose
        # control point is doubled, so the curve itself reaches neck_c at centre:
        # mid = 0.25*neck_y + 0.5*control_y + 0.25*neck_y = neck_c.
        neck_ctrl_y = 2 * neck_c[1] - neck_y
        return (
            f"M {fmt(ox + neck_l[0])} {fmt(neck_l[1])} "
            f"L {fmt(ox + 0)} {fmt(shoulder_tip_y)} "
            f"Q {fmt(ox + inset)} 150 {fmt(ox + 0)} {fmt(underarm_y)} "
            f"L {fmt(ox + 0)} {fmt(L)} "
            f"L {fmt(ox + W)} {fmt(L)} "
            f"L {fmt(ox + W)} {fmt(underarm_y)} "
            f"Q {fmt(ox + W - inset)} 150 {fmt(ox + W)} {fmt(shoulder_tip_y)} "
            f"L {fmt(ox + neck_r[0])} {fmt(neck_r[1])} "
            f"Q {fmt(ox + neck_c[0])} {fmt(neck_ctrl_y)} "
            f"{fmt(ox + neck_l[0])} {fmt(neck_l[1])} Z"
        )

    def grain(ox, x, y0, y1):
        return (
            f'<line x1="{fmt(ox + x)}" y1="{fmt(y0)}" x2="{fmt(ox + x)}" y2="{fmt(y1)}" '
            f'class="grain"/><polygon points="{fmt(ox + x)},{fmt(y0 - 12)} '
            f'{fmt(ox + x - 6)},{fmt(y0)} {fmt(ox + x + 6)},{fmt(y0)}" class="grain"/>'
        )

    # Sleeve net path: spline cap, then side seams down to the hem.
    # Side seams run from the underarm corner (not from mid-cap), as on
    # the reference sleeve: cap ends, side seam drops, hem closes.
    cap_pts = cap_points(sleeve_w)
    cap_sampled, _ = spline_points_and_length(cap_pts)
    sleeve_cap_path = spline_path(cap_pts)
    sleeve_path = (
        f"M {fmt(sleeve_x + 0)} {fmt(sleeve_y0 + cap_h)} "
        + " ".join(
            f"C {fmt(sleeve_x + c1[0])} {fmt(sleeve_y0 + c1[1])} "
            f"{fmt(sleeve_x + c2[0])} {fmt(sleeve_y0 + c2[1])} "
            f"{fmt(sleeve_x + p3[0])} {fmt(sleeve_y0 + p3[1])}"
            for _, c1, c2, p3 in catmull_rom_segments(cap_pts)
        )
        + f" L {fmt(sleeve_x + hem_rx)} {fmt(sleeve_y0 + hem_y)} "
        f"L {fmt(sleeve_x + hem_lx)} {fmt(sleeve_y0 + hem_y)} Z"
    )
    # Sleeve seam-allowance outline (dashed, 10 mm): offset the sampled
    # cap points along their outward normal, then offset the side/hem
    # edges straight out. This is how a CAD double line is produced:
    # an offset, not a scaled copy. Straight body edges are still net
    # only in v2; the sleeve shows the offset method.
    allow_pts = []
    for i, (x, y) in enumerate(cap_sampled):
        xa, ya = cap_sampled[max(0, i - 1)]
        xb, yb = cap_sampled[min(len(cap_sampled) - 1, i + 1)]
        tx, ty = xb - xa, yb - ya
        norm = math.hypot(tx, ty) or 1.0
        # Outward for a left-to-right cap (SVG y down) is (ty, -tx)/|t|.
        allow_pts.append((x + ty / norm * 10, y - tx / norm * 10))
    allow_path = (
        f"M {fmt(sleeve_x + hem_lx - 10)} {fmt(sleeve_y0 + hem_y + 10)} "
        f"L {fmt(sleeve_x - 10)} {fmt(sleeve_y0 + cap_h)} "
        + " ".join(f"L {fmt(sleeve_x + x)} {fmt(sleeve_y0 + y)}" for x, y in allow_pts)
        + f" L {fmt(sleeve_x + sleeve_w + 10)} {fmt(sleeve_y0 + cap_h)} "
        f"L {fmt(sleeve_x + hem_rx + 10)} {fmt(sleeve_y0 + hem_y + 10)} Z"
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -50 {fmt(total_w)} {fmt(total_h + 50)}" width="1200">
<style>
.net {{ fill: #ffffff; stroke: #111111; stroke-width: 2.5; stroke-linejoin: round; }}
.grain {{ stroke: #666666; stroke-width: 1.5; stroke-dasharray: 10 6; fill: #666666; }}
.lab {{ font-family: "Noto Sans CJK SC", sans-serif; font-size: 26px; fill: #111111; font-weight: bold; }}
.sub {{ font-family: "Noto Sans CJK SC", sans-serif; font-size: 20px; fill: #444444; }}
.note {{ font-family: "Noto Sans CJK SC", sans-serif; font-size: 20px; fill: #444444; }}
.notch {{ stroke: #111111; stroke-width: 2.5; }}
.allow {{ fill: none; stroke: #d97706; stroke-width: 1.5; stroke-dasharray: 6 4; }}
</style>
<text x="{fmt(front_x + W / 2)}" y="0" class="lab" text-anchor="middle" transform="translate(0 -18)">&#21069;&#29255; FRONT</text>
<path d="{body_path(front_x, front_neck_c, 55)}" class="net"/>
{grain(front_x, cx, 320, 560)}
<text x="{fmt(back_x + W / 2)}" y="0" class="lab" text-anchor="middle" transform="translate(0 -18)">&#21518;&#29255; BACK</text>
<path d="{body_path(back_x, back_neck_c, 40)}" class="net"/>
{grain(back_x, cx, 320, 560)}
<text x="{fmt(sleeve_x + sleeve_w / 2)}" y="{fmt(sleeve_y0)}" class="lab" text-anchor="middle" transform="translate(0 -18)">&#34966;&#29255; SLEEVE</text>
<path d="{sleeve_path}" class="net"/>
<path d="{allow_path}" class="allow"/>
{grain(sleeve_x, sleeve_w / 2, sleeve_y0 + cap_h + 40, sleeve_y0 + hem_y - 40)}
<text x="{fmt(front_x + W / 2)}" y="{fmt(L + 36)}" class="sub" text-anchor="middle">&#36523;&#29255;&#22260; {cm["chest_garment"]:.0f} cm &#215; &#36523;&#38271; {cm["length"]:.0f} cm</text>
<text x="{fmt(sleeve_x + sleeve_w / 2)}" y="{fmt(sleeve_y0 + hem_y + 36)}" class="sub" text-anchor="middle">&#34966;&#38271; {cm["sleeve_length"]:.0f} cm &#215; &#34966;&#21475;&#22260; {cm["sleeve_hem"]:.0f} cm</text>
<text x="0" y="{fmt(total_h - 60)}" class="note">&#34966;&#29255;&#27225;&#32447;&#20026;&#27225;&#33394;&#34394;&#32447;&#65288;&#27861;&#21521;&#20559;&#31227; 1 cm&#65289;&#65292;&#36523;&#29255;&#20026;&#20928;&#26679;&#12290;&#31616;&#21333; T &#24676;&#29255;&#26679;&#65292;&#19981;&#26159;&#35199;&#35013;&#29255;&#26679;&#12290;</text>
<text x="0" y="{fmt(total_h - 28)}" class="note">&#34966;&#23665;&#38271; {sleeve_cap / 10:.1f} cm = &#21069;&#21518;&#34966;&#31391;&#24635;&#38271; {armhole_total / 10:.1f} cm + &#23481;&#37327; {ease_actual / 10:.1f} cm&#65292;&#35265; verification.json</text>
</svg>
'''
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")

    report = {
        "garment": "basic-tshirt",
        "size": p.get("size"),
        "inputs_cm": {k: cm[k] for k in cm},
        "body_width_mm": round(W, 1),
        "body_length_mm": round(L, 1),
        "armhole_front_one_side_mm": round(front_len_one, 1),
        "armhole_back_one_side_mm": round(back_len_one, 1),
        "armhole_total_one_sleeve_mm": round(armhole_total, 1),
        "sleeve_cap_target_mm": round(target_cap, 1),
        "sleeve_cap_mm": round(sleeve_cap, 1),
        "sleeve_ease_actual_mm": round(ease_actual, 1),
        "sleeve_width_underarm_mm": round(sleeve_w, 1),
        "sleeve_hem_mm": round(hem_w, 1),
        "checks": {
            "sleeve_cap_matches_armhole_plus_ease": abs(sleeve_cap - target_cap) <= 3.0,
            "shoulder_input_vs_body": f"input shoulder {cm['shoulder']:.1f} cm is a sanity reference; "
            "body width is driven by chest_garment/2, shoulder slope is fixed in this basic block",
        },
        "status": "pass" if abs(sleeve_cap - target_cap) <= 3.0 else "fail",
        "sleeve_cap_curve": "Catmull-Rom spline through 9 drafting points "
        "(underarm, 8%/82%, 20%/48%, 34%/20%, top, 66%/20%, 80%/48%, 92%/82%, underarm); "
        "tangent at cap top is horizontal; length still fitted to armhole + ease.",
        "note": "Body is a net pattern. Sleeve allowance is drawn as a 10 mm normal-offset "
        "dashed line. Basic T-shirt block only, not a tailored-suit block.",
    }
    if args.report:
        rp = Path(args.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(f"armhole total {armhole_total / 10:.1f} cm, sleeve cap {sleeve_cap / 10:.1f} cm, "
          f"ease {ease_actual / 10:.1f} cm, sleeve width {sleeve_w / 10:.1f} cm")
    if report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
