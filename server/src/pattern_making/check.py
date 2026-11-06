#!/usr/bin/env python3
"""Validation gate for a pattern job. Standard library only.

Normal check: required files exist, JSON parses, measurements.json states
its source (user-supplied numbers, never guessed), open_items agree
between design.json and requirements.md, and a verification.json exists
for the current version.
--release additionally requires: verification status == pass,
approval.md with an explicit user release record, and no open items
(or open items explicitly accepted as known risk in approval.md).

Library: check(job, release=False) -> {"passed": bool, "errors": [...]}.
CLI: `pattern check --job jobs/<款号> [--release]` (exit 0 = gate passed).
The agent must NOT work around a failure; it reports the failing items
to the user.
"""
import argparse
import json
import re
import sys
from pathlib import Path


def check(job, release=False):
    """Run the validation gate. Returns {"passed", "errors", "job", "release"}."""
    job = Path(job)
    errors = []

    # 1. Required files
    req = job / "requirements.md"
    meas = job / "measurements.json"
    design_p = job / "design.json"
    verif_p = job / "verification.json"
    for p, name in [(req, "requirements.md"), (meas, "measurements.json"), (design_p, "design.json")]:
        if not p.exists():
            errors.append(f"missing {name} in {job}")

    design = None
    measurements = None
    if design_p.exists():
        try:
            design = json.loads(design_p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"design.json is not valid JSON: {e}")
    if meas.exists():
        try:
            measurements = json.loads(meas.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"measurements.json is not valid JSON: {e}")

    # 2. Measurements are user-supplied and state their source (never guessed)
    if measurements is not None:
        source = measurements.get("source")
        if not source or not isinstance(source, str):
            errors.append("measurements.json has no 'source' (where the numbers came from)")
        sizes = measurements.get("sizes")
        if sizes is not None and (not isinstance(sizes, list) or not sizes):
            errors.append("measurements.json 'sizes' must be a non-empty list")

    # 3. open_items agreement
    open_items = []
    if design is not None:
        open_items = design.get("open_items", [])
        if not isinstance(open_items, list):
            errors.append("design.json open_items must be a list")
            open_items = []
    if req.exists():
        req_text = req.read_text(encoding="utf-8")
        # Every open item id/keyword listed in design.json should appear in requirements.md
        for item in open_items:
            if isinstance(item, str) and item and item not in req_text:
                errors.append(f"open item '{item}' in design.json is not mentioned in requirements.md")

    # 4. Version outputs + verification
    version = design.get("version") if design else None
    if not version:
        errors.append("design.json has no version (e.g. v0.1)")
    elif not (job / "outputs" / version).exists():
        errors.append(f"outputs/{version}/ does not exist")
    if not verif_p.exists():
        errors.append("missing verification.json")
    verification = None
    if verif_p.exists():
        try:
            verification = json.loads(verif_p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"verification.json is not valid JSON: {e}")

    # 5. Release gate
    if release:
        if verification is None or verification.get("status") != "pass":
            errors.append("release blocked: verification.json status is not 'pass'")
        approval_p = job / "approval.md"
        approval = approval_p.read_text(encoding="utf-8") if approval_p.exists() else ""
        if not approval_p.exists():
            errors.append("release blocked: missing approval.md (user release record required)")
        else:
            if version and version not in approval:
                errors.append(f"release blocked: approval.md does not mention version {version}")
            if not re.search(r"放行|批准|approved|release", approval):
                errors.append("release blocked: approval.md has no explicit release wording")
        if open_items and "已知风险" not in approval and "known risk" not in approval.lower():
            errors.append("release blocked: open_items remain and approval.md does not record them as known risk")

    return {"passed": not errors, "errors": errors, "job": str(job), "release": release}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--release", action="store_true")
    args = ap.parse_args(argv)
    result = check(args.job, args.release)
    if result["errors"]:
        print(f"CHECK FAILED: {args.job}", file=sys.stderr)
        for e in result["errors"]:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"check passed: {args.job}" + (" (release gate)" if args.release else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
