#!/usr/bin/env node
// Regenerates the engine/library data files from the framework + library.
// Run from server/:  node engine/data/generate.mjs
//
// Outputs (checked in -- they are the project's data, not build artefacts):
//   engine/data/measurements.json   canonical measurements (@freesewing/config)
//   engine/data/settings.json       core pattern settings defaults (probed
//                                   from a design instance; sa default 10
//                                   is this project's runner convention)
//   library/data/models.json        standard measurement sets (@freesewing/models)
//   library/data/schemas/<design>.json
//                                   per-design requirements (draft.mjs --info)
//
// Re-run after upgrading the framework or adding a design to the library.
import { execFileSync } from 'node:child_process'
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { measurements, topToBottomMeasurements, degreeMeasurements } from '@freesewing/config'
import * as models from '@freesewing/models'
import { readFileSync } from 'node:fs'

const HERE = dirname(fileURLToPath(import.meta.url))
const SERVER = join(HERE, '..', '..')
const RUNNER = join(SERVER, 'engine', 'runner', 'draft.mjs')
const ENGINE_DATA = join(SERVER, 'engine', 'data')
const LIBRARY_DATA = join(SERVER, 'library', 'data')

const pkgVersion = (name) =>
  JSON.parse(readFileSync(join(SERVER, 'node_modules', '@freesewing', name, 'package.json'), 'utf8')).version

const write = (path, obj) => {
  writeFileSync(path, JSON.stringify(obj, null, 1) + '\n')
  console.log('wrote', path)
}

// 1. Canonical measurements (all in mm except degreeMeasurements, degrees)
write(join(ENGINE_DATA, 'measurements.json'), {
  source: `@freesewing/config ${pkgVersion('config')}`,
  units: 'mm (degreeMeasurements are in degrees)',
  measurements,
  topToBottomMeasurements,
  degreeMeasurements,
})

// 2. Design list (library + npm) from the runner
const designs = JSON.parse(execFileSync('node', [RUNNER, '--list-designs'], { encoding: 'utf8' })).designs
if (!designs.length) throw new Error('no designs found -- is the library built?')

// 3. Core pattern settings defaults, probed from the first design
const first = designs[0]
const mod = await import(pathToFileURL(first.path || join(SERVER, 'node_modules', '@freesewing', first.design, 'src', 'index.mjs')).href)
const Design = mod[first.design[0].toUpperCase() + first.design.slice(1)]
const probe = new Design({ measurements: {}, options: {}, sa: 10 })
const { measurements: _m, options: _o, absoluteOptions: _a, ...rest } = probe.settings[0]
write(join(ENGINE_DATA, 'settings.json'), {
  source: `@freesewing/core ${pkgVersion('core')} (pattern defaults, probed from ${first.design})`,
  sa_mm_default: 10,
  note: 'sa is the seam allowance in mm; the runner defaults it to 10. settings below are the core defaults.',
  settings: rest,
})

// 4. Standard measurement sets (every export that is a plain object of numbers)
const sets = {}
for (const [k, v] of Object.entries(models)) {
  if (v && typeof v === 'object' && !Array.isArray(v) && Object.values(v).every((x) => typeof x === 'number')) {
    sets[k] = v
  }
}
write(join(LIBRARY_DATA, 'models.json'), {
  source: `@freesewing/models ${pkgVersion('models')} (neckstimate: every set is generated from neck circumference)`,
  groups: models.groups,
  sizes: models.sizes,
  sets,
})

// 5. Per-design schemas via the runner's --info (the same source the tool uses)
mkdirSync(join(LIBRARY_DATA, 'schemas'), { recursive: true })
for (const d of designs) {
  const info = execFileSync('node', [RUNNER, '--info', d.design], { encoding: 'utf8' })
  write(join(LIBRARY_DATA, 'schemas', `${d.design}.json`), JSON.parse(info))
}

console.log(`done: ${designs.length} designs (${designs.map((d) => d.design).join(', ')}), ${Object.keys(sets).length} measurement sets`)
