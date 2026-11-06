# pattern-making (0.1.0) — CLI + MCP server

Pattern-making tools, packaged so an agent calls typed tools instead of
reading prose and running scripts by path. **MCP server is the core,
the CLI package is the foundation** (user decision 2026-11-06).

The four tools are the verified scripts from the `pattern-making` skill
(`~/workspace/custom-skills/pattern-making/scripts/`), refactored into
importable library functions with identical behaviour — every check below
reproduces the scripts' known outputs.

## Tools

| MCP tool | CLI | What it does |
|---|---|---|
| `quantify_dxf` | `pattern quantify` | DXF → quantified JSON. Every number is measured from the file; unmeasurable entities are listed under `unsupported`, never dropped. |
| `plot_numbered_dxf` | `pattern plot` | DXF → numbered verification PNG (layer 2 black #, layer 4 red #, cm). |
| `write_dxf_aama` | `pattern write-dxf` | FreeSewing JSON paths → DXF-AAMA (R12). `--miter` turns SA bevels into sharp corners. |
| `check_job` | `pattern check` | Validation gate on a job folder; `--release` adds the approval gate. A failed gate must be reported, never worked around. |

Tool results are summaries + file paths. The full quantified JSON stays
in the file it was written to, not in the conversation.

## Install

System pip cannot install this (it refuses to replace Debian's
`typing_extensions` 4.10.0, which FastMCP needs newer). Use a venv:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pattern --version   # pattern 0.1.0
```

## CLI

```bash
pattern quantify --in 1.dxf --out quantified.json --by-block --decode-gbk --unit-factor 1
pattern plot --in 1.dxf --out numbered.png [--title "标题"]
pattern write-dxf --input teagan-paths-v2.json --output out.dxf [--miter]
pattern check --job jobs/<款号> [--release]
pattern serve   # start the MCP server (stdio)
```

## MCP server

Stdio transport. Add to the agent's MCP config:

```json
{
  "mcpServers": {
    "pattern-making": {
      "command": "/home/hatch/workspace/your_files/pattern-maker-mcp-repo/server/.venv/bin/pattern",
      "args": ["serve"]
    }
  }
}
```

Claude Code: `~/.claude.json` (or `.mcp.json` in the project).
OpenClaw: the gateway/agent `mcpServers` section, same shape.
Adjust the path if the project moves.

## Tests

```bash
# CLI smoke test (run the four commands against the known files first,
# see the verification notes in this README's history)
.venv/bin/python tests/test_mcp_client.py   # spawns `pattern serve`, calls all 4 tools
```

Verified 2026-11-06 against the known files:

- `quantify --by-block --decode-gbk --unit-factor 1` on the trouser
  `1.dxf` reproduces the stored `quantified.json` exactly (ignoring the
  `source` path). Note the `--unit-factor 1`: that file declares
  `$INSUNITS=6` (metres) but is actually in mm.
- `plot` on `1.dxf`: 10 pieces, 191 labels; pixel-identical to the old
  `dxf_plot.py` under the same matplotlib. (PNG pixels differ from the
  stored `numbered-full-v2.png` only because the venv has matplotlib
  3.11.2 vs 3.6.3 when that file was drawn — the data is identical.)
- `write-dxf --miter` on `teagan-paths-v2.json`: byte-identical to
  `teagan-fitted-v3.1.dxf` except ezdxf's `$TDCREATE`/`$TDUPDATE`
  timestamps; readback verify `ALL CHECKS PASSED` (#1–#102).
- `check`: normal pass, `--release` without `approval.md` fails,
  `--release` with it passes — through both the CLI and the MCP tool.

## Known limits (v0.1.0)

- `write_dxf_aama` is Teagan-only for now: FRONT/BACK/SLEEVE layout,
  single size M, style metadata hardcoded. Parameterizing it belongs to
  the `draft_freesewing` tool (phase 2: a parameterized Node runner for
  measurements + options, replacing hardcoded `variant.mjs`).
- `plot` CJK fonts: Linux Noto Sans CJK path first, then macOS PingFang /
  Hiragino / Noto Sans CJK SC / Songti SC. Without any of them, Chinese
  titles render as boxes (data unaffected).
- The skill repo (`pattern-maker-skills` on GitHub) still ships the old
  `scripts/` and a SKILL.md that references them. Thinning SKILL.md to
  point at this package is the next step, not done here.
- Repo: `penghuizhong/pattern-maker-mcp` (renamed from
  `pattern-maker-skills` 2026-11-06). This package lives in `server/`;
  the skill stays at the repo root.
