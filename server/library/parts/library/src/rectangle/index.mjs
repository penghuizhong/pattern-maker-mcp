import { ensureStoreValues } from '../shared.mjs'

export const rectangle = {
  library: true,
  name: 'library.rectangle',
  measurements: [],
  options: {
    mockRectangle: false, // Can be set via a flag/suggest, not via UI
    noSa: false,
    seamClasses: 'fabric',
    rectangleWidth: { pct: 100, min: 50, max: 150, menu: 'rectangle' },
    rectangleHeight: { pct: 100, min: 50, max: 150, menu: 'rectangle' },
  },
  store: {
    reads: ['width', 'height', 'cutlist', 'title'],
  },
  draft: ({
    store,
    sa,
    macro,
    snippets,
    Snippet,
    units,
    options,
    Point,
    points,
    Path,
    paths,
    log,
    measurements,
    part,
  }) => {
    /*
     * If things are missing in the store, flag a warning and return early.
     * Unless we are asked to mock these values.
     */
    if (!ensureStoreValues(rectangle, 'mockRectangle', store, options)) return part

    // Points
    points.topLeft = new Point(0, 0)
    points.topRight = new Point(store.pget('width', 100) * options.rectangleWidth, 0)
    points.bottomRight = new Point(
      points.topRight.x,
      store.pget('height', 100) * options.rectangleHeight
    )
    points.bottomLeft = new Point(0, points.bottomRight.y)

    // Paths
    paths.seam = new Path()
      .move(points.topLeft)
      .line(points.bottomLeft)
      .line(points.bottomRight)
      .line(points.topRight)
      .line(points.topLeft)
      .close()
      .addClass(options.seamClasses)

    if (sa && !options.noSa) paths.sa = paths.seam.offset(sa).attr('class', 'fabric sa')

    /*
     * Annotations
     */

    // Anchor point for sampling
    points.gridAnchor = new Point(0, 0)

    // Grainline
    macro('grainline', {
      from: points.bottomLeft.shift(0, points.bottomRight.x / 4),
      to: points.topLeft.shift(0, points.bottomRight.x / 4),
    })

    // Cut list
    let cuts = store.pget('cutlist', {})
    if (!Array.isArray(cuts)) cuts = [cuts]
    for (const cut of cuts) store.cutlist.addCut({ cut: 1, from: 'fabric', ...cut })

    // Logo
    points.logo = new Point(points.topRight.x / 2, points.bottomRight.y / 2)
    snippets.logo = new Snippet('logo', points.logo).scale(75 / points.bottomRight.x)

    // Title
    const title = store.pget('title', {})
    points.title = new Point(points.topRight.x / 4, points.bottomRight.y / 1.5)
    macro('title', { at: points.title, nr: 1, title: 'rectangle', scale: 0.5, ...title })

    // Dimensions
    macro('hd', {
      id: 'width',
      from: points.bottomLeft,
      to: points.bottomRight,
      y: points.bottomLeft.y + sa + 15,
    })
    macro('vd', {
      id: 'height',
      from: points.bottomRight,
      to: points.topRight,
      x: points.bottomRight.x + sa + 15,
    })

    return part
  },
}
