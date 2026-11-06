#!/usr/bin/env python3
"""Numbered verification plot for a DXF pattern: all pieces at modelspace
positions, all # labels (layer 2 turn points black, layer 4 notch points red).
Data plot from the DXF itself (ezdxf + matplotlib), not generative imagery.

Usage:
  python3 scripts/dxf_plot.py --in source.dxf --out numbered.png [--title "标题"]

Layer colours: 1 cut line black, 14 net line orange dashed,
7 grainline blue dashed, 8 internal lines grey. Units in the figure are cm
(file mm / 10). Closed polylines are drawn with their closing segment
(honour the DXF closed flag). Block names follow the AAMA convention
"Style.Piece.Size" (GBK bytes declared ANSI_1252): the middle segment is
the piece title.
"""
import argparse
import re
import sys
from pathlib import Path

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D

CJK_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def cjk_font():
    if Path(CJK_PATH).exists():
        return FontProperties(fname=CJK_PATH)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    src = Path(args.src)
    title = args.title if args.title is not None else f"{src.stem} — 编号图"
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

        data = {"name": piece_name(ins.dxf.name), "l1": [], "l14": [], "l7": [], "l8": [], "t2": [], "t4": []}
        for e in blk:
            t = e.dxftype()
            layer = str(e.dxf.layer)
            if t == "POLYLINE" and layer in ("1", "14", "8"):
                pts = [T((v.dxf.location.x, v.dxf.location.y)) for v in e.vertices]
                if e.is_closed:
                    pts.append(pts[0])  # DXF closed flag: last vertex joins first
                data["l" + layer].append(pts)
            elif t == "LINE" and layer == "7":
                pts = [T(e.dxf.start), T(e.dxf.end)]
                data["l7"].append(pts)
            elif t == "TEXT" and layer in ("2", "4"):
                m = re.search(r"#\s*(\d+)", e.dxf.text)
                if m:
                    data["t" + layer].append((T(e.dxf.insert), "#" + m.group(1)))
        pieces.append(data)

    print("pieces:", [(p["name"], len(p["t2"]), len(p["t4"])) for p in pieces])
    print("total labels:", sum(len(p["t2"]) + len(p["t4"]) for p in pieces))

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
        for (x, y), label in p["t2"]:
            ax.text(x, y, label, fontsize=7.5, color="black", ha="center", va="center")
        for (x, y), label in p["t4"]:
            ax.text(x, y, label, fontsize=7.5, color="#c00000", ha="center", va="center",
                    fontweight="bold")

    ax.set_aspect("equal")
    ax.invert_yaxis()
    ax.set_title(title, fontproperties=cjk, fontsize=20, pad=16)
    ax.set_xlabel("cm", fontsize=12)
    ax.set_ylabel("cm", fontsize=12)
    ax.grid(True, color="#eeeeee", lw=0.5)
    fig.legend(handles=[
        Line2D([0], [0], color="black", lw=1.2, label="layer 1 裁剪线"),
        Line2D([0], [0], color="#e67e00", lw=1.0, ls=(0, (4, 2)), label="layer 14 净线"),
        Line2D([0], [0], color="#1f77b4", lw=1.0, ls=(0, (4, 2)), label="layer 7 丝缕线"),
        Line2D([0], [0], color="#888888", lw=0.8, label="layer 8 工艺线"),
        Line2D([0], [0], marker="s", color="black", lw=0, markersize=8,
               markerfacecolor="black", label="# 黑字 = layer 2 拐点"),
        Line2D([0], [0], marker="s", color="#c00000", lw=0, markersize=8,
               markerfacecolor="#c00000", label="# 红字 = layer 4 刀口点"),
    ], prop=cjk, fontsize=11, loc="lower center", ncol=3)
    plt.tight_layout(rect=[0, 0.06, 1, 1])
    plt.savefig(args.out)
    print("saved", args.out)


if __name__ == "__main__":
    main()
