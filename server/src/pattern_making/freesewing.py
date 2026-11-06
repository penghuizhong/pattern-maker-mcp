"""FreeSewing draft runner (Node): draft any installed @freesewing/<design>.

Nothing about any design is hardcoded: the design name, the measurements
and the options all come from the caller. The Node runner
(server/engine/runner/draft.mjs) discovers what a design needs from the
design itself (pattern.getConfig()) and which designs are available by
scanning the project's pattern library (server/library/) first, then
installed npm designs. Measurements are millimetres
(FreeSewing convention); sa is millimetres too.

CLI: `pattern draft --design <name> --measurements <file.json>
[--options <file.json>] [--sa <mm>] --out <dir>`
     `pattern draft --design <name> --info`
     `pattern draft --list-designs`
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[2] / "engine" / "runner" / "draft.mjs"


def _run_node(args):
    """Run the Node runner; returns the JSON it prints on stdout.

    Runner errors are a JSON object on stderr; surface the message plus
    its detail (required/missing measurements, installed designs, ...).
    """
    if not RUNNER.exists():
        raise RuntimeError(f"FreeSewing runner not found: {RUNNER}")
    proc = subprocess.run(["node", str(RUNNER), *args],
                          capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        err = None
        for line in proc.stderr.strip().splitlines():
            try:
                err = json.loads(line)
            except json.JSONDecodeError:
                continue
        if err and "error" in err:
            detail = {k: v for k, v in err.items() if k != "error"}
            if detail:
                raise RuntimeError(f"{err['error']}: {json.dumps(detail, ensure_ascii=False)}")
            raise RuntimeError(err["error"])
        raise RuntimeError(proc.stderr.strip() or f"node draft.mjs failed (exit {proc.returncode})")
    return json.loads(proc.stdout)


def draft(design, measurements, options=None, sa_mm=10.0, out_dir="."):
    """Draft a FreeSewing design into out_dir.

    Returns the runner's summary: design, version, sa_mm, the effective
    (default-merged) measurements and options, required/optional/unused
    measurements, warnings, per-stack path/notch counts, and the three
    file paths (svg, paths JSON, summary JSON). The paths JSON feeds
    write_dxf_aama.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        m_path = Path(tmp) / "measurements.json"
        m_path.write_text(json.dumps(measurements), encoding="utf-8")
        args = ["--design", design, "--measurements", str(m_path),
                "--sa", str(sa_mm), "--out", str(out)]
        if options:
            o_path = Path(tmp) / "options.json"
            o_path.write_text(json.dumps(options), encoding="utf-8")
            args += ["--options", str(o_path)]
        return _run_node(args)


def design_info(design):
    """What a design needs: required + optional measurements, and every
    available option with its default and min/max (from the design)."""
    return _run_node(["--info", design])


def list_designs():
    """Every installed design (name, version, description)."""
    return _run_node(["--list-designs"])["designs"]


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="pattern draft",
        description="Draft a FreeSewing design (any installed @freesewing/<name>).")
    ap.add_argument("--design", help="design name, e.g. teagan")
    ap.add_argument("--measurements", help="JSON file of measurements (mm)")
    ap.add_argument("--options", help="JSON file of design options")
    ap.add_argument("--sa", type=float, default=10.0, help="seam allowance in mm (default 10)")
    ap.add_argument("--out", help="output directory for svg + paths JSON + summary")
    ap.add_argument("--info", action="store_true", help="print what the design needs, do not draft")
    ap.add_argument("--list-designs", action="store_true", help="print installed designs")
    args = ap.parse_args(argv)
    if args.list_designs:
        print(json.dumps({"designs": list_designs()}, ensure_ascii=False, indent=1))
        return 0
    if not args.design:
        ap.error("--design is required")
    if args.info:
        print(json.dumps(design_info(args.design), ensure_ascii=False, indent=1))
        return 0
    if not args.measurements or not args.out:
        ap.error("--measurements and --out are required to draft")
    measurements = json.loads(Path(args.measurements).read_text(encoding="utf-8"))
    options = json.loads(Path(args.options).read_text(encoding="utf-8")) if args.options else {}
    print(json.dumps(draft(args.design, measurements, options, args.sa, args.out),
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
