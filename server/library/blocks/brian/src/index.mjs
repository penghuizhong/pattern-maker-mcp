// Vendored from FreeSewing 4.10.2 (MIT, © Joost De Cock) — see ../../NOTICE.md.
// Intra-library import rewritten to a relative path; framework imports
// (@freesewing/core, @freesewing/plugin-*) still resolve from node_modules.
import { Design, mergeI18n } from '@freesewing/core'
import { i18n as brianI18n } from '../i18n/index.mjs'
import about from '../about.json' with { type: 'json' }
import { sleeve, sleeveI18n } from '../../../parts/library/src/index.mjs'
import { back } from './back.mjs'
import { front } from './front.mjs'
// Re-export skeleton parts so peope can re-use them
import { base } from './base.mjs'

// Setup our new design
const Brian = new Design({
  data: about,
  parts: [back, front, sleeve],
})

// Merge translations
const i18n = mergeI18n([sleeveI18n, brianI18n])

// Named exports
export { back, front, base, Brian, i18n, about }
