import { ensureStoreValues } from '../shared.mjs'

/** Calculates the differece between actual and optimal sleevecap length
 * Positive values mean sleevecap is longer than armhole
 */
function sleevecapDelta(store) {
  return store.pget('sleevecapLength') - store.pget('sleevecapTarget')
}

function sleevecapAdjust(store) {
  const delta = sleevecapDelta(store)
  const len = store.pget('sleevecapLength')
  const doverl = delta / len
  let factor = store.pget('__sleevecapFactor')
  if (doverl > 0.1) factor = factor * 0.8
  if (doverl > 0.02) factor = factor * 0.9
  else if (doverl < -0.1) factor = factor * 1.3
  else if (doverl < -0.02) factor = factor * 1.15
  else if (delta > 0) factor = factor * 0.99
  else factor = factor * 1.008
  store.pset('__sleevecapFactor', factor)
}

function draftSleevecap(part, run) {
  let { store, measurements, options, Point, points, Path, paths } = part.shorthand()
  // Sleeve center axis
  points.centerBiceps = new Point(0, 0)
  /*
   * We used to do this based on armholeDepthFactor,
   * but that is now legacy so instead we use measurements
   */
  if (options.legacyArmholeDepth) {
    points.centerCap = points.centerBiceps.shift(
      90,
      options.sleevecapTopFactorY *
        (measurements.biceps *
          (1 + (options.bicepsEase || 0.15)) * // Option from block, defaults to 0.15 if not set
          options.armholeDepthFactor *
          store.pget('__sleevecapFactor'))
    )
  } else {
    points.centerCap = points.centerBiceps.shift(
      90,
      options.sleevecapTopFactorY *
        (measurements.hpsToWaistBack - measurements.waistToArmpit) *
        /*
         * We are multiplying by 0.75 here to allow
         * the armholeDept option to remain similar values
         * after fixing #651
         * Note that options.armholdeDepth is not set in this library part
         * but typically set in blocks like Brian. So if it is not present
         * we just use zero.
         */
        (1 + (options.armholeDepth || 0)) *
        0.75 *
        store.pget('__sleevecapFactor')
    )
  }

  // Left and right biceps points, limit impact of sleevecapFactor to 25%
  // Note that options.bicepsEase is from a block, we default to 0.15 if it is not set
  let halfWidth = (measurements.biceps * (1 + (options.bicepsEase || 0.15))) / 2
  points.bicepsLeft = points.centerBiceps.shift(
    180,
    halfWidth * options.sleeveWidthGuarantee +
      halfWidth * (1 - options.sleeveWidthGuarantee) * store.pget('__sleevecapFactor')
  )
  points.bicepsRight = points.bicepsLeft.flipX(points.centerBiceps)

  // Adapt sleeve center axis
  points.capLeft = new Point(points.bicepsLeft.x, points.centerCap.y)
  points.capRight = points.capLeft.flipX()
  points.centerCap = points.capLeft.shiftFractionTowards(
    points.capRight,
    options.sleevecapTopFactorX
  )

  // Pitch points
  let width = points.bicepsRight.x
  let height = points.centerCap.y
  points.backPitch = new Point(
    -1 * width * options.sleevecapBackFactorX,
    height * options.sleevecapBackFactorY
  )
  points.frontPitch = new Point(
    width * options.sleevecapFrontFactorX,
    height * options.sleevecapFrontFactorY
  )

  // 4 sleevecap quadrants
  // Base points
  points.capQ1Base = points.frontPitch.shiftFractionTowards(points.bicepsRight, 0.5)
  points.capQ2Base = points.frontPitch.shiftFractionTowards(points.centerCap, 0.5)
  points.capQ3Base = points.backPitch.shiftFractionTowards(points.centerCap, 0.5)
  points.capQ4Base = points.backPitch.shiftFractionTowards(points.bicepsLeft, 0.5)
  // Offset points
  let baseOffset = measurements.biceps * (1 + (options.bicepsEase || 0.15))
  points.capQ1 = points.capQ1Base.shift(
    points.bicepsRight.angle(points.frontPitch) + 90,
    baseOffset * options.sleevecapQ1Offset
  )
  points.capQ2 = points.capQ2Base.shift(
    points.centerCap.angle(points.frontPitch) + 90,
    baseOffset * options.sleevecapQ2Offset
  )
  points.capQ3 = points.capQ3Base.shift(
    points.centerCap.angle(points.backPitch) - 90,
    baseOffset * options.sleevecapQ3Offset
  )
  points.capQ4 = points.capQ4Base.shift(
    points.bicepsLeft.angle(points.backPitch) - 90,
    baseOffset * options.sleevecapQ4Offset
  )
  // Control points
  points.capQ1Cp1 = points.capQ1.shift(
    points.frontPitch.angle(points.bicepsRight),
    baseOffset * options.sleevecapQ1Spread1
  )
  points.capQ1Cp2 = points.capQ1.shift(
    points.frontPitch.angle(points.bicepsRight),
    baseOffset * options.sleevecapQ1Spread2 * -1
  )
  points.capQ2Cp1 = points.capQ2.shift(
    points.centerCap.angle(points.frontPitch),
    baseOffset * options.sleevecapQ2Spread1
  )
  points.capQ2Cp2 = points.capQ2.shift(
    points.centerCap.angle(points.frontPitch),
    baseOffset * options.sleevecapQ2Spread2 * -1
  )
  points.capQ3Cp1 = points.capQ3.shift(
    points.backPitch.angle(points.centerCap),
    baseOffset * options.sleevecapQ3Spread1
  )
  points.capQ3Cp2 = points.capQ3.shift(
    points.backPitch.angle(points.centerCap),
    baseOffset * options.sleevecapQ3Spread2 * -1
  )
  points.capQ4Cp1 = points.capQ4.shift(
    points.bicepsLeft.angle(points.backPitch),
    baseOffset * options.sleevecapQ4Spread1
  )
  points.capQ4Cp2 = points.capQ4.shift(
    points.bicepsLeft.angle(points.backPitch),
    baseOffset * options.sleevecapQ4Spread2 * -1
  )

  // Sleevecap seamline
  paths.sleevecap = new Path()
    .move(points.bicepsRight)
    .curve(points.bicepsRight, points.capQ1Cp1, points.capQ1)
    .curve(points.capQ1Cp2, points.capQ2Cp1, points.capQ2)
    .curve(points.capQ2Cp2, points.capQ3Cp1, points.capQ3)
    .curve(points.capQ3Cp2, points.capQ4Cp1, points.capQ4)
    .curve(points.capQ4Cp2, points.bicepsLeft, points.bicepsLeft)

  // Store sleevecap length & height
  store.pset('sleevecapLength', paths.sleevecap.length())
  store.pset('sleevecapHeight', paths.sleevecap.edge('bottom').x - paths.sleevecap.edge('top').x)
  if (run === 0) {
    let armholeLength = store.pget('frontArmholeLength', 250) + store.pget('backArmholeLength', 250)
    let sleevecapEase = armholeLength * options.sleevecapEase
    store.pset('sleevecapEase', sleevecapEase)
    store.pset('sleevecapTarget', armholeLength + sleevecapEase)
  }

  // Uncomment this line to see all sleevecap iterations
  //paths[run] = paths.sleevecap;
}

const menu = 'advanced.sleevecap'
export const sleeve = {
  library: true,
  name: 'library.sleeve',
  measurements: ['biceps', 'hpsToWaistBack', 'shoulderToWrist', 'waistToArmpit', 'wrist'],
  options: {
    optionPrefix: '',
    mockSleeve: false, // Can be set via a flag/suggest, not via UI
    sleevecapEase: { pct: 0, min: 0, max: 10, menu },
    sleevecapTopFactorX: { pct: 50, min: 25, max: 75, menu },
    sleevecapTopFactorY: { pct: 45, min: 35, max: 125, menu },
    sleevecapBackFactorX: { pct: 60, min: 35, max: 65, menu },
    sleevecapBackFactorY: { pct: 33, min: 30, max: 65, menu },
    sleevecapFrontFactorX: { pct: 55, min: 35, max: 65, menu },
    sleevecapFrontFactorY: { pct: 33, min: 30, max: 65, menu },
    sleevecapQ1Offset: { pct: 1.7, min: 0, max: 7, menu },
    sleevecapQ2Offset: { pct: 3.5, min: 0, max: 7, menu },
    sleevecapQ3Offset: { pct: 2.5, min: 0, max: 7, menu },
    sleevecapQ4Offset: { pct: 1, min: 0, max: 7, menu },
    sleevecapQ1Spread1: { pct: 10, min: 4, max: 20, menu },
    sleevecapQ1Spread2: { pct: 15, min: 4, max: 20, menu },
    sleevecapQ2Spread1: { pct: 15, min: 4, max: 20, menu },
    sleevecapQ2Spread2: { pct: 10, min: 4, max: 20, menu },
    sleevecapQ3Spread1: { pct: 10, min: 4, max: 20, menu },
    sleevecapQ3Spread2: { pct: 8, min: 4, max: 20, menu },
    sleevecapQ4Spread1: { pct: 7, min: 4, max: 20, menu },
    sleevecapQ4Spread2: { pct: 6.3, min: 4, max: 20, menu },
    sleeveLengthBonus: { pct: 0, min: -40, max: 10, menu: 'style' },
    sleeveWidthGuarantee: { pct: 90, min: 25, max: 100, menu: 'advanced' },
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
    if (!ensureStoreValues(sleeve, 'mockSleeve', store, options)) return part

    store.pset('__sleevecapFactor', 1)
    let run = 0
    let delta = 0
    do {
      draftSleevecap(part, run)
      delta = sleevecapDelta(store)
      sleevecapAdjust(store)
      run++
    } while (
      (options.mockSleeve || options.libraryFitSleeve === true) &&
      run < 50 &&
      Math.abs(sleevecapDelta(store)) > 2
    )

    // Paths
    paths.sleevecap.attr('class', 'fabric')

    // Determine the sleeve length
    store.pset('sleeveLength', measurements.shoulderToWrist * (1 + options.sleeveLengthBonus))
    points.sleeveTip = paths.sleevecap.edge('top')
    points.sleeveTop = new Point(0, points.sleeveTip.y) // Always in center

    // Wrist
    points.centerWrist = points.sleeveTop.shift(-90, store.pget('sleeveLength'))
    points.wristRight = points.centerWrist.shift(
      0,
      (measurements.wrist * (1 + options.cuffEase)) / 2
    )
    points.wristLeft = points.wristRight.rotate(180, points.centerWrist)

    // Anchor point for sampling
    points.gridAnchor = new Point(0, 0)

    // Paths
    paths.sleevecap.hide()
    paths.seam = new Path()
      .move(points.bicepsLeft)
      .move(points.wristLeft)
      .move(points.wristRight)
      .line(points.bicepsRight)
      .join(paths.sleevecap)
      .close()
      .attr('class', 'fabric')
    if (sa) paths.sa = paths.seam.offset(sa).attr('class', 'fabric sa')

    /*
     * Annotations
     */

    // Anchor point for sampling
    points.gridAnchor = new Point(0, 0)

    // Grainline
    macro('grainline', {
      from: points.centerWrist,
      to: points.centerBiceps,
    })

    // Cut list
    let cuts = store.pget('cutlist', {})
    if (!Array.isArray(cuts)) cuts = [cuts]
    for (const cut of cuts) store.cutlist.addCut({ cut: 2, from: 'fabric', ...cut })

    // Logo
    points.logo = points.centerBiceps.shiftFractionTowards(points.centerWrist, 0.3)
    snippets.logo = new Snippet('logo', points.logo)

    // Title
    const title = store.pget('title', {})
    macro('title', { at: points.centerBiceps, nr: 1, title: 'sleeve', ...title })

    // Notches
    if (options.mockSleeve || store.pget('frontArmholeToArmholePitch')) {
      points.frontNotch = paths.sleevecap.shiftAlong(store.pget('frontArmholeToArmholePitch', 150))
      snippets.frontNotch = new Snippet('notch', points.frontNotch)
    }
    if (options.mockSleeve || store.pget('backArmholeToArmholePitch')) {
      points.backNotch = paths.sleevecap
        .reverse()
        .shiftAlong(store.pget('backArmholeToArmholePitch', 150))
      snippets.backNotch = new Snippet('bnotch', points.backNotch)
    }

    // Dimensions
    macro('vd', {
      id: 'hCuffToArmhole',
      from: points.wristLeft,
      to: points.bicepsLeft,
      x: points.bicepsLeft.x - sa - 15,
    })
    macro('vd', {
      id: 'hFull',
      from: points.wristLeft,
      to: points.sleeveTip,
      x: points.bicepsLeft.x - sa - 30,
    })
    macro('hd', {
      id: 'wFull',
      from: points.bicepsLeft,
      to: points.bicepsRight,
      y: points.sleeveTip.y - sa - 30,
    })
    macro('hd', {
      id: 'wCuff',
      from: points.wristLeft,
      to: points.wristRight,
      y: points.wristLeft.y + sa + 30,
    })
    macro('pd', {
      id: 'lSleevevap',
      path: paths.sleevecap.reverse(),
      d: -1 * sa - 15,
    })

    return part
  },
  store: {
    reads: [
      'backArmholeLength',
      'backArmholeToArmholePitch',
      'frontArmholeLength',
      'frontArmholeToArmholePitch',
      'cutlist',
      'title',
    ],
    writes: [
      'sleevecapHeight',
      'sleevecapLength',
      'sleeveLength',
      'sleevecapTarget',
      'sleevecapEase',
    ],
    uses: ['__sleevecapFactor'],
  },
}
