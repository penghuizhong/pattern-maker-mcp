#!/usr/bin/env python3
"""MCP server for pattern-making tools (stdio transport).

Exposes the six tools as typed MCP tools; the agent calls these instead
of running scripts by path. Tool results are summaries + file paths --
the full quantified JSON stays in the file it was written to, not in
the conversation.

Tools:
  quantify_dxf      DXF -> quantified JSON (every number measured from the
                    file; unmeasurable entities listed under `unsupported`)
  plot_numbered_dxf DXF -> numbered verification PNG (layer 2 black #,
                    layer 4 red #, cm units)
  write_dxf_aama    FreeSewing JSON paths -> DXF-AAMA (R12, Teagan layout)
  check_job         validation gate on a job folder (normal + --release)
  draft_freesewing  FreeSewing design -> SVG + JSON paths (any installed
                    @freesewing/<design>; measurements + options from
                    the caller, nothing hardcoded)
  freesewing_design_info
                    what a design needs: required measurements + option
                    specs (defaults, min/max) -- from the design itself

Run: `pattern serve` or `python -m pattern_making.server`.
"""
from fastmcp import FastMCP

from . import check as check_mod
from . import freesewing as freesewing_mod
from . import plot as plot_mod
from . import quantify as quantify_mod
from . import write_dxf as write_dxf_mod

mcp = FastMCP("pattern-making")


def _quantify_summary(result, out):
    """Strip outline_points (100KB+) from the quantified dict; keep metrics."""
    pieces = {}
    for name, p in result["pieces"].items():
        layers = {}
        for layer, ms in p.get("layers", {}).items():
            layers[layer] = [{k: v for k, v in m.items() if k != "outline_points"} for m in ms]
        pieces[name] = {
            "layers": layers,
            "texts": p.get("texts", []),
            "point_count": p.get("point_count", 0),
            "notches": p.get("notches", []),
            "grainlines": p.get("grainlines", []),
        }
    return {
        "source": result["source"],
        "units": result["units"],
        "mode": result.get("mode", "by-layer"),
        "out": out,
        "pieces": pieces,
        "checks": result.get("checks", []),
        "unsupported": result["unsupported"],
    }


@mcp.tool
def quantify_dxf(dxf_path: str, out_json: str, by_block: bool = False,
                 decode_gbk: bool = False, unit_factor: float | None = None) -> dict:
    """Quantify a garment DXF into structured JSON.

    Every number is measured from entities actually present in the file;
    entities the reader cannot measure are listed under `unsupported`,
    never silently dropped. Use by_block=True for apparel-CAD (AAMA)
    files whose modelspace holds one INSERT per pattern piece; use
    decode_gbk=True for BUYI-TECH style files whose Chinese text is GBK
    bytes declared as ANSI_1252. Returns a per-piece/per-layer metric
    summary; the full JSON (with outline points) is written to out_json.
    """
    result = quantify_mod.quantify(dxf_path, out_json, by_block, decode_gbk, unit_factor)
    return _quantify_summary(result, out_json)


@mcp.tool
def plot_numbered_dxf(dxf_path: str, out_png: str, title: str | None = None) -> dict:
    """Draw a numbered verification plot (PNG) from a DXF pattern.

    All pieces at modelspace positions; layer 2 turn points get black #
    labels, layer 4 notch points red # labels. Units in the figure are cm
    (file mm / 10). Closed polylines are drawn with their closing segment.
    Returns piece names with label counts and the output path.
    """
    return plot_mod.plot(dxf_path, out_png, title)


@mcp.tool
def write_dxf_aama(paths_json: str, out_dxf: str, miter: bool = False) -> dict:
    """Write a DXF-AAMA file (R12 / AC1009) from FreeSewing JSON paths.

    Input is the dump-json-v2.mjs format: {stack: {paths: {seam, sa,
    grainline?}, notches, title}}. Output is one BLOCK per piece
    (Style.Piece.Size) + INSERT, standard layers 1/14/7/6/2/3/4, global
    # numbering per piece (seam walk then SA walk). With miter=True,
    FreeSewing SA bevel joins become sharp miter corners (garment-CAD
    convention). Current scope: Teagan fitted tee layout
    (FRONT/BACK/SLEEVE, single size M).
    """
    return write_dxf_mod.write_dxf(paths_json, out_dxf, miter=miter)


@mcp.tool
def check_job(job_dir: str, release: bool = False) -> dict:
    """Run the validation gate on a pattern job folder.

    Normal check: required files exist, JSON parses, measurements.json
    states its source (user-supplied numbers, never guessed), open_items
    agree between design.json and requirements.md, verification.json
    exists for the current version. With release=True it additionally
    requires verification status == pass, approval.md with an explicit
    user release record, and no open items (or open items recorded as
    known risk). A failed gate must be reported to the user, never
    worked around. Returns {"passed", "errors", "job", "release"}.
    """
    return check_mod.check(job_dir, release)


@mcp.tool
def draft_freesewing(design: str, measurements: dict, out_dir: str,
                     options: dict | None = None, sa_mm: float = 10.0) -> dict:
    """Draft a FreeSewing design into SVG + JSON paths.

    Generic: design is any installed @freesewing/<name> (teagan, brian,
    ... -- a design that is not installed fails with the installed
    list). Measurements are millimetres, keyed by FreeSewing name
    (e.g. chest, waist, shoulderToShoulder); options are the design's
    own options (e.g. fitWaist, waistEase, chestEase) -- use
    freesewing_design_info first to see what a design needs. Nothing
    about any design is hardcoded: required measurements and option
    specs are discovered from the design itself at draft time, unknown
    options and out-of-range values come back as warnings. Returns the
    summary (effective measurements/options, per-stack paths, warnings)
    plus the three file paths; the paths JSON feeds write_dxf_aama.
    """
    return freesewing_mod.draft(design, measurements, options or {}, sa_mm, out_dir)


@mcp.tool
def freesewing_design_info(design: str) -> dict:
    """What a FreeSewing design needs, from the design itself.

    Required + optional measurements and every available option with
    its default and min/max. Call this before draft_freesewing when the
    design's measurements or options are not already known. A design
    that is not installed fails with the installed list.
    """
    return freesewing_mod.design_info(design)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
