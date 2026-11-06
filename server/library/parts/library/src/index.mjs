import { Design } from '@freesewing/core'
import about from '../about.json' with { type: 'json' }
import { i18n } from '../i18n/index.mjs'
import { i18n as rectangleI18n } from '../i18n/rectangle/index.mjs'
import { i18n as sleeveI18n } from '../i18n/sleeve/index.mjs'
import { i18n as twoPartSleeveI18n } from '../i18n/two-part-sleeve/index.mjs'
import { i18n as threePartHoodI18n } from '../i18n/three-part-hood/index.mjs'

// Parts
import { rectangle } from './rectangle/index.mjs'
import { sleeve } from './sleeve/index.mjs'
import { topsleeve, undersleeve, twoPartSleeve } from './two-part-sleeve/index.mjs'
import { threePartHood, hoodCenter, hoodSide } from './three-part-hood/index.mjs'

// Setup our new design
const Library = new Design({
  data: about,
  parts: [
    rectangle,
    sleeve,
    topsleeve,
    undersleeve,
    twoPartSleeve,
    threePartHood,
    hoodCenter,
    hoodSide,
  ],
})

// Named exports
export {
  rectangle,
  sleeve,
  topsleeve,
  undersleeve,
  twoPartSleeve,
  threePartHood,
  hoodCenter,
  hoodSide,
  Library,
  i18n,
  rectangleI18n,
  sleeveI18n,
  twoPartSleeveI18n,
  threePartHoodI18n,
  about,
}

const _ = {
  needs: {
    backArmholeLength: 'Length of the armhole for the back part',
    frontArmholeLength: 'Length of the armhole for the front part',
    backArmholeToArmholePitch:
      'Length from the back start of the sleevecap to the armhole pitch point (used for notch placement).',
    frontArmholeToArmholePitch:
      'Length from the front start of the sleevecap to the armhole pitch point (used for notch placement).',
  },
  sets: {
    sleevecapLength: 'Length of the sleevecap',
    sleevecapHeight: 'Height of the sleevecap',
    sleeveLength: 'Total length of the sleeve',
    sleevecapEase: 'Sleevecap ease as an absolute value',
    sleevecapTarget: 'The theoretical sleevecap length we want',
  },
}
