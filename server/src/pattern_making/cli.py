#!/usr/bin/env python3
"""`pattern` command line: quantify | plot | write-dxf | check | reanchor | apattern | serve."""
import argparse

from . import __version__
from . import apattern as apattern_mod
from . import check as check_mod
from . import plot as plot_mod
from . import quantify as quantify_mod
from . import reanchor as reanchor_mod
from . import write_dxf as write_dxf_mod


def build_parser():
    ap = argparse.ArgumentParser(
        prog="pattern",
        description="Pattern-making tools: DXF quantify/plot/write (AAMA) + job validation gate.")
    ap.add_argument("--version", action="version", version=f"pattern {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("quantify", help="quantify a DXF file into JSON")
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", dest="out", required=True)
    p.add_argument("--by-block", action="store_true", help="group by block (INSERT) instead of by layer")
    p.add_argument("--decode-gbk", action="store_true", help="re-decode GBK Chinese text declared as ANSI_1252")
    p.add_argument("--unit-factor", type=float, default=None,
                   help="override $INSUNITS conversion to mm")

    p = sub.add_parser("plot", help="draw a numbered verification plot (PNG) from a DXF")
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--title", default=None)

    p = sub.add_parser("write-dxf", help="write a DXF-AAMA file (R12) from JSON paths")
    p.add_argument("--input", default="tee163-paths.json")
    p.add_argument("--output", default="tee163.dxf")
    p.add_argument("--miter", action="store_true",
                   help="replace SA bevel joins with miter (sharp) corners")

    p = sub.add_parser("check", help="run the validation gate on a job folder")
    p.add_argument("--job", required=True)
    p.add_argument("--release", action="store_true")

    p = sub.add_parser("reanchor", help="re-anchor defined segments onto a new DXF version")
    p.add_argument("--anchors", required=True, help="segments-anchors.json with block-local anchor coords")
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--tolerance", type=float, default=0.3,
                   help="max anchor-to-# distance in cm (default 0.3)")

    p = sub.add_parser("apattern", help="convert a DXF version to a .apattern file (agent-era pattern format)")
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--anchors", required=True)
    p.add_argument("--quantified", required=True)
    p.add_argument("--names", required=True, help="JSON: point names + segment names + piece info")
    p.add_argument("--meta", required=True, help="JSON: style, size, source, lineage")
    p.add_argument("--out", required=True)
    p.add_argument("--block-map", default=None, help="JSON mapping block-name substring -> piece id")

    sub.add_parser("serve", help="start the MCP server (stdio)")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "quantify":
        argv2 = ["--in", args.inp, "--out", args.out]
        if args.by_block:
            argv2.append("--by-block")
        if args.decode_gbk:
            argv2.append("--decode-gbk")
        if args.unit_factor is not None:
            argv2 += ["--unit-factor", str(args.unit_factor)]
        return quantify_mod.main(argv2)
    if args.cmd == "plot":
        argv2 = ["--in", args.src, "--out", args.out]
        if args.title is not None:
            argv2 += ["--title", args.title]
        return plot_mod.main(argv2)
    if args.cmd == "write-dxf":
        argv2 = ["--input", args.input, "--output", args.output]
        if args.miter:
            argv2.append("--miter")
        return write_dxf_mod.main(argv2)
    if args.cmd == "check":
        argv2 = ["--job", args.job]
        if args.release:
            argv2.append("--release")
        return check_mod.main(argv2)
    if args.cmd == "reanchor":
        argv2 = ["--anchors", args.anchors, "--in", args.src, "--tolerance", str(args.tolerance)]
        if args.out is not None:
            argv2 += ["--out", args.out]
        return reanchor_mod.main(argv2)
    if args.cmd == "apattern":
        argv2 = ["--in", args.src, "--anchors", args.anchors,
                 "--quantified", args.quantified, "--names", args.names,
                 "--meta", args.meta, "--out", args.out]
        if args.block_map is not None:
            argv2 += ["--block-map", args.block_map]
        return apattern_mod.main(argv2)
    if args.cmd == "serve":
        from .server import main as serve_main
        return serve_main()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
