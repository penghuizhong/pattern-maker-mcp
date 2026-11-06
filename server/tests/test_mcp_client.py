#!/usr/bin/env python3
"""Smoke-test the MCP server end to end: spawn `pattern serve` over stdio,
list tools, call all six against the known test files, and check results.

Run: .venv/bin/python tests/test_mcp_client.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = "/home/hatch/workspace/your_files/pattern-maker-mcp-repo/server/.venv/bin/pattern"
TROUSER = "/home/hatch/workspace/your_files/user-dxf-1/1.dxf"
TROUSER_Q = "/home/hatch/workspace/your_files/user-dxf-1/quantified.json"
TEAGAN_PATHS = "/home/hatch/workspace/your_files/freesewing-teagan-test/teagan-paths-v2.json"
JOB = "/tmp/job-test"  # rebuilt here each run: /tmp is wiped between sessions


def ensure_job_fixture():
    """Rebuild /tmp/job-test (a valid job: requirements, measurements with
    a source, design v0.1, verification pass, approval for release)."""
    job = Path(JOB)
    (job / "outputs" / "v0.1").mkdir(parents=True, exist_ok=True)
    (job / "requirements.md").write_text(
        "# Test job (MCP smoke-test fixture)\n\nSmoke-test job for the MCP server test suite. Not a real garment job.\n",
        encoding="utf-8",
    )
    (job / "measurements.json").write_text(
        '{"source": "test fixture: temporary measurements (2026-11-03), not product sizes", "chest": 960, "waist": 820}\n',
        encoding="utf-8",
    )
    (job / "design.json").write_text('{"version": "v0.1", "open_items": []}\n', encoding="utf-8")
    (job / "verification.json").write_text('{"status": "pass"}\n', encoding="utf-8")
    (job / "approval.md").write_text("# Approval (test fixture)\n\nv0.1 approved for release (test fixture).\n", encoding="utf-8")

# The 2026-11-03 temporary measurements (mm) the Teagan chain was first
# proven with -- guessed values to verify the run, NOT product sizes.
TEAGAN_MEASUREMENTS = {
    "biceps": 340, "chest": 960, "hips": 980, "hpsToBust": 260,
    "hpsToWaistBack": 420, "neck": 380, "shoulderToShoulder": 440,
    "shoulderSlope": 13, "waistToArmpit": 180, "waistToHips": 200,
    "waist": 820, "shoulderToWrist": 600, "wrist": 170,
}
TEAGAN_FITTED_OPTIONS = {"fitWaist": True, "waistEase": 0.08, "chestEase": 0.05}


def tool_json(result):
    assert len(result.content) == 1, result.content
    return json.loads(result.content[0].text)


async def main():
    ensure_job_fixture()
    params = StdioServerParameters(command=SERVER, args=["serve"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("tools:", names)
            assert names == ["quantify_dxf", "plot_numbered_dxf", "write_dxf_aama",
                             "check_job", "draft_freesewing", "freesewing_design_info"], names
            for t in tools.tools:
                print(f"  {t.name}: {json.dumps(t.input_schema.get('properties', {}), ensure_ascii=False)[:220]}")

            # 1. quantify (same flags as the stored quantified.json)
            r = tool_json(await session.call_tool("quantify_dxf", {
                "dxf_path": TROUSER, "out_json": "/tmp/mcp-q.json",
                "by_block": True, "decode_gbk": True, "unit_factor": 1.0}))
            print("quantify pieces:", len(r["pieces"]), "| unsupported:", r["unsupported"],
                  "| mode:", r["mode"])
            # 10 pattern pieces + _MODELSPACE_TEXT (header texts in modelspace)
            assert len(r["pieces"]) == 11 and r["unsupported"] == []
            disk = json.load(open("/tmp/mcp-q.json"))
            stored = json.load(open(TROUSER_Q))
            disk.pop("source"); stored.pop("source")
            assert disk == stored, "MCP quantify output != stored quantified.json"
            print("quantify output == stored quantified.json (ignoring source path)")

            # 2. plot
            r = tool_json(await session.call_tool("plot_numbered_dxf", {
                "dxf_path": TROUSER, "out_png": "/tmp/mcp-plot.png"}))
            print("plot pieces:", len(r["pieces"]), "| total_labels:", r["total_labels"])
            assert r["total_labels"] == 191 and len(r["pieces"]) == 10

            # 3. write-dxf --miter
            r = tool_json(await session.call_tool("write_dxf_aama", {
                "paths_json": TEAGAN_PATHS, "out_dxf": "/tmp/mcp-v3.dxf", "miter": True}))
            print("write_dxf pieces:", r["pieces"], "| numbers:", r["total_numbers"],
                  "| notches:", r["notches"])
            assert r["total_numbers"] == 102 and r["notches"] == 4

            # 4a. check normal + release (job has approval.md)
            r = tool_json(await session.call_tool("check_job", {"job_dir": JOB}))
            print("check normal:", r)
            assert r["passed"] is True
            r = tool_json(await session.call_tool("check_job", {"job_dir": JOB, "release": True}))
            print("check release:", r)
            assert r["passed"] is True

            # 4b. check release without approval.md must FAIL (gate, not crash)
            import shutil
            shutil.copytree(JOB, "/tmp/job-test-noapp", dirs_exist_ok=True)
            os.remove("/tmp/job-test-noapp/approval.md")
            r = tool_json(await session.call_tool("check_job", {"job_dir": "/tmp/job-test-noapp", "release": True}))
            print("check release (no approval):", r)
            assert r["passed"] is False and any("approval.md" in e for e in r["errors"])

            # 5. draft Teagan fitted (same measurements + options as the
            # stored teagan-paths-v2.json) -- paths must reproduce it
            r = tool_json(await session.call_tool("draft_freesewing", {
                "design": "teagan", "measurements": TEAGAN_MEASUREMENTS,
                "options": TEAGAN_FITTED_OPTIONS, "out_dir": "/tmp/mcp-draft-teagan"}))
            print("draft teagan stacks:", [s["name"] for s in r["stacks"]],
                  "| warnings:", r["warnings"], "| sa:", r["sa_mm"], "| source:", r["source"])
            assert r["design"] == "teagan" and r["warnings"] == []
            assert r["source"] == "library" and r["libraryPath"].endswith("library/designs/teagan/src/index.mjs")
            assert sorted(r["requiredMeasurements"]) == sorted(TEAGAN_MEASUREMENTS)
            assert r["options"]["fitWaist"] is True and r["options"]["waistEase"] == 0.08
            svg = open(r["files"]["svg"], encoding="utf-8").read()
            assert len(svg) > 10000 and "teagan.front" in svg
            fresh = json.load(open(r["files"]["paths"]))
            stored = json.load(open(TEAGAN_PATHS))
            assert sorted(fresh) == sorted(stored)
            for name in stored:
                for key in ("topLeft", "notches", "title"):
                    assert fresh[name][key] == stored[name][key], (name, key)
                for key in stored[name]["paths"]:
                    assert fresh[name]["paths"][key] == stored[name]["paths"][key], (name, key)
            print("draft teagan paths == stored teagan-paths-v2.json (contract subset)")

            # 6. draft Brian with the same measurements -- proves the
            # runner is generic, not Teagan-specific (Brian needs 11 of
            # the 13; hips + waist come back as unused warnings)
            r = tool_json(await session.call_tool("draft_freesewing", {
                "design": "brian", "measurements": TEAGAN_MEASUREMENTS,
                "out_dir": "/tmp/mcp-draft-brian"}))
            print("draft brian stacks:", [s["name"] for s in r["stacks"]],
                  "| warnings:", r["warnings"], "| source:", r["source"])
            assert r["design"] == "brian" and len(r["stacks"]) == 3
            assert r["source"] == "library"
            assert any("hips" in w for w in r["warnings"])

            # 7. design info: Teagan's requirements come from the design
            r = tool_json(await session.call_tool("freesewing_design_info", {"design": "teagan"}))
            print("info teagan required:", len(r["requiredMeasurements"]),
                  "| options:", len(r["options"]))
            assert sorted(r["requiredMeasurements"]) == sorted(TEAGAN_MEASUREMENTS)
            assert r["options"]["fitWaist"] == {"type": "bool", "default": False}
            assert r["options"]["waistEase"] == {"type": "pct", "default": 25, "min": 8, "max": 40}

            # 8. draft with missing measurements must FAIL with the list
            res = await session.call_tool("draft_freesewing", {
                "design": "teagan", "measurements": {"chest": 960},
                "out_dir": "/tmp/mcp-draft-fail"})
            assert res.is_error, res
            err = res.content[0].text
            print("draft (missing measurements) error:", err[:160])
            assert "missing required measurements" in err and "biceps" in err

            # 9. draft of a design that is not installed must FAIL with
            # the installed list
            res = await session.call_tool("draft_freesewing", {
                "design": "aaron", "measurements": TEAGAN_MEASUREMENTS,
                "out_dir": "/tmp/mcp-draft-fail"})
            assert res.is_error, res
            err = res.content[0].text
            print("draft (not installed) error:", err[:200])
            assert "not available" in err and "teagan" in err and "brian" in err

            # 10. chain: write DXF from the FRESH Teagan paths JSON
            r = tool_json(await session.call_tool("write_dxf_aama", {
                "paths_json": "/tmp/mcp-draft-teagan/teagan-paths.json",
                "out_dxf": "/tmp/mcp-v3-fresh.dxf", "miter": True}))
            print("write_dxf from fresh draft:", r["pieces"], "| numbers:",
                  r["total_numbers"], "| notches:", r["notches"])
            assert r["total_numbers"] == 102 and r["notches"] == 4

    print("ALL MCP CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
