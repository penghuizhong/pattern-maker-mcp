# Engine — 通用生成纸样引擎

The generation engine: give it data (measurements + options), it gives
back a pattern (SVG + JSON paths). It is the FreeSewing framework,
pinned as a dependency, plus this project's runner and data structures.
It does not contain any pattern of its own -- patterns live in
`../library/`.

## Layout

```
server/
├── package.json, package-lock.json, node_modules/   # Node root: the framework
├── engine/
│   ├── README.md                  # this file
│   ├── runner/
│   │   └── draft.mjs              # generic draft runner
│   └── data/                      # 数据结构 (generated, checked in)
│       ├── measurements.json      # canonical 42 measurements
│       ├── settings.json          # core pattern settings defaults
│       ├── paths-format.md        # the draft output format
│       └── generate.mjs           # regenerates the data files
└── library/                       # 基础纸样库 (the patterns)
```

## Framework (the foundation, not a fork)

FreeSewing 4.10.2, MIT, pinned exact in `server/package.json`
(`package-lock.json` is the pin). The framework is a dependency, not
vendored source: it is generic machinery (points, paths, curves, seam
allowance, layout, SVG rendering) maintained upstream. What it provides:

| Piece | Package | What it does |
|---|---|---|
| Core | `@freesewing/core` | `Design` / `Pattern`, `Point`, `Path`, `Store`, `Stack`, `Part`, `Snippet`, SVG renderer, plugin system, settings |
| Config | `@freesewing/config` | Canonical measurement list (42), degree measurements, sewing techniques |
| Plugins | `@freesewing/plugin-theme` | SVG theme (paperless info, titles, date stamp) |
| | `@freesewing/plugin-transform` | Point/path transforms (needed at runtime) |
| | `@freesewing/plugin-bust` | Bust adjustment (used by the Brian block) |
| Models (dev) | `@freesewing/models` | Standard measurement sets (neckstimate) -- used only by `data/generate.mjs` |

Core source map (`node_modules/@freesewing/core/src/`, 7.3k lines):
`design.mjs` (Design constructor), `pattern/` (Pattern: drafter,
renderer, sampler, plugins, config), `part.mjs`, `path.mjs`,
`point.mjs`, `store.mjs`, `stack.mjs`, `snippet.mjs`, `svg.mjs`,
`bezier.mjs`, `config.mjs` (settings defaults), `hooks.mjs`,
`utils.mjs`, `attributes.mjs`, `defs.mjs`.

## Runner (`runner/draft.mjs`)

One generic runner for every design. It resolves a design from the
library first (`../library/`, by directory scan -- no hardcoded list),
then from installed npm designs (`@freesewing/<name>`). It discovers
what a design needs from the design itself (`pattern.getConfig()`),
validates the caller's measurements against that list, and warns on
unknown options / out-of-range values instead of failing silently.
Each call runs two drafts with the same settings: one without the
theme for the paths JSON, one with the theme for the SVG.

```
node engine/runner/draft.mjs --design <name> --measurements <file.json>
  [--options <file.json>] [--sa <mm>] --out <dir> [--library <dir>]
node engine/runner/draft.mjs --design <name> --info
node engine/runner/draft.mjs --list-designs
```

Measurements are millimetres; `pct` options are fractions (0.08 = 8%)
while the design spec states min/max in percent -- the runner converts
before the range check.

## Data structures (`data/`)

All generated from the framework by `data/generate.mjs` (run it after
upgrading the framework or adding a design). Do not hand-edit the
generated files; fix the generator or the framework version instead.

- `measurements.json` -- the 42 canonical measurements (sorted, plus
  top-to-bottom order and the degree list: only `shoulderSlope` is in
  degrees, the rest are mm).
- `settings.json` -- core pattern settings defaults (`complete`,
  `expand`, `idPrefix`, `stackPrefix`, `locale`, `units`, `margin`,
  `scale`, `layout`) plus the runner's `sa` default (10 mm).
- `paths-format.md` -- the draft output format (stacks, paths, ops,
  notches, title).
- Per-design requirements live with the library, not here:
  `../library/data/schemas/<design>.json` (required + optional
  measurements, options with defaults and min/max).

## Add a design

Two ways, both picked up without touching the runner:

1. **Vendor it into the library** (preferred for base patterns):
   copy the design's `src/`, `about.json`, `i18n/`, `package.json`,
   `README.md` into `../library/<category>/<name>/`, rewrite any
   `@freesewing/<other-design>` imports to relative paths inside the
   library (framework imports stay as-is), then run
   `node engine/data/generate.mjs` to add its schema.
2. **`npm install @freesewing/<name>`** in `server/` (for a
   try-out): the runner's npm fallback finds it. The library still
   wins on a name conflict.

## What the engine does not do

- No DXF: the engine produces SVG + JSON paths only. DXF writing is
  the Python side (`write_dxf_aama`).
- No grading: re-drafting per measurement set is the grading mechanism;
  there is no size-rule table in the framework.
- No fitting: the engine proves geometry only. Whether a draft fits a
  body is a human judgement, checked against the quantified DXF.
