#!/usr/bin/env python3
"""Smoke-test the MCP server end to end: spawn `pattern serve` over stdio,
list tools, call all four against the known test files, and check results.

Run: .venv/bin/python tests/test_mcp_client.py
"""
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# No hardcoded absolute paths: repo-relative paths come from this file's
# location; the jobs data root is configurable (env PATTERN_JOBS_ROOT),
# defaulting to ~/workspace/jobs/ (local default, not a fixed HOME).
REPO = Path(__file__).resolve().parent.parent  # server/
SERVER = str(REPO / ".venv" / "bin" / "pattern")
TEE163_PATHS = str(Path(__file__).resolve().parent / "fixtures" / "tee163-paths.json")
JOBS_ROOT = Path(os.environ.get("PATTERN_JOBS_ROOT", "~/workspace/jobs")).expanduser()
TROUSER = str(JOBS_ROOT / "user-dxf-1" / "1.dxf")
TROUSER_Q = str(JOBS_ROOT / "user-dxf-1" / "outputs" / "v0.1" / "quantified.json")
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
                             "reanchor_segments", "dxf_to_apattern", "check_job"], names
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

            # 3. write-dxf --miter (from the stored 163 T-shirt paths JSON)
            r = tool_json(await session.call_tool("write_dxf_aama", {
                "paths_json": TEE163_PATHS, "out_dxf": "/tmp/mcp-v3.dxf", "miter": True}))
            print("write_dxf pieces:", r["pieces"], "| numbers:", r["total_numbers"],
                  "| notches:", r["notches"])
            assert r["total_numbers"] == 171 and r["notches"] == 0

            # 3b. reanchor: women's block v2 anchors onto the v3 DXF.
            # # numbers shuffled v2->v3, but every anchor must match and
            # every segment length must equal its v2 value.
            anchors = str(JOBS_ROOT / "womens-block-v2" / "outputs" / "v0.1" / "segments-anchors.json")
            v3dxf = str(JOBS_ROOT / "womens-block-v3" / "source.dxf")
            if Path(anchors).exists() and Path(v3dxf).exists():
                r = tool_json(await session.call_tool("reanchor_segments", {
                    "anchors_path": anchors, "dxf_path": v3dxf,
                    "out_json": "/tmp/mcp-reanchored.json"}))
                print("reanchor segments:", len(r["segments"]), "| unmatched:", r["unmatched"])
                assert r["unmatched"] == []
                expect = {"后领围线": 8.63, "后中长": 39.5, "胸围线": 48.0, "腰围线": 48.0,
                          "背宽线": 18.5, "后小肩长": 12.62, "前小肩长": 12.6,
                          "前领围线": 12.32, "前中长": 35.0, "乳距宽": 9.0,
                          "后袖笼长": 22.78, "前袖笼长": 21.9}
                got = {s["name"]: s["length_cm"] for s in r["segments"]}
                assert got == expect, got
                print("reanchor lengths == v2 lengths")
            else:
                print("reanchor skipped: womens-block v2/v3 jobs not present")

            # 3c. apattern: tshirt-165-96 v0.2 DXF -> first .apattern.
            # Point naming is the human decision (which # is the armpit);
            # the test records it inline. All 20 segment lengths must
            # equal the anchors file, and both pairing checks must pass.
            v02 = JOBS_ROOT / "tshirt-165-96" / "outputs" / "v0.2"
            if (v02 / "source.dxf").exists() and (v02 / "segments-anchors.json").exists():
                names = {
                    "points": {
                        "front": {"12": "hem_l", "13": "armpit_l", "14": "shoulder_joint_l",
                                  "15": "shoulder_tip_l", "16": "neckline_c", "17": "shoulder_tip_r",
                                  "18": "shoulder_joint_r", "19": "armpit_r", "20": "hem_r",
                                  "26": "waist_r", "31": "chest_w_r", "36": "waist_l", "41": "chest_w_l"},
                        "back": {"55": "hem_l", "56": "armpit_l", "57": "shoulder_joint_l",
                                 "58": "shoulder_tip_l", "59": "neckline_c", "60": "shoulder_tip_r",
                                 "61": "shoulder_joint_r", "62": "armpit_r", "63": "hem_r",
                                 "64": "center_hem", "69": "back_w_l", "75": "waist_l",
                                 "79": "back_w_r", "85": "waist_r"},
                        "sleeve": {"96": "cuff_l", "97": "cap_l", "98": "cap_top",
                                   "99": "cap_r", "100": "cuff_r", "105": "cuff_c"},
                        "collar": {"119": "collar_l", "120": "collar_w", "123": "collar_r"}},
                    "segments": {"前摆围": "hem", "前胸围": "chest", "前胸宽": "chest_width",
                                 "前腰围": "waist", "前袖笼线（右）": "armhole_r",
                                 "前袖笼线（左）": "armhole_l", "前领围线": "neckline",
                                 "后中长": "center_length", "后摆围": "hem", "后背宽": "back_width",
                                 "后胸围": "chest", "后腰围": "waist",
                                 "后袖笼线（右）": "armhole_r", "后袖笼线（左）": "armhole_l",
                                 "后领围线": "neckline", "袖口围": "cuff", "袖山线": "cap",
                                 "袖长": "sleeve_length", "领宽": "width", "领长": "length"},
                    "pieces": {
                        "front": {"label": "前片", "material": "面料", "quantity": 1, "symmetric": True},
                        "back": {"label": "后片", "material": "面料", "quantity": 1, "symmetric": True},
                        "sleeve": {"label": "袖片", "material": "面料", "quantity": 2, "symmetric": True},
                        "collar": {"label": "领片", "material": "罗纹", "quantity": 1, "symmetric": True}}}
                meta = {"style": "男士165-96t-shirt", "size": "M",
                        "source_dxf": "outputs/v0.2/source.dxf",
                        "source_note": "BUYI-TECH DXF-AAMA R12, 2026/11/6, 完整可生产版",
                        "derived_from": "tshirt-165-96 v0.1",
                        "changes": ["半片改整片", "缝份 1.0 改 0.8（下摆 2.0）", "加袖、领", "前领加深 10.0 cm"]}
                Path("/tmp/mcp-apattern-names.json").write_text(
                    json.dumps(names, ensure_ascii=False), encoding="utf-8")
                Path("/tmp/mcp-apattern-meta.json").write_text(
                    json.dumps(meta, ensure_ascii=False), encoding="utf-8")
                r = tool_json(await session.call_tool("dxf_to_apattern", {
                    "dxf_path": str(v02 / "source.dxf"),
                    "anchors_path": str(v02 / "segments-anchors.json"),
                    "quantified_path": str(v02 / "quantified.json"),
                    "names_json": "/tmp/mcp-apattern-names.json",
                    "meta_json": "/tmp/mcp-apattern-meta.json",
                    "out_path": "/tmp/mcp-tshirt-165-96-M.apattern"}))
                print("apattern:", r["pieces"], "pieces,", r["points"], "points,",
                      r["segments"], "segments,", r["edges"], "edges")
                assert r["pieces"] == 4 and r["points"] == 36 and r["segments"] == 20
                assert r["edges"] == 12
                assert all(c["pass"] for c in r["checks"]), r["checks"]
                print("apattern checks all pass")
            else:
                print("apattern skipped: tshirt-165-96 v0.2 job not present")

            # 4a. check normal + release (job has approval.md)
            r = tool_json(await session.call_tool("check_job", {"job_dir": JOB}))
            print("check normal:", r)
            assert r["passed"] is True
            r = tool_json(await session.call_tool("check_job", {"job_dir": JOB, "release": True}))
            print("check release:", r)
            assert r["passed"] is True

            # 4b. check release without approval.md must FAIL (gate, not crash)
            shutil.copytree(JOB, "/tmp/job-test-noapp", dirs_exist_ok=True)
            os.remove("/tmp/job-test-noapp/approval.md")
            r = tool_json(await session.call_tool("check_job", {"job_dir": "/tmp/job-test-noapp", "release": True}))
            print("check release (no approval):", r)
            assert r["passed"] is False and any("approval.md" in e for e in r["errors"])

    print("ALL MCP CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
