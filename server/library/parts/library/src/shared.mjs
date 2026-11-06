/**
 * A function to ensure that all required store values are set or mocked
 *
 * @param {object} partConfig - The part config object as defined in the design (not the runtime part)
 * @param {string} mockOptionName - The name of the option that controls mocking of store values
 * @return {bool} ok - true is store values or present or should be mocked, false if not
 */
export function ensureStoreValues(partConfig, mockOptionName, store, options) {
  let missing = false
  for (const key of partConfig.store.reads) {
    // No need to be pedantic about title and cutlist
    if (!['title', 'cutlist'].includes(key) && !store.pget(key)) missing = true
  }
  if (missing) {
    const desc = `Part **${partConfig.name}** relies on these values to be set in the store: ${partConfig.store.reads.map((item) => '`' + item + '`').join(', ')}`
    store.flag.warn({
      title: `Missing store data for ${partConfig.name}`,
      desc,
      suggest: {
        text: options[mockOptionName] ? 'Clear mocked store values' : 'Mock store values',
        icon: 'fixme',
        update: {
          settings: [['options', mockOptionName], options[mockOptionName] ? false : true],
        },
      },
    })
    store.log.warn(desc)

    return options[mockOptionName] ? true : false
  }

  return true
}
