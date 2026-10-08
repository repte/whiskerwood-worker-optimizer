# Assignment icon gameplay visibility

## Scope

The user requested the same gameplay-layer visibility as the Campfire Panel mod.
The assignment widget starts collapsed and becomes visible only after the
gameplay world and its native HUD are ready. The loader checks the same native
`ArcoPlayerState`, `HudState` and `VisibilityToggles` fields as Campfire Panel:
the HUD must have faded in, there must be no active `ArcoView`, HUD display must
be enabled, replay/developer hiding and saving must be inactive, and
`showHudRoot` must be true.

Simulation pause, end-of-day pause and an available victory action do not
themselves hide the icon. A menu or other state that hides the native gameplay
HUD still hides it. Visibility changes do not cancel, restart or disable an
assignment. The existing calculation and application algorithms are unchanged.

## Regression Evidence

The new compiled test first failed against the installed performance candidate:
`Assignment icon must start hidden before gameplay is ready` and
`Gameplay visibility function is missing: HudAllowsDisplay`.

The implementation changes only `generate_widget.py`, `generate_lifecycle.py`
and their generated `WBP_WorkerOptimizer` / `BP_MapLoad` assets. The widget writes
Slate visibility only when its visibility state changes. Shutdown hides it
before marking it closed. The manual UI pump continues to report UI health
independently of whether it is visible.

`test_gameplay_visibility.py` covers default-hidden construction, the native HUD
guard combinations, hide/restore, preserved preferences and run identity, and
shutdown. A real compiled controller tick is exercised while hidden; its editor
configuration boundary is explicit, not a claim of successful in-game worker
application. The test is registered in `test_all.py` and `Test-Mod.ps1`.

Independent source and test reviews found no actionable issues. After generation,
the same editor process retained a stale widget default and failed the initial
visibility assertions. A fresh editor load confirmed both the saved default and
new instances were collapsed. The complete fresh targeted run passed
`WO_GAMEPLAY_VISIBILITY_SAVED_ASSETS_PASS`, including the native HUD tests,
widget/manual-surface checks, notifications, layout and public-flavor checks.

The final complete `Test-Mod.ps1` suite passed with
`WO_GAMEPLAY_VISIBILITY_TESTS_PASS` at 10:03:39 UTC and `WO_ALL_TESTS_PASS` at
10:03:56 UTC on 8 October 2026. Its strict Python/Blueprint/script-error checks
passed. The solver and planner assets remain byte-identical to the final
performance benchmark assets; the visibility change does not regenerate them.

## Package And Installation

Combined build `20261008-115852-7696bc58` passed a full Windows Shipping cook
(`BUILD SUCCESSFUL`, exit 0) and `WO_PACKAGE_TESTS_PASS`. It contains 46 runtime
assets in 92 entries, excluding the editor-only chunk label. The PAK is 557,151
bytes, SHA256
`BF93CC988DEE20DD02C89C287A1F84D8834DD5CA89FFE1D8A355BB9AD86F4843`.
The descriptor identifies `0.3.3-performance-preview`, EngineVersion `5.8`.

All 46 runtime source assets and the descriptor matched the build project after
the tests. With the game closed, both local mod files were replaced and checked
against the verified delivery. The earlier performance-only local package is
preserved in `GameplayVisibility/PreviousLocalMod/` under the evidence directory
below. Saves, settings and other mods were not changed. The game was not launched
by this workflow. GitHub publication and Workshop preparation use this combined
package, not the earlier `20261008-112235-7c83b569` performance-only build.

## Acceptance Boundary

Editor fixtures do not establish the complete positive visibility path in a
shipping gameplay world or visually verify real menu/loading/saving transitions.
Those checks remain part of the user's game test. No automated game actions,
save edits or Workshop submission are part of this change.

Local development evidence is preserved under
`D:/TD/WoodMod/DeploymentCandidates/performance-1000/GameplayVisibility/`.
The [performance record](2026-10-08-large-settlements.md) documents the separate
planner-only timing measurements and their limits.
