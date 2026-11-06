import { ensureStoreValues } from '../shared.mjs'
import { threePartHood } from './shared.mjs'

function libraryHoodSide({
  store,
  sa,
  Point,
  points,
  Path,
  paths,
  Snippet,
  snippets,
  macro,
  part,
  options,
}) {
  /*
   * If things are missing in the store, flag a warning and return early.
   * Unless we are asked to mock these values.
   */
  if (!ensureStoreValues(threePartHood, 'mockThreePartHood', store, options)) return part

  paths.seam = new Path()
    .move(points.frontEdge)
    .curve(points.frontEdgeCp2, points.neckRollCp1, points.neckRoll)
    .curve(points.neckRollCp2, points.hoodRimCp, points.hoodRim)
    .curve(points.hoodRim, points.hoodTopCp1, points.hoodTop)
    .curve(points.hoodTopCp2, points.neckEdge, points.neckEdge)
    .curve(points.neckEdgeCp2, points.frontEdgeCp1, points.frontEdge)
    .close()
    .attr('class', 'fabric')

  if (sa) {
    // Reversing this curve sidesteps a bezierjs edge case
    paths.sa = paths.seam
      .reverse()
      .offset(sa * -1)
      .attr('class', 'fabric sa')
  }

  /*
   * Annotations
   */
  //notches
  macro('sprinkle', {
    snippet: 'notch',
    on: ['shoulderNotch', 'cfNotch'],
  })

  // Cut list
  let cuts = store.pget('cutlist', {})
  if (!Array.isArray(cuts)) cuts = [cuts]
  for (const cut of cuts) store.cutlist.addCut({ cut: 4, from: 'fabric', ...cut })

  // Title
  const title = store.pget('title', {})
  points.title = new Point(points.hoodTop.x, points.neckEdge.y / 4)
  macro('title', { at: points.title, nr: 5, title: 'hoodSide', align: 'center', ...title })

  // Logo
  points.logo = new Point(points.hoodTop.x, points.neckEdge.y * 0.666)
  snippets.logo = new Snippet('logo', points.logo)

  // Grainline
  macro('grainline', {
    from: points.shoulderNotch,
    to: points.hoodTop,
  })

  // Dimensions
  const neckSeam = new Path()
    .move(points.neckEdge)
    .curve(points.neckEdgeCp2, points.frontEdgeCp1, points.frontEdge)
    .split(points.shoulderNotch)
  const centralSeam = new Path()
    .move(points.hoodRim)
    .curve(points.hoodRim, points.hoodTopCp1, points.hoodTop)
    .curve(points.hoodTopCp2, points.neckEdge, points.neckEdge)
    .reverse()
  const openingSeam = new Path()
    .move(points.neckRoll)
    .curve(points.neckRollCp2, points.hoodRimCp, points.hoodRim)

  macro('pd', {
    id: 'lNeckToNotch',
    path: neckSeam[0],
    d: sa + 15,
  })
  macro('pd', {
    id: 'lNotchToNeck',
    path: neckSeam[1],
    d: sa + 15,
  })
  macro('pd', {
    id: 'lHood',
    path: centralSeam,
    d: sa * -1 - 15,
  })
  macro('hd', {
    id: 'wAtNeck',
    from: points.neckEdge,
    to: points.frontEdge,
    y: points.frontEdge.y + sa + 30,
  })
  macro('hd', {
    id: 'wFull',
    from: centralSeam.edge('left'),
    to: points.frontEdge,
    y: points.frontEdge.y + sa + 45,
  })
  const openingEdge = openingSeam.edge('left')
  macro('hd', {
    id: 'wOpeningToTip',
    from: openingEdge,
    to: points.frontEdge,
    y: openingEdge.y,
  })
  macro('vd', {
    id: 'hTipToOpeningTip',
    from: points.frontEdge,
    to: points.hoodRim,
    x: points.hoodRim.x + sa + 15,
  })
  macro('vd', {
    id: 'hFull',
    from: points.frontEdge,
    to: points.hoodTop,
    x: points.hoodRim.x + sa + 30,
  })

  return part
}

export const hoodSide = {
  library: true,
  name: 'library.hoodSide',
  from: threePartHood,
  options: {
    mockThreePartHood: false,
  },
  store: {
    reads: ['cutlist', 'title'],
  },
  draft: libraryHoodSide,
}
