#!/usr/bin/env python3
"""Grading table from the locked size tables. Standard library only.

Usage:
  python3 scripts/grading.py --garment womens-suit
  python3 scripts/grading.py --garment mens-suit --sizes S M L --out jobs/x/outputs/v0.1/graded.json

Rules (see references/grading.md):
  - The table IS the grading result. This script never invents step sizes
    for the mens table (its shoulder/length steps are non-uniform).
  - It checks the invariants on every size and exits non-zero on any
    violation. Never silently fix a number: report the conflict to the user.
"""
import argparse
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent

# jacket_chest - jacket_waist, jacket_waist - trousers_waist, jacket_hip - trousers_hip
INVARIANTS = {
    "mens-suit": {"chest_waist": 14, "waist_diff": 6, "hip_diff": 2},
    "womens-suit": {"chest_waist": 16, "waist_diff": 6, "hip_diff": 0},
}

# womens hip: jacket hip - trousers hip is 0 on every size (100/100, 104/104, ...).
# mens hip: jacket hip - trousers hip is 2 on every size (104/102, 108/106, ...).


def load(garment):
    path = SKILL_DIR / "measurements" / f"{garment}.json"
    if not path.exists():
        raise SystemExit(f"unknown garment table: {path} (expected mens-suit or womens-suit)")
    return json.loads(path.read_text(encoding="utf-8"))


def check(data, sizes):
    """Return a list of invariant violations (empty = pass)."""
    inv = INVARIANTS[data["garment"]]
    errors = []
    for size in sizes:
        j = data["jacket"][size]
        t = data["trousers"][size]
        checks = {
            "chest_waist": j["chest"] - j["waist"],
            "waist_diff": j["waist"] - t["waist"],
            "hip_diff": j["hip"] - t["hip"],
        }
        for name, want in inv.items():
            if checks[name] != want:
                errors.append(
                    f"{size}: {name} = {checks[name]}, expected {want} "
                    f"(jacket={j}, trousers={t})"
                )
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--garment", required=True, choices=["mens-suit", "womens-suit"])
    ap.add_argument("--sizes", nargs="*", default=None, help="default: all sizes in the table")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    data = load(args.garment)
    sizes = args.sizes or [m["letter"] for m in data["size_map"]]
    missing = [s for s in sizes if s not in data["jacket"] or s not in data["trousers"]]
    if missing:
        raise SystemExit(f"missing sizes in table {args.garment}: {missing}")

    errors = check(data, sizes)
    result = {
        "garment": data["garment"],
        "measure_type": data["measure_type"],
        "unit": data["unit"],
        "source": data["source"],
        "source_note": data["source_note"],
        "sizes": sizes,
        "jacket": {s: data["jacket"][s] for s in sizes},
        "trousers": {s: data["trousers"][s] for s in sizes},
        "size_map": [m for m in data["size_map"] if m["letter"] in sizes],
        "invariants_checked": INVARIANTS[data["garment"]],
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(text)
    if errors:
        print("GRADING CHECK FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"grading check passed: {args.garment} {','.join(sizes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
