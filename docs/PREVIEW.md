# Preview Validation

**Version: v0.3.3-performance-preview | Target: Whiskerwood 0.7.209.0 on Windows | Updated: 8 October 2026**

**Public in-game acceptance remains pending and belongs to the user.** See the [release notes](releases/v0.3.3-performance-preview.md), [GitHub release](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.3.3-performance-preview) and [packaged ZIP](https://github.com/repte/whiskerwood-worker-optimizer/releases/download/v0.3.3-performance-preview/WorkerOptimizer-v0.3.3-performance-preview.zip). The Workshop update is prepared, not submitted; its live version remains v0.3.1-preview.

## Current Change

The performance update removes repeated work while preserving the existing exact assignment approach, constraints and checked outcomes. No approximate search, hybrid solver or arbitrary candidate limit is introduced.

The assignment icon uses the same native gameplay-HUD visibility checks as the Campfire Panel mod and belongs only to the gameplay HUD. It hides in menus, when the HUD is hidden, during loading or saving, and in replay. Simulation pause and end of day do not themselves hide it. Temporarily hiding the icon does not cancel or restart an active request.

One-click assignment, feasible minimum crews before extra staffing, the saved construction reserve and protection of paused/unsupported workplaces remain unchanged. The warehouse compatibility behavior introduced in [v0.3.1-preview](releases/v0.3.1-preview.md) is retained.

## Current Verification

Six compiled-editor planner benchmarks with 1,000 workers took **5.61-14.55 seconds** on the test machine. Assignment hashes and checked objectives were unchanged. The [large-settlement record](verification/2026-10-08-large-settlements.md) documents the complete editor suite, repeated measurements and pre-icon local package. These timings measure planner calls, not total in-game duration; school search, frame scheduling, capture/scoring and assignment application can add time.

Combined build `20261008-115852-7696bc58` passed the complete editor suite, including gameplay visibility, a Windows Shipping cook and package checks on 8 October 2026. The final package contains 46 runtime assets / 92 entries (557,151 bytes); solver and planner asset hashes match the measured performance candidate. The [gameplay-visibility record](verification/2026-10-08-gameplay-visibility.md) documents the saved-asset checks and final package checksum.

These checks do not replace shipping-game acceptance. Use a separate save and only one installed copy of the mod. Prefer night or just after day start; daytime assignment may cause errors.

1. Check that the icon follows gameplay visibility: pause/end of day alone keep it visible; menus, hidden HUD, loading and saving hide it.
2. Hide and restore the icon during an active request; confirm no cancellation, duplicate request or restart occurs.
3. Measure complete large-settlement runs, including schools, and compare actual assignments, minimum crews and free residents. A finished busy indicator alone does not prove success.
4. Confirm paused and unsupported warehouse occupants remain unchanged, and report failed runs with tooltips, logs and before/after observations.

See the [local game-test checklist](LOCAL_TEST.md) for the detailed acceptance checks.

## Historical: 0.2.0 Release Validation

The following record is retained for the older release. Its features, Workshop status and game acceptance do not describe v0.3.3-performance-preview.

**Release: `0.2.0` | Tested candidate: `0.2.0-local.7` | Updated: 6 October 2026**

The first regular [GitHub release, v0.2.0](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.2.0)
is available as [WorkerOptimizer-v0.2.0.zip](https://github.com/repte/whiskerwood-worker-optimizer/releases/download/v0.2.0/WorkerOptimizer-v0.2.0.zip).
The Workshop update is prepared and awaits manual submission; its published
package remains **0.1.1-dev**. The author confirmed the final in-game test of
**0.2.0-local.7** passed on 6 October 2026.

### Included

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

### Verification

The full automated Blueprint suite, native UMG render/interaction checks, full
package build and package validation passed on 6 October 2026. The UI checks
include reduced game DPI, wide/narrow history layouts, native selection events,
category expansion and measured text/control bounds. These checks use editor
fixtures, not a replacement for in-game acceptance.

The release PAK is byte-identical to the tested **0.2.0-local.7** PAK and contains
46 assets / 92 package entries. Only the separate descriptor's version and
description metadata changed for the **0.2.0** release; the PAK was not rebuilt.
The PAK SHA256 is:

```text
A2A90735D8018AA36DF5E1448284B12EBA4F5C0166939316300E7F86B2A6B5FD
```

The author's final shipping-game test passed on 6 October 2026. This acceptance
does not establish comprehensive all-language review, long-session coverage or
large-settlement performance. Those areas still need broader manual validation.
Frame budgets are not a guarantee of stutter-free gameplay.

### Quick In-Game Check

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
