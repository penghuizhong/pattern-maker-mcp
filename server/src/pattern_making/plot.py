#!/usr/bin/env python3
"""Numbered verification plot for a DXF pattern: all pieces at modelspace
positions, all # labels coloured by the geometry they belong to. Data plot
from the DXF itself (ezdxf + matplotlib), not generative imagery.

Library: plot(src, out, title=None) -> {"pieces", "total_labels", "out"}.
CLI: `pattern plot --in source.dxf --out numbered.png [--title "标题"]`

Layer colours: 1 cut line black, 14 net line orange dashed,
7 grainline blue dashed, 8 internal lines grey. Units in the figure are cm
(file mm / 10). Closed polylines are drawn with their closing segment
(honour the DXF closed flag). Block names follow the AAMA convention
"Style.Piece.Size" (GBK bytes declared ANSI_1252): the middle segment is
the piece title.

# label colours are by ROLE (the geometry the point belongs to), not by the
layer of the POINT/TEXT itself (layer 2 for almost all of them):
orange = net-outline vertex (layer 14), black = cut-outline vertex
(layer 1), grey = internal/construction-line endpoint (layer 8),
red = notch (layer 4), purple = punch hole (layer 13).
One geometric point can carry several # (several line ends meet there,
each got its own ID when the CAD created it); same-spot same-role #
are drawn as one combined "#A/#B" label so the user sees it is one
point with several IDs, and different-role # at one spot keep their own
colours. Labels that would overlap are nudged apart with a thin leader
line back to the point.
"""
import argparse
import re
import sys
from pathlib import Path

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, findfont
from matplotlib.lines import Line2D

CJK_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
# macOS CJK fonts, tried when the Linux path above does not exist.
CJK_FAMILIES = ["PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "Songti SC"]


def cjk_font():
    if Path(CJK_PATH).exists():
        return FontProperties(fname=CJK_PATH)
    for family in CJK_FAMILIES:
        try:
            path = findfont(family, fallback_to_default=False)
            return FontProperties(fname=path)
        except Exception:
            continue
    return None


def ungbk(s):
    try:
        return s.encode("cp1252").decode("gbk")
    except Exception:
        return s


def piece_name(block_name):
    name = ungbk(block_name)
    parts = name.split(".")
    return parts[1] if len(parts) > 1 else name


# Role of a # point -> (label colour, bold). Coloured by the geometry the
# point belongs to, so # at one spot but on different lines stay apart.
ROLE_STYLE = {
    "notch": ("#c00000", True),      # layer 4 notch (on cut/net line)
    "hole": ("#7d3c98", True),       # layer 13 punch / drill hole
    "net": ("#e67e00", False),       # vertex of the layer 14 net outline
    "cut": ("black", False),         # vertex of the layer 1 cut outline
    "internal": ("#555555", False),  # endpoint of a layer 8 construction line
    "grain": ("#1f77b4", False),     # endpoint of the layer 7 grainline
}
ROLE_LABEL = {
    "net": "# 橙字 = 净线拐点",
    "cut": "# 黑字 = 裁剪线拐点",
    "internal": "# 灰字 = 工艺线端点",
    "notch": "# 红字 = 刀口点",
    "hole": "# 紫字 = 打孔点",
}


def classify_role(text_layer, point_layer, geom_layers):
    """Role of one # point. Notch/hole come from the POINT's own layer;
    the rest from which drawn geometry has a vertex at the point
    (net outline outranks cut, cut outranks internal)."""
    if text_layer == "4" or point_layer == "4":
        return "notch"
    if point_layer == "13":
        return "hole"
    if "14" in geom_layers:
        return "net"
    if "1" in geom_layers:
        return "cut"
    if "8" in geom_layers:
        return "internal"
    if "7" in geom_layers:
        return "grain"
    return "internal"  # standalone point, no drawn vertex here


def combine_labels(points):
    """points: list of (x, y, num:int, role). Same spot (1 mm grid) and
    same role collapse into one "#A/#B" label; different roles at one
    spot stay separate so their colours still show. Returns the list
    draw_labels wants: (x, y, text, colour, bold)."""
    groups = {}
    for x, y, num, role in points:
        key = (round(x, 2), round(y, 2), role)
        groups.setdefault(key, []).append((x, y, num))
    out = []
    for (rx, ry, role), members in groups.items():
        members.sort(key=lambda m: m[2])
        xs = sum(m[0] for m in members) / len(members)
        ys = sum(m[1] for m in members) / len(members)
        text = "/".join("#" + str(m[2]) for m in members)
        colour, bold = ROLE_STYLE[role]
        out.append((xs, ys, text, colour, bold))
    return out


def _label_box(x, y, text):
    """Estimated text bounding box in data (cm) coords, centred on (x, y).
    7.5 pt at this figure size is ~0.3 cm per character wide, ~0.6 cm tall;
    the padding keeps neighbouring labels from touching."""
    w = 0.32 * len(text) + 0.2
    h = 0.6 + 0.2
    return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)


def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def draw_labels(ax, labels):
    """Draw # labels without overlap. Several # points can share one spot
    (same location, several IDs) or sit ~1 cm apart, so plain centred text
    piles up unreadably. Place labels greedily: a label keeps its point
    unless its box would collide with one already placed, in which case it
    steps outwards (up/down/left/right, then diagonals, then further) and
    gets a thin leader line back to its point. Deterministic order."""
    placed = []
    # Offsets to try (cm), nearest first: original, then a spiral outwards.
    steps = [0.9, 1.8, 2.7, 3.6]
    offsets = [(0.0, 0.0)]
    for s in steps:
        offsets += [(0, s), (0, -s), (s, 0), (-s, 0),
                    (s, s), (-s, s), (s, -s), (-s, -s)]
    for x, y, text, color, bold in sorted(labels, key=lambda t: (t[1], t[0], t[2])):
        box = _label_box(x, y, text)
        px, py = x, y
        for dx, dy in offsets:
            cx, cy = x + dx, y + dy
            cb = _label_box(cx, cy, text)
            if not any(_overlaps(cb, pb) for pb in placed):
                px, py = cx, cy
                box = cb
                break
        placed.append(box)
        if (px, py) != (x, y):
            ax.plot([x, px], [y, py], color="#999999", lw=0.6)
            ax.plot([x], [y], marker="o", markersize=2, color=color)
        ax.text(px, py, text, fontsize=7.5, color=color, ha="center", va="center",
                fontweight="bold" if bold else "normal")


def plot(src, out, title=None):
    """Draw the numbered verification plot. Returns a summary dict."""
    src = Path(src)
    title = title if title is not None else f"{src.stem} — 编号图"
    cjk = cjk_font()

    doc = ezdxf.readfile(src)
    ms = doc.modelspace()

    pieces = []
    for ins in ms:
        if ins.dxftype() != "INSERT":
            continue
        blk = doc.blocks[ins.dxf.name]
        ox, oy, _ = ins.dxf.insert
        xs, ys = ins.dxf.xscale, ins.dxf.yscale
        rot = ins.dxf.rotation
        assert xs == 1.0 and ys == 1.0 and rot == 0.0, (ins.dxf.name, xs, ys, rot)

        def T(p):
            return ((p[0] + ox) / 10.0, (p[1] + oy) / 10.0)

        data = {"name": piece_name(ins.dxf.name), "l1": [], "l14": [], "l7": [], "l8": [],
                "pts": [], "texts": [], "vmap": {}}
        for e in blk:
            t = e.dxftype()
            layer = str(e.dxf.layer)
            if t == "POLYLINE" and layer in ("1", "14", "8"):
                pts = [T((v.dxf.location.x, v.dxf.location.y)) for v in e.vertices]
                for p in pts:
                    data["vmap"].setdefault((round(p[0], 2), round(p[1], 2)), set()).add(layer)
                if e.is_closed:
                    pts.append(pts[0])  # DXF closed flag: last vertex joins first
                data["l" + layer].append(pts)
            elif t == "LINE" and layer in ("7", "8"):
                pts = [T(e.dxf.start), T(e.dxf.end)]
                for p in pts:
                    data["vmap"].setdefault((round(p[0], 2), round(p[1], 2)), set()).add(layer)
                if layer == "7":
                    data["l7"].append(pts)
                else:
                    data["l8"].append(pts)
            elif t == "POINT" and layer in ("2", "4", "13"):
                data["pts"].append((T(e.dxf.location), layer))
            elif t == "TEXT" and layer in ("2", "4", "13"):
                m = re.search(r"#\s*(\d+)", e.dxf.text)
                if m:
                    data["texts"].append((T(e.dxf.insert), layer, int(m.group(1))))
        pieces.append(data)

    # Resolve each # label to its POINT (same layer first, else nearest),
    # then to the geometry at that point, and colour it by role.
    for p in pieces:
        labelled = []  # (x, y, num, role)
        for (tx, ty), tlayer, num in p["texts"]:
            # nearest POINT on the same layer, else nearest POINT at all
            best = None
            for (px, py), player in p["pts"]:
                d2 = (px - tx) ** 2 + (py - ty) ** 2
                same = (player == tlayer)
                key = (0 if same else 1, d2)
                if best is None or key < best[0]:
                    best = (key, (px, py), player)
            if best is None:
                anchor, player = (tx, ty), tlayer
            else:
                anchor, player = best[1], best[2]
            geom = p["vmap"].get((round(anchor[0], 2), round(anchor[1], 2)), set())
            role = classify_role(tlayer, player, geom)
            labelled.append((anchor[0], anchor[1], num, role))
        p["labels"] = combine_labels(labelled)
        p["n_labels"] = len(p["texts"])

    total_labels = sum(p["n_labels"] for p in pieces)

    fig, ax = plt.subplots(figsize=(26, 18), dpi=180)
    for p in pieces:
        for pts in p["l1"]:
            xs, ys = zip(*pts)
            ax.plot(xs, ys, color="black", lw=1.2)
        for pts in p["l14"]:
            xs, ys = zip(*pts)
            ax.plot(xs, ys, color="#e67e00", lw=1.0, ls=(0, (4, 2)))
        for pts in p["l7"]:
            xs, ys = zip(*pts)
            ax.plot(xs, ys, color="#1f77b4", lw=1.0, ls=(0, (4, 2)))
        for pts in p["l8"]:
            xs, ys = zip(*pts)
            ax.plot(xs, ys, color="#888888", lw=0.8)
        # piece title at bbox top
        allpts = [pt for k in ("l1", "l14") for pts in p[k] for pt in pts]
        if allpts:
            xs, ys = zip(*allpts)
            ax.text(sum(xs) / len(xs), max(ys) + 2.0, p["name"],
                    fontproperties=cjk, fontsize=15, fontweight="bold",
                    ha="center", color="#222222")
        draw_labels(ax, p["labels"])

    ax.set_aspect("equal")
    # No invert_yaxis: the user's CAD (ETCAD / BUYI-TECH) displays Y-up,
    # and the file's own Y is the CAD's Y. Inverting here flipped the plot
    # upside down relative to the DXF (shoulder at top in the PNG, at the
    # bottom in the CAD). Keep matplotlib's default Y-up so the plot
    # matches the CAD view exactly.
    ax.set_title(title, fontproperties=cjk, fontsize=20, pad=16)
    ax.set_xlabel("cm", fontsize=12)
    ax.set_ylabel("cm", fontsize=12)
    ax.grid(True, color="#eeeeee", lw=0.5)
    # Legend: line layers first, then # roles (only roles actually present).
    roles_present = []
    for p in pieces:
        for (_, _, text, colour, bold) in p["labels"]:
            for role, (c, b) in ROLE_STYLE.items():
                if c == colour and b == bold and role not in roles_present:
                    roles_present.append(role)
    legend_handles = [
        Line2D([0], [0], color="black", lw=1.2, label="layer 1 裁剪线"),
        Line2D([0], [0], color="#e67e00", lw=1.0, ls=(0, (4, 2)), label="layer 14 净线"),
        Line2D([0], [0], color="#1f77b4", lw=1.0, ls=(0, (4, 2)), label="layer 7 丝缕线"),
        Line2D([0], [0], color="#888888", lw=0.8, label="layer 8 工艺线"),
    ]
    for role in ("net", "cut", "internal", "notch", "hole", "grain"):
        if role in roles_present:
            colour, bold = ROLE_STYLE[role]
            legend_handles.append(Line2D([0], [0], marker="s", color=colour, lw=0,
                                         markersize=8, markerfacecolor=colour,
                                         label=ROLE_LABEL.get(role, role)))
    fig.legend(handles=legend_handles, prop=cjk, fontsize=11, loc="lower center", ncol=3)
    plt.tight_layout(rect=[0, 0.06, 1, 1])
    plt.savefig(out)
    return {
        "pieces": [{"name": p["name"], "turn_labels": p["n_labels"]}
                   for p in pieces],
        "total_labels": total_labels,
        "out": str(out),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default=None)
    args = ap.parse_args(argv)
    result = plot(args.src, args.out, args.title)
    print("pieces:", [(p["name"], p["turn_labels"]) for p in result["pieces"]])
    print("total labels:", result["total_labels"])
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
