#!/usr/bin/env python3
"""Validation gate for a pattern job. Standard library only.

Usage:
  python3 scripts/check_job.py --job jobs/<款号>
  python3 scripts/check_job.py --job jobs/<款号> --release

Normal check: required files exist, JSON parses, sizes exist in the
locked tables, open_items agree between design.json and requirements.md,
and a verification.json exists for the current version.
--release additionally requires: verification status == pass,
approval.md with an explicit user release record, and no open items
(or open items explicitly accepted as known risk in approval.md).

Exit 0 = gate passed, non-zero = gate failed. The agent must NOT
work around a failure; it reports the failing items to the user.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


def fail(errors, msg):
    errors.append(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--release", action="store_true")
    args = ap.parse_args()
    job = Path(args.job)
    errors = []

    # 1. Required files
    req = job / "requirements.md"
    meas = job / "measurements.json"
    design_p = job / "design.json"
    verif_p = job / "verification.json"
    for p, name in [(req, "requirements.md"), (meas, "measurements.json"), (design_p, "design.json")]:
        if not p.exists():
            fail(errors, f"missing {name} in {job}")

    design = None
    measurements = None
    if design_p.exists():
        try:
            design = json.loads(design_p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            fail(errors, f"design.json is not valid JSON: {e}")
    if meas.exists():
        try:
            measurements = json.loads(meas.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            fail(errors, f"measurements.json is not valid JSON: {e}")

    # 2. Measurements reference the locked tables and sizes exist there
    if measurements is not None:
        garment = measurements.get("garment")
        sizes = measurements.get("sizes", [])
        table_p = SKILL_DIR / "measurements" / f"{garment}.json" if garment else None
        if not table_p or not table_p.exists():
            fail(errors, f"measurements.json garment '{garment}' has no locked table in measurements/")
        else:
            table = json.loads(table_p.read_text(encoding="utf-8"))
            for s in sizes:
                if s not in table["jacket"] or s not in table["trousers"]:
                    fail(errors, f"size {s} not in locked table {garment}")

    # 3. open_items agreement
    open_items = []
    if design is not None:
        open_items = design.get("open_items", [])
        if not isinstance(open_items, list):
            fail(errors, "design.json open_items must be a list")
            open_items = []
    if req.exists():
        req_text = req.read_text(encoding="utf-8")
        # Every open item id/keyword listed in design.json should appear in requirements.md
        for item in open_items:
            if isinstance(item, str) and item and item not in req_text:
                fail(errors, f"open item '{item}' in design.json is not mentioned in requirements.md")

    # 4. Version outputs + verification
    version = design.get("version") if design else None
    if not version:
        fail(errors, "design.json has no version (e.g. v0.1)")
    elif not (job / "outputs" / version).exists():
        fail(errors, f"outputs/{version}/ does not exist")
    if not verif_p.exists():
        fail(errors, "missing verification.json")
    verification = None
    if verif_p.exists():
        try:
            verification = json.loads(verif_p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            fail(errors, f"verification.json is not valid JSON: {e}")

    # 5. Release gate
    if args.release:
        if verification is None or verification.get("status") != "pass":
            fail(errors, "release blocked: verification.json status is not 'pass'")
        approval_p = job / "approval.md"
        approval = approval_p.read_text(encoding="utf-8") if approval_p.exists() else ""
        if not approval_p.exists():
            fail(errors, "release blocked: missing approval.md (user release record required)")
        else:
            if version and version not in approval:
                fail(errors, f"release blocked: approval.md does not mention version {version}")
            if not re.search(r"放行|批准|approved|release", approval):
                fail(errors, "release blocked: approval.md has no explicit release wording")
        if open_items and "已知风险" not in approval and "known risk" not in approval.lower():
            fail(errors, "release blocked: open_items remain and approval.md does not record them as known risk")

    if errors:
        print(f"CHECK FAILED: {job}", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"check passed: {job}" + (" (release gate)" if args.release else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
