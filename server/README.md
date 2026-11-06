# pattern-making (0.2.0) — CLI + MCP server

Pattern-making tools, packaged so an agent calls typed tools instead of
reading prose and running scripts by path. **MCP server is the core,
the CLI package is the foundation** (user decision 2026-11-06).

The six tools are the verified scripts from the `pattern-making` skill
(`~/workspace/custom-skills/pattern-making/scripts/`), refactored into
importable library functions with identical behaviour — every check below
reproduces the scripts' known outputs — plus a generic FreeSewing draft
runner that drafts from this project's own pattern library.

## Layout

```
server/
├── package.json, package-lock.json, node_modules/   # Node root: the framework
├── engine/                       # 通用生成纸样引擎
│   ├── runner/draft.mjs          # generic draft runner
│   └── data/                     # 数据结构 (measurements, settings, paths format)
├── library/                      # 基础纸样库 (vendored FreeSewing designs)
│   ├── blocks/brian/             # base block
│   ├── designs/teagan/           # garment
│   ├── parts/library/            # reusable parts
│   └── data/                     # 款式数据 (models, per-design schemas)
├── src/pattern_making/           # Python tools (quantify/plot/write/check/draft)
└── tests/
```

The framework (FreeSewing core + plugins, exact 4.10.2) is a pinned
dependency, not a fork. The pattern library is vendored source in this
repo, so its formulas are visible and extendable -- see
`engine/README.md` and `library/README.md` (and `library/NOTICE.md`
for the MIT attribution).

## Tools

| MCP tool | CLI | What it does |
|---|---|---|
| `quantify_dxf` | `pattern quantify` | DXF → quantified JSON. Every number is measured from the file; unmeasurable entities are listed under `unsupported`, never dropped. |
| `plot_numbered_dxf` | `pattern plot` | DXF → numbered verification PNG (layer 2 black #, layer 4 red #, cm). |
| `write_dxf_aama` | `pattern write-dxf` | FreeSewing JSON paths → DXF-AAMA (R12). `--miter` turns SA bevels into sharp corners. |
| `check_job` | `pattern check` | Validation gate on a job folder; `--release` adds the approval gate. A failed gate must be reported, never worked around. |
| `draft_freesewing` | `pattern draft` | FreeSewing design → SVG + JSON paths. Generic: any installed `@freesewing/<design>`; measurements + options from the caller, nothing hardcoded (see `freesewing/README.md`). |
| `freesewing_design_info` | `pattern draft --info` | What a design needs: required measurements + option specs (defaults, min/max), from the design itself. |

Tool results are summaries + file paths. The full quantified JSON stays
in the file it was written to, not in the conversation.

## Install

System pip cannot install this (it refuses to replace Debian's
`typing_extensions` 4.10.0, which FastMCP needs newer). Use a venv:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pattern --version   # pattern 0.2.0

# FreeSewing framework (draft tool only): Node deps for the engine.
# Run from server/ -- node_modules lives here, shared by the runner
# and the vendored library.
npm install
# Regenerate the engine/library data files after a framework upgrade
# or adding a design: node engine/data/generate.mjs
# Add a design later: vendor it into library/ (see library/README.md),
# or npm install @freesewing/<name> for a try-out.
```

## CLI

```bash
pattern quantify --in 1.dxf --out quantified.json --by-block --decode-gbk --unit-factor 1
pattern plot --in 1.dxf --out numbered.png [--title "标题"]
pattern write-dxf --input teagan-paths-v2.json --output out.dxf [--miter]
pattern check --job jobs/<款号> [--release]
pattern draft --design teagan --measurements m.json [--options o.json] [--sa 10] --out outdir
pattern draft --design teagan --info
pattern draft --list-designs
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
# CLI smoke test (run the commands against the known files first,
# see the verification notes in this README's history)
.venv/bin/python tests/test_mcp_client.py   # spawns `pattern serve`, calls all 6 tools
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
- `draft` Teagan fitted (the 2026-11-03 temporary measurements +
  fitWaist/waistEase 0.08/chestEase 0.05): the paths JSON reproduces
  the stored `teagan-paths-v2.json` exactly on the writer's contract
  (seam, sa, grainline, notches, title, topLeft per stack); the SVG
  matches `teagan-fitted.svg` except the theme's date stamp. The
  draft returns no warnings; resolved options are the design's
  default-merged set (50 keys).
- `draft` Brian with the same 13 measurements: 3 stacks
  (brian.back, brian.front, library.sleeve); hips + waist correctly
  reported as unused by Brian (it needs 11). This is the genericity
  proof: the runner is not Teagan-specific.
- `draft` errors: missing measurements fail with the required +
  missing lists; an uninstalled design (aaron) fails with the
  installed list (brian, library, teagan); unknown options come back
  as warnings, not silent acceptance.
- Chain: `write-dxf --miter` from the fresh Teagan draft paths gives
  the same 102 numbers / 4 notches as from the stored paths file.
- Library (vendored FreeSewing 4.10.2): drafting Teagan from
  `library/designs/teagan/` reproduces the stored
  `teagan-paths-v2.json` exactly on the writer's contract, and Brian
  from `library/blocks/brian/` drafts 3 stacks -- the vendored
  formulas (with intra-library imports rewritten to relative paths)
  behave identically to the npm packages. `draft` reports
  `source: "library"` for these; the npm fallback is dormant until a
  design is `npm install`ed.

## Known limits (v0.2.0)

- `write_dxf_aama` is Teagan-only for now: FRONT/BACK/SLEEVE layout,
  single size M, style metadata hardcoded. Parameterizing it for
  other designs is separate work from the (now generic) draft tool.
- `draft_freesewing` discovery: the library is scanned for
  `<category>/<name>/src/index.mjs` directories (categories are
  organisation only); npm designs are found by importing each
  `@freesewing/*` package and keeping the ones that export a design
  constructor -- keywords and `about.json` do not discriminate (every
  @freesewing package carries "design" in its keywords).
  `@freesewing/library` lists as a design (it is a Design object
  bundling reusable parts); drafting it is not a garment.
- pct options are passed as fractions (0.08 = 8%) while the design
  spec states min/max in percent; the runner converts before the
  range check.
- `plot` CJK fonts: Linux Noto Sans CJK path first, then macOS PingFang /
  Hiragino / Noto Sans CJK SC / Songti SC. Without any of them, Chinese
  titles render as boxes (data unaffected).
- SKILL.md (repo root) now points at this package; the thinning landed
  2026-11-06 (staging, with the server/ 0.2.0 work).
- Repo: `penghuizhong/pattern-maker-mcp` (renamed from
  `pattern-maker-skills` 2026-11-06). This package lives in `server/`;
  the skill stays at the repo root.
