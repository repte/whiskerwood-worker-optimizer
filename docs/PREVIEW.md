# 0.2.0 Source Preview

**Candidate: `0.2.0-local.7` | Updated: 6 October 2026**

This repository contains the upcoming 0.2.0 implementation. The published
Workshop package and downloadable release are still **0.1.1-dev**. This preview
does not announce a new binary release. Final in-game testing is in progress.

## Included

- Responsive settings with General, Priorities and Logbook tabs.
- Searchable building categories, expandable rows and per-type priority overrides.
- Optional assignment at day start or every 5, 10 or 15 real-time minutes.
  Timers count during pauses; assignments wait for the simulation to resume.
- A bounded logbook with timestamps, status icons/colors, confirmed changes and
  grouped reasons for unstaffed buildings. Storage follows the exact save slot.
- Translation catalogs for the game's 17 language IDs, without a separate
  language selector.
- Bounded automatic replanning inside the same request when relevant state
  changes. The start button stays locked; there is no player cancellation.
- Readable small-window layouts, corrected category expansion and history
  selection, aligned status columns and unclipped general-setting help text.

Both assignment modes aim to fill minimum operating crews before extra slots.
Builder reserve, worker eligibility and required crew sizes remain binding.
Buildings can remain unstaffed when there are not enough eligible workers.

## Verification

The full automated Blueprint suite, native UMG render/interaction checks, full
package build and package validation passed on 6 October 2026. The UI checks
include reduced game DPI, wide/narrow history layouts, native selection events,
category expansion and measured text/control bounds. These checks use editor
fixtures, not a replacement for in-game acceptance.

The local candidate package contains 46 assets / 92 package entries.
Its SHA256 is:

```text
A2A90735D8018AA36DF5E1448284B12EBA4F5C0166939316300E7F86B2A6B5FD
```

Final in-game UI verification, all-language review, long sessions and large
settlement performance are not signed off. Previous small-settlement tests do
not establish those results for this candidate. Frame budgets are not a
guarantee of stutter-free gameplay.

## Quick In-Game Check

Use a separate test save and only one installed copy of the mod.

1. Open all three tabs. Select different logbook runs and confirm their details change.
2. Expand a category, search for a building and check its inherited or own priority.
3. Resize the game window. Text should remain readable and the logbook should switch between side-by-side and stacked views.
4. With the simulation running, assign once. The start button must remain locked until the request finishes or stops with a reported reason.
5. Compare worker professions, minimum crews, reserve and paused buildings before and after the run.
6. Check optional scheduling, pause/resume, and logbook persistence after saving and reloading.

For issues, include the game/mod versions, other active mods, settlement size,
settings, expected result and the relevant logbook entry. Review screenshots
and logs for private information before posting them publicly.

See the [guide](GUIDE.md) for implementation details and limitations.
