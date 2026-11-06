import { ensureStoreValues } from '../shared.mjs'
import { pctBasedOn } from '@freesewing/core'

function draftTwoPartSleeve({ Path, paths, points, store, options, part }) {
  function draftSleeve(part, tweak) {
    let { Point, Path, points, store, options, measurements, utils } = part.shorthand()
    /*
     * The bicepsEase option comes from the block. If it is not set, we default to 0.15
     */
    // Sleeve frame
    points.top = new Point(0, 0)
    const easedQuarterBiceps = (measurements.biceps / 4) * (1 + (options.bicepsEase || 0.15))
    points.boxTopRight = points.top.shift(0, easedQuarterBiceps * tweak)
    points.boxTopLeft = points.boxTopRight.flipX()
    points.boxBottom = points.top.shift(
      -90,
      measurements.shoulderToWrist * (1 + options.sleeveLengthBonus)
    )
    points.boxBottomRight = points.boxBottom.shift(0, points.boxTopRight.x)
    points.boxBottomLeft = points.boxBottomRight.flipX()
    points.armCenter = points.top.shift(
      -90,
      measurements.biceps * (1 + (options.bicepsEase || 0.15)) * options.sleevecapHeight * tweak
    )
    points.armRight = points.armCenter.shift(0, points.boxTopRight.x)
    points.armLeft = points.armRight.flipX()
    points.elbowCenter = points.top.shift(-90, measurements.shoulderToElbow)
    points.elbowRight = points.elbowCenter.shift(0, points.boxTopRight.x)
    points.elbowLeft = points.elbowRight.flipX()

    // Using sleeve width to adapt other values
    let factor = points.boxTopRight.x

    // Note: us = undersleeve, ts = topsleeve
    points.backPitchPoint = new Point(factor, points.armCenter.y / 3)
    points.usTip = points.backPitchPoint.shift(180, factor / 4)
    points.tsLeftEdge = points.armLeft.shift(180, factor / 4)
    points.usLeftEdge = points.armLeft.shift(0, factor / 4)
    points.tsRightEdge = points.armRight.shift(0, factor / 9)
    points.usRightEdge = points.armRight.shift(180, factor / 9)
    points.frontPitchPoint = new Point(points.boxTopLeft.x, points.armCenter.y * 0.6)
    points.tsElbowLeft = points.elbowLeft.shift(180, factor / 9)
    points.usElbowLeft = points.elbowLeft.shift(0, factor / 2.4)

    // Different approach to sleeve bend, wrist right first
    points.tsWristRight = utils.beamsIntersect(
      points.elbowRight,
      points.boxBottomRight.rotate(options.sleeveBend * -1, points.elbowRight),
      points.boxBottomLeft,
      points.boxBottomRight
    )
    points.usWristRight = points.tsWristRight.clone()

    // Shift wrist left to the exact wrist width
    let wristWidth = measurements.wrist * (1 + options.cuffEase)
    let topWrist = wristWidth / 2 + factor / 5
    let underWrist = wristWidth / 2 - factor / 5
    points.tsWristLeftHelperBottom = points.tsWristRight.shift(180, topWrist / 2)
    points.usWristLeftHelperBottom = points.usWristRight.shift(180, underWrist / 2)
    points.tsWristLeftHelperTop = points.tsElbowLeft.shiftFractionTowards(points.elbowRight, 0.5)
    points.usWristLeftHelperTop = points.usElbowLeft.shiftFractionTowards(points.elbowRight, 0.5)
    let tsWristAngle = points.tsWristLeftHelperBottom.angle(points.tsWristLeftHelperTop)
    let usWristAngle = points.usWristLeftHelperBottom.angle(points.usWristLeftHelperTop)
    points.tsWristLeft = points.tsWristRight.shift(tsWristAngle - 90, topWrist * -1)
    points.usWristLeft = points.usWristRight.shift(usWristAngle - 90, underWrist * -1)

    // Control points ts
    points.tsRightEdgeCpTop = points.tsRightEdge.shift(
      90,
      points.backPitchPoint.dy(points.tsRightEdge) / 2
    )
    points.tsRightEdgeCpBottom = points.tsRightEdgeCpTop.flipY(points.tsRightEdge)
    points.elbowRightCpTop = points.tsWristRight.shiftFractionTowards(points.elbowRight, 1.15)
    points.topCpRight = points.top.shift(0, factor / 1.6)
    points.topCpLeft = points.topCpRight.flipX()
    points.tsLeftEdgeCpRight = points.tsLeftEdge.shift(
      0,
      points.tsLeftEdge.dist(points.armLeft) / 2
    )
    points.frontPitchPointCpBottom = points.frontPitchPoint.shiftFractionTowards(
      points.tsLeftEdgeCpRight,
      0.666
    )
    points.frontPitchPointCpTop = points.frontPitchPointCpBottom.rotate(180, points.frontPitchPoint)
    points.tsElbowLeftCpTop = points.tsWristLeft.shiftFractionTowards(points.tsElbowLeft, 1.2)

    // Control points us
    points.usRightEdgeCpBottom = points.usRightEdge.shift(
      points.usTip.angle(points.elbowRight),
      points.usTip.dy(points.usRightEdge) / 2
    )
    points.usRightEdgeCpTop = points.usRightEdgeCpBottom.rotate(180, points.usRightEdge)
    points._helper1 = new Path()
      .move(points.backPitchPoint)
      ._curve(points.topCpRight, points.top)
      .shiftAlong(5)
    points._helper2 = new Path()
      .move(points.backPitchPoint)
      ._curve(points.tsRightEdgeCpTop, points.tsRightEdge)
      .shiftAlong(5)
    points.usLeftEdgeRight = points.usLeftEdge.shift(
      0,
      points.usLeftEdge.dist(points.armCenter) / 3
    )
    points.usLeftEdgeCpRight = points.usLeftEdge.shift(
      0,
      points.usLeftEdge.dist(points.armCenter) / 1.2
    )

    // Angle of the usTip
    let angle =
      points._helper1.angle(points.backPitchPoint) - points.backPitchPoint.angle(points._helper2)
    points.usTipCpBottom = points.usRightEdgeCpTop.rotate(angle * -1, points.usTip)
    points.usElbowLeftCpTop = points.usWristLeft.shiftFractionTowards(points.usElbowLeft, 1.2)

    // Calculate length of the sleevecap seam
    let lenTop = new Path()
      .move(points.backPitchPoint)
      .curve(points.backPitchPoint, points.topCpRight, points.top)
      .curve(points.topCpLeft, points.frontPitchPointCpTop, points.frontPitchPoint)
      .curve(points.frontPitchPointCpBottom, points.tsLeftEdgeCpRight, points.tsLeftEdge)
      .length()
    let lenUnder = new Path()
      .move(points.usTip)
      .curve(points.usTipCpBottom, points.usLeftEdgeCpRight, points.usLeftEdgeRight)
      .line(points.usLeftEdge)
      .length()
    store.pset('sleevecapLength', lenTop + lenUnder)
  }

  /*
   * If things are missing in the store, flag a warning and return early.
   * Unless we are asked to mock these values.
   */
  if (!ensureStoreValues(twoPartSleeve, 'mockTwoPartSleeve', store, options)) return part

  let armholeLength = store.pget('frontArmholeLength', 200) + store.pget('backArmholeLength', 200)
  let sleevecapEase = armholeLength * options.sleevecapEase
  store.pset('sleevecapEase', sleevecapEase)
  store.pset('sleevecapTarget', armholeLength + sleevecapEase)

  let delta = 0
  let runs = 0
  let tweak = 1
  let target = store.pget('sleevecapTarget')
  do {
    draftSleeve(part, tweak)
    runs++
    delta = store.pget('sleevecapLength') - target
    if (delta > 0) tweak = tweak * 0.99
    else tweak = tweak * 1.02
  } while (Math.abs(delta) > 2 && runs < 50)

  // Paths
  paths.ts = new Path()
    .move(points.tsWristRight)
    .line(points.elbowRight)
    .curve(points.elbowRightCpTop, points.tsRightEdgeCpBottom, points.tsRightEdge)
    .curve_(points.tsRightEdgeCpTop, points.backPitchPoint)
    .curve(points.backPitchPoint, points.topCpRight, points.top)
    .curve(points.topCpLeft, points.frontPitchPointCpTop, points.frontPitchPoint)
    .curve(points.frontPitchPointCpBottom, points.tsLeftEdgeCpRight, points.tsLeftEdge)
    .curve(points.tsLeftEdge, points.tsElbowLeftCpTop, points.tsElbowLeft)
    .line(points.tsWristLeft)
    .line(points.tsWristRight)
    .close()
    .hide()

  paths.us = new Path()
    .move(points.usWristRight)
    .line(points.elbowRight)
    .curve(points.elbowRightCpTop, points.usRightEdgeCpBottom, points.usRightEdge)
    .curve_(points.usRightEdgeCpTop, points.usTip)
    .curve(points.usTipCpBottom, points.usLeftEdgeCpRight, points.usLeftEdgeRight)
    .line(points.usLeftEdge)
    .curve(points.usLeftEdge, points.usElbowLeftCpTop, points.usElbowLeft)
    .line(points.usWristLeft)
    .line(points.usWristRight)
    .close()
    .hide()

  return part
}

export const twoPartSleeve = {
  name: 'library.twoPartSleeve',
  hide: { self: true },
  measurements: ['shoulderToElbow', 'shoulderToWrist', 'wrist'],
  options: {
    mockTwoPartSleeve: false, // Can be set via a flag/suggest, not via UI
    // Fit
    cuffEase: { pct: 40, min: 2, max: 100, ...pctBasedOn('wrist'), menu: 'fit' },
    sleeveLengthBonus: { pct: 0, min: -20, max: 15, menu: 'fit' },
    sleeveBend: { deg: 10, min: 0, max: 20, menu: 'fit' },
    sleevecapHeight: { pct: 45, min: 40, max: 60, menu: 'advanced' },
    sleevecapEase: { pct: 1, min: 0, max: 10, menu: 'advanced' },
  },
  draft: draftTwoPartSleeve,
  store: {
    reads: ['frontArmholeLength', 'backArmholeLength', 'cutlist', 'title'],
    writes: ['sleevecapLength', 'sleevecapTarget'],
  },
}

export function dimensions(part, s) {
  let { macro, points, sa } = part.shorthand()

  macro('ld', {
    id: 'wAtCuff',
    from: points[s + 'WristLeft'],
    to: points[s + 'WristRight'],
    d: 15,
  })
  macro('ld', {
    id: 'wAtElbow',
    from: points[s + 'ElbowLeft'],
    to: points.elbowRight,
  })
  macro('ld', {
    id: 'wAtArmhole',
    from: points[s + 'LeftEdge'],
    to: points[s + 'RightEdge'],
  })
  macro('hd', {
    id: 'wArmholeInnerToElbowInner',
    from: points[s + 'LeftEdge'],
    to: points[s + 'ElbowLeft'],
    y: points[s + 'WristRight'].y + 3 * sa + 15,
  })
  macro('hd', {
    id: 'wArmholeInnerToCuffInner',
    from: points[s + 'LeftEdge'],
    to: points[s + 'WristLeft'],
    y: points[s + 'WristRight'].y + 3 * sa + 30,
  })
  macro('hd', {
    id: 'wCuffHorizontal',
    from: points[s + 'LeftEdge'],
    to: points[s + 'WristRight'],
    y: points[s + 'WristRight'].y + 3 * sa + 45,
  })
  macro('hd', {
    id: 'wCuffInnerToElbow',
    from: points[s + 'LeftEdge'],
    to: points.elbowRight,
    y: points[s + 'WristRight'].y + 3 * sa + 60,
  })
  macro('vd', {
    id: 'hElbowToArmholeInner',
    from: points[s + 'ElbowLeft'],
    to: points[s + 'LeftEdge'],
    x: points[s + 'LeftEdge'].x - sa - 15,
  })
  macro('vd', {
    id: 'hCuffInnerToArmholeInner',
    from: points[s + 'WristLeft'],
    to: points[s + 'LeftEdge'],
    x: points[s + 'LeftEdge'].x - sa - 30,
  })
  macro('vd', {
    id: 'hCuffOuterToArmholeInner',
    from: points[s + 'WristRight'],
    to: points[s + 'LeftEdge'],
    x: points[s + 'LeftEdge'].x - sa - 45,
  })
}
