#!/usr/bin/env node
// Generic FreeSewing draft runner for the pattern-making engine.
//
// Drafts a design from the project's own pattern library
// (server/library/) first, and falls back to an installed npm design
// (@freesewing/<name>) when the library does not have it. Nothing about
// any design is hardcoded: the design name, the measurements and the
// options all come from the caller. What a design needs is discovered
// at runtime from the design itself (pattern.getConfig() -- the same
// source the FreeSewing docs point at: measurements and options are
// defined by the pattern design, not by the core library).
//
// How designs are found (no hardcoded lists):
//   library -- every <library>/<category>/<name>/src/index.mjs under the
//              library root is a candidate; a directory counts as a
//              design when its module exports a design constructor
//              named after the directory (capitalised, e.g. Teagan).
//              Categories (blocks/, designs/, parts/) are organisation
//              only; the scan does not care what they are called.
//   npm     -- every node_modules/@freesewing/* package whose module
//              exports such a constructor. (Keywords and about.json do
//              not discriminate: every @freesewing package carries
//              "design" in its keywords.)
// The library wins on a name conflict; the summary reports `source`
// ("library" or "npm") and, for library designs, the library path.
//
// The library root defaults to <node-root>/library, where the node root
// is found by walking up from this file to the directory holding
// node_modules/@freesewing/core. Pass --library <dir> to override.
//
// Modes:
//   --info <design>
//       Print the design's required + optional measurements and its
//       available options (default, min/max where the design defines
//       them). No draft is run. Use this to find out what to pass.
//   --list-designs
//       Print every available design (library + npm), with source.
//   --design <name> --measurements <file.json> [--options <file.json>]
//       [--sa <mm>] --out <dir> [--library <dir>]
//       Draft the design and write three files into <dir>:
//         <design>.svg          rendered pattern (theme plugin)
//         <design>-paths.json   per-stack paths/notches/title, the
//                               dump-json-v2 shape (all paths, not a
//                               hardcoded subset) -- feeds write_dxf_aama
//         <design>-summary.json the summary below, also printed to stdout
//
// The paths dump runs on a separate instance without the theme plugin:
// the theme only affects rendering, and a themed draft can add render
// artefacts to the stacks. The SVG runs on a second instance with the
// theme. Both instances get the same settings, so the geometry is
// identical.
//
// Measurements are millimetres (FreeSewing convention). Errors print a
// JSON object {"error": ...} to stderr and exit non-zero.
import { readdirSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { pluginTheme as theme } from '@freesewing/plugin-theme'

const HERE = dirname(fileURLToPath(import.meta.url))
const OPTION_TYPES = ['bool', 'pct', 'mm', 'deg', 'count']

function fail(msg, extra = {}) {
  console.error(JSON.stringify({ error: msg, ...extra }))
  process.exit(1)
}

// Walk up from a directory until one holding node_modules/@freesewing/core
// is found. That directory is the Node root (server/ in this project).
function findNodeRoot(start) {
  let dir = start
  for (;;) {
    try {
      readFileSync(join(dir, 'node_modules', '@freesewing', 'core', 'package.json'), 'utf8')
      return dir
    } catch {
      // not here -- go up
    }
    const parent = dirname(dir)
    if (parent === dir) return null
    dir = parent
  }
}

const NODE_ROOT = findNodeRoot(HERE)
if (!NODE_ROOT) fail('cannot find node_modules/@freesewing/core above ' + HERE)

const cap = (name) => name[0].toUpperCase() + name.slice(1)

// Is this module a design? It must export a design constructor named
// after the package/directory (capitalised) carrying a designConfig.
function designFromModule(mod, name) {
  const Design = mod[cap(name)]
  if (typeof Design === 'function' && Design.designConfig !== undefined) return Design
  return null
}

// Every installed npm design, discovered by importing each
// node_modules/@freesewing/* package.
async function listNpmDesigns() {
  const scope = join(NODE_ROOT, 'node_modules', '@freesewing')
  let names = []
  try {
    names = readdirSync(scope)
  } catch {
    return []
  }
  const out = []
  for (const name of names) {
    try {
      const mod = await import(`@freesewing/${name}`)
      if (!designFromModule(mod, name)) continue
      let version = null
      let description = ''
      try {
        const pkg = JSON.parse(readFileSync(join(scope, name, 'package.json'), 'utf8'))
        version = pkg.version
        description = pkg.description || ''
      } catch {
        // version/description are nice-to-have
      }
      out.push({ design: name, version, description, source: 'npm' })
    } catch {
      // not importable, or not a design -- skip
    }
  }
  return out.sort((a, b) => a.design.localeCompare(b.design))
}

// Candidate design directories under the library root:
// <library>/<category>/<name>/src/index.mjs. Categories are
// organisation only; any depth-2 directory with an index counts.
function scanLibrary(libraryRoot) {
  const out = []
  let categories = []
  try {
    categories = readdirSync(libraryRoot, { withFileTypes: true })
      .filter((d) => d.isDirectory())
      .map((d) => d.name)
  } catch {
    return out
  }
  for (const cat of categories) {
    let names = []
    try {
      names = readdirSync(join(libraryRoot, cat), { withFileTypes: true })
        .filter((d) => d.isDirectory())
        .map((d) => d.name)
    } catch {
      continue
    }
    for (const name of names) {
      const entry = join(libraryRoot, cat, name, 'src', 'index.mjs')
      try {
        readFileSync(entry)
        out.push({ design: name, entry })
      } catch {
        // no index -- not a design directory
      }
    }
  }
  return out
}

async function listLibraryDesigns(libraryRoot) {
  const out = []
  for (const { design, entry } of scanLibrary(libraryRoot)) {
    try {
      const mod = await import(pathToFileURL(entry).href)
      if (!designFromModule(mod, design)) continue
      let version = null
      let description = ''
      try {
        const about = JSON.parse(readFileSync(join(dirname(dirname(entry)), 'about.json'), 'utf8'))
        version = about.version
        description = about.description || ''
      } catch {
        // version/description are nice-to-have
      }
      out.push({ design, version, description, source: 'library', path: entry })
    } catch {
      // not importable, or not a design -- skip
    }
  }
  return out.sort((a, b) => a.design.localeCompare(b.design))
}

// Merged design list: library first, npm as fallback; the library wins
// on a name conflict.
async function listDesigns(libraryRoot) {
  const lib = await listLibraryDesigns(libraryRoot)
  const npm = await listNpmDesigns()
  const seen = new Set(lib.map((d) => d.design))
  return [...lib, ...npm.filter((d) => !seen.has(d.design))]
}

// Load a design package by name: library first, npm fallback.
// Returns {Design, about, source, path?}.
async function loadDesign(design, libraryRoot) {
  for (const { design: name, entry } of scanLibrary(libraryRoot)) {
    if (name !== design) continue
    const mod = await import(pathToFileURL(entry).href)
    const Design = designFromModule(mod, design)
    if (!Design) fail(`library design '${design}' does not export '${cap(design)}'`, { path: entry })
    return { Design, about: mod.about || null, source: 'library', path: entry }
  }
  let mod
  try {
    mod = await import(`@freesewing/${design}`)
  } catch {
    fail(`design '${design}' is not available`, {
      hint: `npm install @freesewing/${design} in ${NODE_ROOT}, or vendor it into ${libraryRoot}`,
      installed: await listDesigns(libraryRoot),
    })
  }
  const Design = designFromModule(mod, design)
  if (!Design) fail(`design '${design}' does not export '${cap(design)}'`, { exports: Object.keys(mod) })
  return { Design, about: mod.about || null, source: 'npm' }
}

// Normalise one option spec from getConfig() into {type, default, min?, max?}.
// Specs come in three shapes (all seen in the wild):
//   {pct: 25, min: 8, max: 40, menu: "fit"}   typed, with range
//   4.8 / false / "text"                      bare scalar default
//   ""                                        empty-string default
function normaliseOption(spec) {
  if (spec !== null && typeof spec === 'object') {
    for (const t of OPTION_TYPES) {
      if (t in spec) {
        const out = { type: t, default: spec[t] }
        if (spec.min !== undefined) out.min = spec.min
        if (spec.max !== undefined) out.max = spec.max
        return out
      }
    }
    return { type: 'raw', default: spec }
  }
  return { type: typeof spec, default: spec }
}

const cleanOp = (op) => {
  const o = { type: op.type }
  for (const k of ['from', 'to', 'cp1', 'cp2']) if (op[k]) o[k] = { x: op[k].x, y: op[k].y }
  return o
}

function parseArgs(argv) {
  const args = {}
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--design') args.design = argv[++i]
    else if (a === '--measurements') args.measurementsFile = argv[++i]
    else if (a === '--options') args.optionsFile = argv[++i]
    else if (a === '--sa') args.sa = Number(argv[++i])
    else if (a === '--out') args.out = argv[++i]
    else if (a === '--library') args.library = argv[++i]
    else if (a === '--info') args.info = argv[++i]
    else if (a === '--list-designs') args.listDesigns = true
    else fail(`unknown argument: ${a}`)
  }
  return args
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const libraryRoot = args.library || join(NODE_ROOT, 'library')

  if (args.listDesigns) {
    console.log(JSON.stringify({ designs: await listDesigns(libraryRoot) }, null, 1))
    return
  }

  if (args.info) {
    const { Design, about, source } = await loadDesign(args.info, libraryRoot)
    const cfg = new Design({ measurements: {}, options: {}, sa: 10 }).getConfig()
    const options = {}
    for (const [name, spec] of Object.entries(cfg.options || {})) options[name] = normaliseOption(spec)
    console.log(
      JSON.stringify(
        {
          design: args.info,
          version: about?.version || null,
          source,
          requiredMeasurements: cfg.measurements || [],
          optionalMeasurements: cfg.optionalMeasurements || [],
          options,
        },
        null,
        1,
      ),
    )
    return
  }

  const { design, measurementsFile, optionsFile, out } = args
  const sa = args.sa ?? 10
  if (!design || !measurementsFile || !out) {
    fail('usage: draft.mjs --design <name> --measurements <file.json> [--options <file.json>] [--sa <mm>] --out <dir> [--library <dir>]')
  }
  const measurements = JSON.parse(readFileSync(measurementsFile, 'utf8'))
  const options = optionsFile ? JSON.parse(readFileSync(optionsFile, 'utf8')) : {}

  const { Design, about, source, path } = await loadDesign(design, libraryRoot)

  // Discover what the design needs, from the design itself.
  const cfg = new Design({ measurements: {}, options: {}, sa }).getConfig()
  const required = cfg.measurements || []
  const optional = cfg.optionalMeasurements || []
  const missing = required.filter((m) => measurements[m] === undefined)
  if (missing.length) fail(`missing required measurements for '${design}'`, { required, missing })
  const unused = Object.keys(measurements).filter((m) => !required.includes(m) && !optional.includes(m))

  // Warn, don't fail, on unknown or out-of-range options: FreeSewing
  // silently accepts unknown options, so a typo would otherwise pass
  // unnoticed. Ranges come from the design's own option specs.
  const warnings = []
  for (const m of unused) warnings.push(`measurement '${m}' is not used by '${design}'`)
  for (const [name, value] of Object.entries(options)) {
    const spec = (cfg.options || {})[name]
    if (!spec) {
      warnings.push(`option '${name}' is not defined by '${design}'`)
      continue
    }
    // pct options are passed as fractions (0.08 = 8%) while the design
    // spec states min/max in percent (8 = 8%); compare in percent.
    const norm = normaliseOption(spec)
    const v = norm.type === 'pct' && typeof value === 'number' ? value * 100 : value
    if (typeof v === 'number' && norm.min !== undefined && v < norm.min) {
      warnings.push(`option '${name}'=${value} is below the design minimum ${norm.min}${norm.type === 'pct' ? '%' : ''}`)
    }
    if (typeof v === 'number' && norm.max !== undefined && v > norm.max) {
      warnings.push(`option '${name}'=${value} is above the design maximum ${norm.max}${norm.type === 'pct' ? '%' : ''}`)
    }
  }

  const settings = { measurements, options, sa }

  // Draft 1 (no theme): geometry only -> paths JSON.
  const pathsPattern = new Design(settings)
  pathsPattern.draft()
  const props = pathsPattern.getRenderProps()
  const stacks = {}
  for (const [sname, stack] of Object.entries(props.stacks)) {
    const part = stack.parts[0]
    const paths = {}
    for (const [pname, path] of Object.entries(part.paths || {})) paths[pname] = path.ops.map(cleanOp)
    // Writer contract (same as dump-json-v2): the grainline is the path
    // whose name contains "grainline" (macro paths are named like
    // __macro_grainline_grainline_line). Expose it under the plain key
    // too, so write_dxf_aama finds it; the original name stays as well.
    if (!('grainline' in paths)) {
      const gl = Object.keys(paths).find((k) => /grainline/i.test(k))
      if (gl) paths.grainline = paths[gl]
    }
    const snippets = Object.entries(part.snippets || {}).map(([name, s]) => ({
      name,
      def: s.def,
      x: s.anchor.x,
      y: s.anchor.y,
    }))
    stacks[sname] = {
      topLeft: stack.topLeft,
      paths,
      notches: snippets.filter((s) => s.def === 'notch' || s.def === 'bnotch'),
      snippets,
      title: part.points?.title ? { x: part.points.title.x, y: part.points.title.y } : null,
    }
  }

  // Draft 2 (theme): SVG.
  const svgPattern = new Design(settings)
  const svg = svgPattern.use(theme).draft().render()
  const effective = svgPattern.settings?.[0] || {}

  mkdirSync(out, { recursive: true })
  const svgPath = join(out, `${design}.svg`)
  const pathsPath = join(out, `${design}-paths.json`)
  const summaryPath = join(out, `${design}-summary.json`)
  writeFileSync(svgPath, svg)
  writeFileSync(pathsPath, JSON.stringify(stacks, null, 1))
  const summary = {
    design,
    version: about?.version || null,
    source,
    libraryPath: path || null,
    sa_mm: sa,
    measurements: effective.measurements || measurements,
    options: effective.options || options,
    requiredMeasurements: required,
    optionalMeasurements: optional,
    unusedMeasurements: unused,
    warnings,
    stacks: Object.entries(stacks).map(([name, s]) => ({
      name,
      paths: Object.keys(s.paths),
      notches: s.notches.length,
      snippets: s.snippets.length,
      title: !!s.title,
    })),
    files: { svg: svgPath, paths: pathsPath, summary: summaryPath },
  }
  writeFileSync(summaryPath, JSON.stringify(summary, null, 1))
  console.log(JSON.stringify(summary))
}

main().catch((e) => fail(e.message, { stack: e.stack }))
