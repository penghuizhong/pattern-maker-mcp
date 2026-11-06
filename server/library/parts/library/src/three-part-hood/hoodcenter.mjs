import { threePartHood } from './shared.mjs'
import { ensureStoreValues } from '../shared.mjs'

function libraryHoodCenter({
  store,
  sa,
  Point,
  points,
  Path,
  paths,
  expand,
  macro,
  units,
  part,
  options,
  measurements,
}) {
  /*
   * If things are missing in the store, flag a warning and return early.
   * Unless we are asked to mock these values.
   */
  if (!ensureStoreValues(threePartHood, 'mockThreePartHood', store, options)) return part

  const width = measurements.head / 10
  const length = paths.hoodCenter.length()

  if (expand) {
    store.flag.preset('expandIsOn')
  } else {
    // Expand is off, do not draw the part but flag this to the user
    const extraSa = sa ? 2 * sa : 0
    store.flag.note({
      msg: `library:cutHoodCenter`,
      notes: [sa ? 'flag:saIncluded' : 'flag:saExcluded', 'flag:partHiddenByExpand'],
      replace: {
        width: units(width + extraSa),
        length: units(length + extraSa),
        nr: store.pget('title', {})?.nr ?? 6,
      },
      suggest: {
        text: 'flag:show',
        icon: 'expand',
        update: {
          settings: ['expand', 1],
        },
      },
    })
    // Also hint about expand
    store.flag.preset('expandIsOff')

    return part.hide()
  }

  points.topLeft = new Point(0, 0)
  points.bottomLeft = new Point(0, width)
  points.topRight = new Point(length, 0)
  points.bottomRight = new Point(length, width)

  paths.seam = new Path()
    .move(points.topLeft)
    .line(points.bottomLeft)
    .line(points.bottomRight)
    .line(points.topRight)
    .line(points.topLeft)
    .close()
    .attr('class', 'fabric')

  if (sa) paths.sa = paths.seam.offset(sa).addClass('fabric sa')

  // Cut list
  let cuts = store.pget('cutlist', {})
  if (!Array.isArray(cuts)) cuts = [cuts]
  for (const cut of cuts) store.cutlist.addCut({ cut: 2, from: 'fabric', ...cut })

  // Title
  const title = store.pget('title', {})
  points.title = points.bottomLeft.shiftFractionTowards(points.topRight, 0.5)
  macro('title', { at: points.title, nr: 6, title: 'hoodCenter', ...title })

  // Grainline
  macro('grainline', {
    from: points.topLeft.shift(-90, width / 2),
    to: points.topRight.shift(-90, width / 2),
  })

  // Dimensions
  macro('hd', {
    id: 'wFull',
    from: points.bottomLeft,
    to: points.bottomRight,
    y: points.bottomRight.y + sa + 15,
  })
  macro('vd', {
    id: 'hFull',
    from: points.bottomRight,
    to: points.topRight,
    x: points.topRight.x + sa + 15,
  })

  return part
}

export const hoodCenter = {
  library: true,
  name: 'library.hoodCenter',
  from: threePartHood,
  options: {
    mockThreePartHood: false,
  },
  store: {
    reads: ['cutlist', 'title'],
  },
  draft: libraryHoodCenter,
}
