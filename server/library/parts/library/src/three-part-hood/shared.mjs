import { ensureStoreValues } from '../shared.mjs'

function draftThreePartHood({ store, Point, points, Path, paths, measurements, part, options }) {
  /*
   * If things are missing in the store, flag a warning and return early.
   * Unless we are asked to mock these values.
   */
  if (!ensureStoreValues(threePartHood, 'mockThreePartHood', store, options)) return part

  const neckFront = store.pget('neckOpeningLenFront', 150)
  const neckBack = store.pget('neckOpeningLenBack', 110)
  let neckOpening = neckFront + neckBack
  let hoodOpening = measurements.head
  let neckCutoutDelta = store.pget('neckCutoutFront', 80) - store.pget('neckCutoutBack', 10)
  store.pset('hoodCenterWidth', measurements.head / 10)
  let halfCenterPanel = store.pget('hoodCenterWidth') / 2
  points.topLeft = new Point(0, 0)
  points.topRight = new Point(neckOpening, 0)
  points.neckRight = new Point(neckOpening, (hoodOpening - halfCenterPanel) / 2)
  points.neckLeft = new Point(0, points.neckRight.y)
  points.frontLeft = points.neckLeft.shift(-90, neckCutoutDelta)
  points.frontEdge = points.neckRight.shift(-90, neckCutoutDelta)
  points.neckEdge = points.neckLeft.shift(0, halfCenterPanel)
  points.neckEdgeCp2 = new Point(points.neckRight.x / 2, points.neckEdge.y)
  points.frontEdgeCp1 = new Point(points.neckEdgeCp2.x, points.frontEdge.y)
  points.shoulderNotch = new Path()
    .move(points.neckEdge)
    .curve(points.neckEdgeCp2, points.frontEdgeCp1, points.frontEdge)
    .shiftAlong(neckBack - halfCenterPanel)
  points.hoodTop = new Point(points.shoulderNotch.x, points.topLeft.y)
  points.hoodTopCp2 = points.hoodTop.shift(180, points.neckEdge.y * 0.7)
  points.hoodRim = new Point(points.frontEdge.x, points.neckRight.y * 0.2)
  points.hoodTopCp1 = points.hoodTop.shift(0, points.hoodTop.dx(points.hoodRim) / 2)
  points.frontEdgeCp2 = points.frontEdge.shift(90, halfCenterPanel)
  points._tmp1 = new Path()
    .move(points.hoodRim)
    .curve(points.hoodRim, points.hoodTopCp1, points.hoodTop)
    .shiftAlong(2)
    .rotate(90, points.hoodRim)
  points.hoodRimCp = points.hoodRim.shiftTowards(points._tmp1, points.neckRight.y / 3)
  points.neckRoll = points.neckRight.shift(180, halfCenterPanel)
  points._tmp2 = new Path()
    .move(points.neckRoll)
    .curve(points.neckRoll, points.hoodRimCp, points.hoodRim)
    .shiftAlong(2)
  points.neckRollCp2 = points.neckRoll.shiftTowards(points._tmp2, halfCenterPanel)
  points.neckRollCp1 = points.neckRollCp2.rotate(180, points.neckRoll)

  points.cfNotch = new Path()
    .move(points.neckEdge)
    .curve(points.neckEdgeCp2, points.frontEdgeCp1, points.frontEdge)
    .shiftAlong(neckOpening - halfCenterPanel)

  // Store length of center seam
  paths.hoodCenter = new Path()
    .move(points.hoodRim)
    .curve(points.hoodRim, points.hoodTopCp1, points.hoodTop)
    .curve(points.hoodTopCp2, points.neckEdge, points.neckEdge)
    .hide()

  // Store length of center seam
  store.set('hoodCenterLength', paths.hoodCenter.length())

  return part
}

export const threePartHood = {
  library: true,
  name: 'library.threePartHood',
  measurements: ['head'],
  hide: { self: true },
  options: {
    mockThreePartHood: false,
  },
  store: {
    reads: [
      'neckOpeningLenFront',
      'neckOpeningLenBack',
      'neckCutoutFront',
      'neckCutoutBack',
      'cutlist',
      'title',
    ],
    writes: ['hoodCenterWidth', 'hoodCenterLength'],
  },
  draft: draftThreePartHood,
}
