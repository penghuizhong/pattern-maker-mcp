import { ensureStoreValues } from '../shared.mjs'
import { twoPartSleeve, dimensions } from './shared.mjs'

function draftTopsleeve({
  macro,
  Path,
  Point,
  points,
  paths,
  snippets,
  Snippet,
  options,
  sa,
  store,
  part,
}) {
  /*
   * If things are missing in the store, flag a warning and return early.
   * Unless we are asked to mock these values.
   */
  if (!ensureStoreValues(twoPartSleeve, 'mockTwoPartSleeve', store, options)) return part

  // Extract seamline from sleeve
  delete paths.us
  paths.seam = paths.ts.clone().unhide().setClass('fabric')
  delete paths.ts

  // Seam allowance
  if (sa) {
    paths.sa = paths.seam.clone()
    // Remove hem
    paths.sa.ops.splice(-2)
    paths.sa = paths.sa
      .offset(sa)
      .join(
        new Path()
          .move(points.tsWristLeft)
          .line(points.tsWristRight)
          .offset(sa * 3)
      )
      .close()
      .addClass('fabric sa')
  }

  /*
   * Annotations
   */
  // Cut list
  let cuts = store.pget('cutlist', {})
  if (!Array.isArray(cuts)) cuts = [cuts]
  for (const cut of cuts) store.cutlist.addCut({ cut: 2, from: 'fabric', ...cut })

  // Logo
  snippets.logo = new Snippet('logo', points.elbowCenter.shift(90, 50))

  // Title
  const title = store.pget('title', {})
  macro('title', { at: points.armCenter, nr: 3, title: 'topsleeve', ...title })

  // Grainline
  macro('grainline', {
    from: new Point(points.top.x, points.tsWristLeft.y),
    to: points.top,
  })

  // Dimensions
  dimensions(part, 'ts')
  macro('vd', {
    id: 'hSleeveCap',
    from: points.tsLeftEdge,
    to: points.top,
    x: points.tsLeftEdge.x - sa - 15,
  })
  macro('hd', {
    id: 'wArmholeInnerToSleevecapTop',
    from: points.tsLeftEdge,
    to: points.top,
    y: points.top.x - sa - 15,
  })
  macro('hd', {
    id: 'wArmholeInnerToSleevecapEnd',
    from: points.tsLeftEdge,
    to: points.backPitchPoint,
    y: points.top.x - sa - 30,
  })
  macro('hd', {
    id: 'wSleeveHead',
    from: points.tsLeftEdge,
    to: points.tsRightEdge,
    y: points.top.x - sa - 45,
  })
  macro('vd', {
    id: 'hArmholeInnerToSleeveCapEnd',
    from: points.tsRightEdge,
    to: points.backPitchPoint,
    x: points.tsRightEdge.x + sa + 15,
  })

  return part
}

export const topsleeve = {
  name: 'library.topsleeve',
  from: twoPartSleeve,
  draft: draftTopsleeve,
  options: twoPartSleeve.options,
}
