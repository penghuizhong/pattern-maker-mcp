# NOTICE — vendored FreeSewing code

The designs in this library (`blocks/brian/`, `designs/teagan/`,
`parts/library/`) are vendored from FreeSewing 4.10.2:

- Source: https://codeberg.org/freesewing/freesewing
- License: MIT, © Joost De Cock (see the FreeSewing LICENSE;
  the MIT text also covers this project's own code where noted)
- Version vendored: 4.10.2 (2026-09-13)

## What was changed

Only the intra-library imports were rewritten to relative paths so the
library is self-contained (designs reference each other inside this
repo instead of through npm package names):

- `blocks/brian/src/index.mjs`: `@freesewing/library` → relative
- `designs/teagan/src/index.mjs`: `@freesewing/brian` → relative
- `designs/teagan/src/front.mjs`: `@freesewing/brian` → relative
- `designs/teagan/src/sleeve.mjs`: `@freesewing/library` → relative

Each rewritten file carries a header comment saying so. Everything
else -- the formulas, `about.json`, `i18n/`, `package.json`,
`README.md` -- is copied verbatim. Files not vendored: the designs'
tests (they depend on the FreeSewing monorepo's shared test harness)
and their CHANGELOGs.

The FreeSewing framework (`@freesewing/core`, `@freesewing/config`,
plugins) is NOT vendored; it is a pinned dependency in
`server/package.json` (exact 4.10.2, `package-lock.json` is the pin).
