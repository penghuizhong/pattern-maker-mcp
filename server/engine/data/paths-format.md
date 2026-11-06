# Draft output format (`<design>-paths.json`)

What `draft.mjs` writes per design. Units are millimetres, origin at the
top-left of the draft (y grows downwards, as in the SVG). This is the
same shape `dump-json-v2.mjs` produced, plus every path per part (not a
hardcoded subset) and every snippet.

```json
{
  "<stack>": {                          // e.g. "teagan.front"
    "topLeft": {"x": 0, "y": 0},        // stack offset in the draft
    "paths": {
      "<name>": [                       // every path in the part:
        {"type": "move", "to": {"x", "y"}},
        {"type": "line", "from": {"x", "y"}, "to": {"x", "y"}},
        {"type": "curve", "from": {"x", "y"},
         "cp1": {"x", "y"}, "cp2": {"x", "y"}, "to": {"x", "y"}}
      ],
      "seam": [...],                    // net outline (closed)
      "sa": [...],                      // cut outline (seam + seam allowance)
      "grainline": [...]                // also exposed under the plain key
                                        // when the part names it
                                        // __macro_grainline_grainline_line
    },
    "notches": [                        // snippets with def notch/bnotch
      {"name": "...", "def": "notch", "x": 0, "y": 0}
    ],
    "snippets": [                       // every snippet in the part
      {"name": "...", "def": "...", "x": 0, "y": 0}
    ],
    "title": {"x": 0, "y": 0} | null    // piece-title anchor (if the part has one)
  }
}
```

## Notes

- **Ops.** Only `move` / `line` / `curve` (cubic Bézier, two control
  points). `from` is the previous op's end; a path always starts with
  a `move`.
- **Closed paths.** A path is closed when its last op ends where it
  started; the writer (`write_dxf_aama`) also honours the polyline
  closed flag when it flattens. Do not assume an explicit closing op.
- **Which paths the writer reads.** `write_dxf_aama` uses only
  `paths.seam`, `paths.sa`, `paths.grainline` (when present),
  `notches` and `title`. Every other path in the file (sideSeam,
  hemBase, chest/waist lines, macro banners, cut-on-fold, scalebox)
  is reference geometry for inspection, ignored by the writer.
- **Notches.** A notch snippet's anchor lies on the seam; the writer
  projects it onto the cut line. `bnotch` is a double notch.
- **The SVG** (`<design>.svg`) is the same draft rendered by the theme
  plugin. It carries a date stamp, so it is not byte-stable across
  days; the paths JSON is the stable artefact -- compare that, not the
  SVG, when checking a draft reproduces.
