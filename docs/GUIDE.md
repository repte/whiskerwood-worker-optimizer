# Worker Optimizer Documentation

[Back to README](../README.md)

[Usage](#usage) · [Implementation](#how-it-works) · [Build](#building-and-testing) · [Testing and limits](#verification-and-known-limits) · [Troubleshooting](#reporting-problems)

Assign residents to suitable workplaces with one manual icon, while respecting the saved number to keep free for construction.

Worker Optimizer matches residents to jobs using guild specialties, productivity and job eligibility. It selects feasible minimum operating crews before filling additional positions by suitability. Active supported workplaces have equal priority in this preview.

**Version scope:** this guide describes **v0.3.1-preview**. The user will perform the in-game test; acceptance is pending. GitHub publication and preparing Workshop files are separate from submitting an update to Steam. Historical validation for earlier releases does not validate this preview.

## Features

- A small action button in the lower-left corner of the game.
- An always-visible assignment icon. The former visibility shortcut is disabled, including previously saved bindings.
- One manual reassignment request per click. Saved automatic schedules are disabled.
- A saved reserve of unassigned residents for construction: **1 by default**, **0 to disable**. This preview has no reserve or shortcut editor.
- Feasible minimum operating crews before additional workers, subject to eligibility and the construction reserve.
- Equal priority for active supported buildings. Saved category/type priorities and strict/weighted mode selections are ignored.
- The earlier settings and logbook code/assets retained, with their views inaccessible from this preview.
- Paused buildings and their current workers left untouched.
- Dynamic discovery of building definitions instead of a hardcoded building list.
- Unsupported workplaces skipped and reported, with their workers protected.
- Translations for all 17 game languages, with English fallback.

## Status

The target is **Whiskerwood 0.7.209.0 for Windows**. The [v0.3.1-preview release](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.3.1-preview) contains the preview package and its current verification record. The [Workshop item](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514) receives this version only after a separate manual submission.

**In-game validation is pending and belongs to the user.** This preview skips unsupported warehouse workplaces whose native API does not expose a mutable workforce and protects their existing workers. The fix must still be tested in the shipping game. Editor tests use native-function stubs and cannot establish that game-side commands succeed. Use a separate test save. See [preview notes](releases/v0.3.1-preview.md).

## Installation

For Workshop installation, subscribe, wait for Steam to download and restart the game. The prepared v0.3.1-preview upload is not a live Workshop update until manually submitted. To test this preview before submission, use its GitHub package and avoid loading the Workshop copy at the same time.

For manual installation, download [WorkerOptimizer-v0.3.1-preview.zip](https://github.com/repte/whiskerwood-worker-optimizer/releases/download/v0.3.1-preview/WorkerOptimizer-v0.3.1-preview.zip) from [Releases](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.3.1-preview), not the source-code ZIP. Use either Workshop or a local installation, never both. Close Whiskerwood before installing or replacing the mod. Place the packaged files in this directory:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\mods\WorkerOptimizer\
  WorkerOptimizer.pak
  WorkerOptimizer.uplugin
```

Start the game and load a settlement. Only the assignment icon should appear in the lower-left corner; settings and logbook controls must not appear.

The packaged mod does not require Python, Unreal Editor or the development tools. To uninstall, close the game and remove only the `WorkerOptimizer` folder from `mods`. Do not remove any save files.

## Usage

Click the assignment icon to run the optimizer. The icon displays a busy indicator until the request completes. Extra clicks do not restart or cancel it. No settings or logbook views are accessible.

**Recommended timing:** run assignment at night or just after a new day starts. Running it during the day may cause assignment errors; this compatibility fix does not remove that recommendation.

The optimizer captures scoring values once per plan. Ordinary speed/productivity fluctuations do not abort the request. Relevant workplace or eligibility changes can trigger bounded automatic replanning within the same manual request; this is not a scheduled run. The supported native calls update their assignment state before returning, so the result is checked immediately. Only observed effects count as confirmed changes. There is no player cancellation or automatic rollback of confirmed changes.

A rejected or unobserved result is treated as failure. After the request and its result processing finish, another manual attempt is possible; a returned native failure does not leave a persistent lock or require a world reload. An unrelated later state change is not counted as a late success. Revised native request handling still needs game testing and does not guarantee acceptance by the game. Inspect results in the game's building/resident windows and consult the mod log when reporting failures.

The icon is always visible. **Ctrl + Alt + O** and previously saved visibility bindings are disabled. There is no gear, logbook button or shortcut editor in this preview.

### Existing Preferences

| Saved preference | Behavior in this preview |
| --- | --- |
| Residents kept free for building | Respected. Minimum number of eligible residents to leave unassigned; default 1 when unset. Takes precedence over staffing. |
| Assignment mode: strict/weighted | Ignored. Active supported buildings use the same priority. |
| Category and building-type priorities | Ignored. No building receives an earlier priority tier from old preferences. |
| Automatic assignment | Disabled, including an earlier saved day-start or minute schedule. |
| Visibility shortcut | Disabled. The icon remains visible, including with an older saved binding. |

The reserve counts eligible, movable residents only. Workers protected in paused or unsupported buildings do not count toward it, and construction-yard employees are not unassigned builders. If fewer eligible residents are available than requested, all available residents remain free.

For example, with five residents eligible for all three one-worker workplaces and a saved reserve of two, the staffing target is one worker in each workplace and two free residents. Extra positions are considered after feasible minimum crews. When there are too few suitable residents to staff every minimum crew, some workplaces remain unstaffed; equal priority does not remove eligibility or reserve constraints.

Native assignment effects are checked after each call returns. There is no delayed command queue that needs the simulation to resume before it can confirm a returned call.

### Disabled Views and Schedules

There are no scheduled runs in this preview. Loading a save, a new day or elapsed timer intervals must not start an assignment request. This also applies when a schedule was enabled in an earlier release.

The former settings, priorities and logbook implementation remains in the source and assets, but its views cannot be opened. Stored preferences and history are not deleted as part of the interface simplification. Existing reserve values are read without providing an editor for them. Earlier documentation describing those panels applies only to the corresponding older release.

### Languages

The mod follows the game language and includes all 17 game-language entries:

English, French, German, Italian, Spanish, Russian, Japanese, Simplified Chinese, Korean, Turkish, Brazilian Portuguese, Polish, Ukrainian, Czech, Hungarian, Traditional Chinese and Latin American Spanish.

Unsupported languages fall back to English. There is no separate mod language selector. Catalog completeness and placeholder checks pass; translation quality and rendering across all languages still need manual review.

## How It Works

The runtime is implemented in Unreal Engine Blueprints and UMG widgets, built with the [Whiskerwood modkit](https://github.com/Whiskerwood-Modding/Whiskerwood-Project). Python scripts author and test the Blueprint assets in the editor; they are not part of the running mod.

Each run has five stages:

1. **Capture the settlement.** Read player-owned workplaces, their slots and current occupants, then collect eligible residents. Exclude paused or unsupported workplaces and protect their occupants.
2. **Score possible assignments.** Check education and role requirements, then calculate productivity for each hypothetical workplace. Employment-dependent modifiers are adjusted for the destination instead of blindly reusing the resident's current displayed productivity. School assignments use teacher/student eligibility and learning-rate scoring.
3. **Plan staffing.** Reserve the saved number of free residents, give active supported buildings equal priority, select feasible minimum crews, then fill additional positions by worker suitability. Where a workplace has no fixed minimum role, an eligible occupied slot supplies its initial crew. Native required roles still have to form complete crews. The assignment solver uses a shortest-augmenting-path approach. Empty slots are represented explicitly.
4. **Validate the result.** Reject duplicate assignments, invalid roles and inconsistent snapshots before applying changes. Teacher-dependent school assignments are checked as complete plans.
5. **Apply and confirm.** Release the workers needed for the next target and its native dependencies, then hire the selected worker. There is no global fire-all batch. Firing a native required worker also dismisses that building's optional workers, so the queue explicitly releases movable optional workers first and schedules their planned assignments afterward. If an optional occupant is protected, the planner keeps affected required incumbents fixed to avoid that collateral dismissal. Other unchanged assignments remain in place; remaining surplus workers are released afterward. Send native fire/hire actions one at a time and check the workplace and slot immediately after each call returns. Relevant changes can trigger bounded automatic replanning; a rejected result or exhausted retries ends the request with a reported reason. Only observed effects are counted. The mod does not directly overwrite the game's workforce arrays.

Among otherwise equal production outcomes, the reserve selection favors residents with better neutral productivity, carrying capacity and movement speed. This is a tie-breaking heuristic, not a prediction of exact construction time.

Planning advances incrementally across ticks. A map-load session owns the controller, action bridge and widget, prevents duplicate controls and cleans up its references when the world ends. Loading a save does not trigger an assignment run, and schedules are disabled.

Startup listens for the native load-completion event and also checks `ProjectArcoGameModeBase.CurrentInitPhase`. Once the phase is `DONE` and a player controller exists, a missing event no longer prevents session creation. The fallback is checked at half-second intervals and stops once the session is ready; it never triggers optimization.

The assignment icon adapts to viewport size and the game's UI scale. Other mods' overlays are not automatically detected. The retained panel implementation is inaccessible in this preview.

### Update Compatibility

Building types, guild specialties and slot layouts come from game data. New building types using supported workplace components can participate without adding their names to the mod.

The workplace adapter and native action bridge are version-sensitive. A new component implementation or changed game API may still require an update. Unknown workplaces are preserved rather than assigned using guessed rules. Newly discovered supported types use the same priority as other active supported buildings.

In **v0.3.1-preview**, the native `ResourceBuilding` family is excluded from planning, including `GranaryResourceBuilding` used by prefab `tinywarehouse`. In the inspected game version, its native assignment API returns no mutable workforce, so a planned hire could stop the request. Existing occupants remain protected: they are neither reassigned elsewhere nor counted toward the free construction reserve. This addresses that specific rejected-hire path, not every possible assignment failure. See the [native workplace capability verification](verification/2026-10-07-native-workplace-capability.md).

### Source Layout

```text
Content/Mods/WorkerOptimizer/     Blueprint assets, widgets and mod descriptor
Automation/WorkerOptimizer/      Asset generators, tests and packaging scripts
Plugins/WorkerOptimizerEditor/   Editor-only authoring and test support
```

`BP_WorkforceSnapshot` and `BP_WorkplaceAdapter` handle discovery. `BP_JobEligibility` and `BP_JobScorer` provide eligibility and scoring. `BP_StaffingPlanner`, `BP_AssignmentSolver` and `BP_PlanSearch` produce the plan. `BP_ActionPlan`, `BP_ActionBridge` and `BP_ApplicationRunner` validate and apply it. `BP_AutoAssignment`, `BP_Logbook`, `BP_SettingsModel`, `BP_HotkeyConfig` and the former panel widgets remain present, but scheduling, visibility shortcuts and panel access are disabled. `BP_PrioritySettings`, `BP_Startup`, `BP_MapLoad` and the main widget handle preserved preferences, lifecycle and the manual icon.

The editor helper is a development dependency only. It is excluded from the packaged mod. Runtime assets reference existing game content; the mod package does not bundle the game or Unreal Engine.

## Building and Testing

Set up the official modkit and its required custom Unreal Engine build first, following the [modkit setup instructions](https://github.com/Whiskerwood-Modding/Whiskerwood-Project#setup). An installed copy of Whiskerwood is required. The tested development environment used the custom Unreal Engine 5.8.3 build on Windows and modkit commit `a1a958377bda68a12a7749faf477de7514042984`.

Use this source as an overlay on a separate modkit checkout, preserving the directories shown above. Build the editor-only `WorkerOptimizerEditor` plugin as part of the project and ensure it is enabled. Open the project with the required custom engine; a stock engine installation is not a substitute.

Copy `Content/Mods/WorkerOptimizer`, `Automation/WorkerOptimizer` and `Plugins/WorkerOptimizerEditor` into the corresponding modkit directories. Also copy `docs/WorkerOptimizer/SPIELTEST.md` to `Docs/WorkerOptimizer/SPIELTEST.md`; the packaging script includes this checklist beside the deliverable. Do not replace the modkit's root README or license. No game content, engine binaries or locally built editor binaries are included in this repository.

The optional `inspect_native.py` investigation helper needs `capstone` and `pefile` under `Intermediate/WorkerOptimizerTools`. It is not required for building or playing the mod. The other editor scripts use the modkit's bundled tooling.

From the modkit root, with the engine path adjusted for your installation:

```powershell
./Automation/WorkerOptimizer/Test-Mod.ps1 -EngineRoot '<path-to-custom-engine>'
./Automation/WorkerOptimizer/Build-Mod.ps1 -EngineRoot '<path-to-custom-engine>'
```

The build script runs the test suites, performs a full cook and verifies the mod package's content inventory and integrity. It does not install or publish the mod. It packages the existing Blueprint assets; changes to generator scripts must first be applied to those assets in the editor.

The installable output is:

```text
Saved/WorkerOptimizerBuilds/<build-id>/Delivery/WorkerOptimizer/
```

Only the `.pak` and `.uplugin` files in that folder are installation inputs. The larger intermediate Windows archive is not a standalone game and must not be distributed as one.

## Verification and Known Limits

**Current preview: in-game validation is pending.** The user will test **0.3.1-preview**. Its workplace exclusion and occupant protection must be checked against the real game; neither editor fixtures nor successful package checks prove that live assignments succeed. See [preview notes](releases/v0.3.1-preview.md) for the current verification status.

The focused workplace tests, full automated editor suite, Windows cook and package checks passed for this fix on 7 October 2026 (CEST). The [native workplace capability verification](verification/2026-10-07-native-workplace-capability.md) records those checks and their tested build. The final v0.3.1-preview delivery is packaged separately with updated external version metadata.

Acceptance should cover unchanged occupants of affected warehouse workplaces, supported neighboring workplaces still participating, the single visible icon, inactive old schedules, equal treatment despite old priority/mode preferences, the preserved builder reserve, minimum crews before extra staffing, and actual confirmed worker changes. Test in a separate save, including a save with existing preferences; use the [local test checklist](LOCAL_TEST.md).

### Historical Checks

The following records describe older releases only. They do not validate the new manual interface or native request handling.

The complete automated test run, full cook and package checks passed for **0.2.0-local.7 on 6 October 2026**. Its final in-game test was confirmed green by the author on the same date. The **v0.2.0** release PAK is byte-identical to that tested candidate; only descriptor version and description metadata changed. Coverage includes assignment planning, fixed and flexible minimum crews, priorities, protected workers, reserves, language catalogs, settings, schedules, logbook behavior, lifecycle, action confirmation and the redesigned UI. Package checks confirmed 46 runtime assets and excluded editor helpers and test probes. See the [release PAK checksum](PREVIEW.md#verification).

Four native UMG frames using synthetic editor data cover wide history at 1920x1080 and reduced DPI, plus narrow history, priorities and general settings at 1280x720 and reduced DPI. Native event checks exercise history selection and category expansion; geometry checks cover columns, text, scrolling and panel bounds. These editor checks are separate from the author's final in-game confirmation. Editor tests cannot prove all native game behavior because the modkit contains native-function stubs.

Live testing on 5 October 2026 confirmed:

- Reserves of 0, 1 and 2 produced the expected number of free residents in a five-resident settlement, with all three workplaces staffed.
- Appropriate guild assignments were visible in resident profiles, including the game's +50 guild-specialty productivity contribution.
- The visibility shortcut worked while paused and persisted across restart.
- English, German, French and Polish settings refreshed correctly after changing the game language.

Remaining limits include large-city performance, complex school configurations, special bonus-slot production effects, live priority trade-offs and workplace changes during queued actions. Exact school search can become expensive as the number of distinct teacher choices grows.

Earlier 0.2.0 previews completed assignment runs and showed persisted history in the shipping game. The final release candidate passed the author's in-game test on 6 October 2026. This confirmation does not establish comprehensive coverage of scheduling intervals, extended sessions, all 17 languages, save-slot history edge cases or full keyboard/gamepad operation; those areas still need broader manual validation.

Incremental work, cached views and reused list rows reduce per-frame work, but the time budget is not a hard frame-time guarantee. Smooth performance in large settlements remains unverified.

The optimizer follows its defined staffing and productivity objectives. It does not model total economic value, resource balance or full travel efficiency, and the results are not a claim of a globally optimal settlement economy. Keeping residents free does not guarantee construction progress when materials or other game conditions prevent building.

## Reporting Problems

Include the mod and game versions, other active mods, resident/building/school counts, the saved builder reserve if known, the expected result, the actual result and the icon tooltip. Note whether the save had older schedule or priority preferences. Before/after screenshots of assignments are useful; this preview has no accessible logbook view.

The game's mod log is located at:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\Logs\modlog.txt
```

Relevant entries begin with `WorkerOptimizer` or `Worker Optimizer`. Review logs for personal information before sharing them. Do not upload your entire save or log directory.

## Acknowledgments

Built using the community [Whiskerwood modkit](https://github.com/Whiskerwood-Modding/Whiskerwood-Project). Whiskerwood and its game assets belong to their respective owners. This is an unofficial community mod; see the [third-party notices](../THIRD_PARTY_NOTICES.md) for attribution.
