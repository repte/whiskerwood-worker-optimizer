# Worker Optimizer Documentation

[Back to README](../README.md)

[Settings](#usage) · [Implementation](#how-it-works) · [Build](#building-and-testing) · [Testing and limits](#verification-and-known-limits) · [Troubleshooting](#reporting-problems)

Assign residents to suitable workplaces with one click, while keeping a configurable number free for construction.

Worker Optimizer matches residents to jobs using guild specialties, productivity and job eligibility. It selects feasible minimum operating crews in priority order before filling additional positions, with category priorities and building-type overrides to control where workers are needed most.

**Version scope:** this guide describes **v0.2.0**, available from [GitHub Releases](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.2.0). The Workshop update is prepared and awaits manual submission; the published Workshop package remains **v0.1.1-dev**.

## Features

- A small action button in the lower-left corner of the game.
- Responsive General, Priorities and Logbook tabs, opened from the settings gear or logbook button.
- A rebindable visibility shortcut, defaulting to **Ctrl + Alt + O**.
- One reassignment run per click, plus optional scheduling at day start or every 5, 10 or 15 real-time minutes; automatic assignment is off by default.
- A configurable reserve of unassigned residents for construction: **1 by default**, **0 to disable**, adjustable up to **100**.
- Feasible minimum operating crews selected in priority order before additional workers, subject to eligibility and the construction reserve.
- Strict or weighted priorities, with five priority levels, searchable categories and building-type overrides.
- A logbook with run results, confirmed changes and grouped reasons, retaining up to 50 runs per identified save slot.
- Paused buildings and their current workers left untouched.
- Dynamic discovery of building definitions instead of a hardcoded building list.
- Unsupported workplaces skipped and reported, with their workers protected.
- Translations for all 17 game languages, with English fallback.

## Status

The first regular release, **v0.2.0**, is available on [GitHub Releases](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.2.0). Built for **Whiskerwood 0.7.209.0 for Windows**. The [Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514) update awaits manual submission.

On **6 October 2026**, candidate **0.2.0-local.7** passed the full automated test run, full cook and package checks. Four native UMG frames with synthetic editor data passed the UI checks. The author also confirmed that the final test in the shipping game passed. The v0.2.0 release uses that exact tested PAK; only descriptor version and description metadata changed. See [release validation](PREVIEW.md). Larger settlements, complex school arrangements and interactions with other mods need further testing. Use a separate test save before trying it in an established settlement.

## Installation

The existing Workshop subscription currently installs **v0.1.1-dev**. The **v0.2.0** Workshop update is prepared and awaits manual submission. For Workshop installation, subscribe, wait for Steam to download and restart the game. Remove any separate local WorkerOptimizer installation first.

For manual installation of **v0.2.0**, download [WorkerOptimizer-v0.2.0.zip](https://github.com/repte/whiskerwood-worker-optimizer/releases/download/v0.2.0/WorkerOptimizer-v0.2.0.zip) from [Releases](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.2.0), not the source-code ZIP. Use either Workshop or a local installation, never both. Close Whiskerwood before installing or replacing the mod. Place the packaged files in this directory:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\mods\WorkerOptimizer\
  WorkerOptimizer.pak
  WorkerOptimizer.uplugin
```

Start the game and load a settlement. The action button and settings gear appear in the lower-left corner.

The packaged mod does not require Python, Unreal Editor or the development tools. To uninstall, close the game and remove only the `WorkerOptimizer` folder from `mods`. Do not remove any save files.

## Usage

Click the arrow button to run the optimizer. The button stays locked and displays a busy indicator until the request finishes. Extra clicks do not restart or cancel it; settings, logbook and visibility controls remain available.

The optimizer captures scoring values once per plan. Ordinary speed/productivity fluctuations do not abort the request. Relevant workplace or eligibility changes can trigger at most two automatic replans under the same frozen settings and logbook entry. Confirmed changes are retained, and a pending native command must be observed before replanning. An unconfirmed command keeps the start button locked to prevent overlapping changes; loading another world ends the old session. There is no player cancellation or automatic rollback of confirmed changes.

**Ctrl + Alt + O** hides or shows the controls without changing assignments. The adjacent gear opens **General**, **Priorities** and **Logbook**. General contains the reserve, assignment mode, automatic schedule and visibility shortcut. Priorities provides building search, expandable categories and building-type overrides. The logbook button opens run history directly.

In the older **v0.1.1-dev** Workshop package, the gear changes the visibility shortcut and assignment preferences are in the game's **Settings > Mods** menu. That release runs on demand and does not include the new tabbed panel, automatic schedule or logbook.

| Setting | Behavior |
| --- | --- |
| Assignment mode: strict | Higher priority tiers take precedence over lower tiers after minimum-crew selection. |
| Assignment mode: weighted | Priorities influence the productivity score, allowing trade-offs between priorities and productivity. |
| Residents kept free for building | Minimum number of eligible residents to leave unassigned. This reserve takes precedence over building staffing. |
| Automatic assignment | Off by default; choose day start or every 5, 10 or 15 real-time minutes. |
| Category priority | Sets a default priority from Very low to Very high. |
| Building-type priority | Overrides the category for every building of that type, or inherits the category setting. |

The reserve counts eligible, movable residents only. Workers protected in paused or unsupported buildings do not count toward it, and construction-yard employees are not unassigned builders. If fewer eligible residents are available than requested, all available residents remain free.

For example, with five available residents and three buildings that each need one worker to operate, a reserve of two leaves one worker in each building. A higher-priority building does not take a second worker at the expense of another building's feasible minimum crew. If there are too few eligible residents to supply all minimum crews, priorities determine which crews can be staffed.

Global game pause also pauses assignment processing. Resume the simulation to let a queued run complete. The visibility shortcut works while paused.

### Automatic Assignment

Automatic assignment is optional and off by default. Choose **Day start**, **5 minutes**, **10 minutes** or **15 minutes** in General. Minute intervals use real time, including time spent paused. A run that becomes due while paused waits for the simulation to resume; missed intervals coalesce into one pending run instead of accumulating. The next minute interval starts when the active run ends. Switching to Off stops future automatic runs but does not cancel an active request.

### Logbook

The logbook shows timestamps, results, confirmed assignment changes and grouped reasons. Use **All** or **Problems** to filter runs, then select an entry for details. It retains the latest 50 runs per identified save slot.

History is stored separately from the game save. Different save names or autosave slots can have separate histories; loading an older version of the same slot does not rewind its logbook. Copying only the save file does not copy the history. If the save slot cannot be identified safely, history stays in the current session. An entry awaiting persistence may be lost on immediate exit. History storage status is separate from the assignment result.

### Languages

The mod follows the game language and includes all 17 game-language entries:

English, French, German, Italian, Spanish, Russian, Japanese, Simplified Chinese, Korean, Turkish, Brazilian Portuguese, Polish, Ukrainian, Czech, Hungarian, Traditional Chinese and Latin American Spanish.

Unsupported languages fall back to English. There is no separate mod language selector. Catalog completeness and placeholder checks pass; translation quality and rendering across all languages still need manual review.

## How It Works

The runtime is implemented in Unreal Engine Blueprints and UMG widgets, built with the [Whiskerwood modkit](https://github.com/Whiskerwood-Modding/Whiskerwood-Project). Python scripts author and test the Blueprint assets in the editor; they are not part of the running mod.

Each run has five stages:

1. **Capture the settlement.** Read player-owned workplaces, their slots and current occupants, then collect eligible residents. Exclude paused or unsupported workplaces and protect their occupants.
2. **Score possible assignments.** Check education and role requirements, then calculate productivity for each hypothetical workplace. Employment-dependent modifiers are adjusted for the destination instead of blindly reusing the resident's current displayed productivity. School assignments use teacher/student eligibility and learning-rate scoring.
3. **Plan staffing.** Reserve the requested free residents, select feasible minimum crews in priority order, then fill additional positions according to the selected priority mode. Where a workplace has no fixed minimum role, an eligible occupied slot supplies its initial crew. Native required roles still have to form complete crews. The assignment solver uses a shortest-augmenting-path approach; strict tiers preserve earlier tier results while resolving later tiers. Empty slots are represented explicitly.
4. **Validate the result.** Reject duplicate assignments, invalid roles and inconsistent snapshots before applying changes. Teacher-dependent school assignments are checked as complete plans.
5. **Apply and confirm.** Send the game's native fire/hire actions one at a time and check the actual workplace and slot after each action. Relevant changes can trigger bounded automatic replanning; an unresolved command or exhausted retries stops further changes with a reported reason. The mod does not directly overwrite the game's workforce arrays.

Among otherwise equal production outcomes, the reserve selection favors residents with better neutral productivity, carrying capacity and movement speed. This is a tie-breaking heuristic, not a prediction of exact construction time.

Planning advances incrementally across ticks. A map-load session owns the controller, action bridge and widget, prevents duplicate controls and cleans up its references when the world ends. Loading a save does not itself trigger an assignment run; an enabled schedule waits for its next due event.

Startup listens for the native load-completion event and also checks `ProjectArcoGameModeBase.CurrentInitPhase`. Once the phase is `DONE` and a player controller exists, a missing event no longer prevents session creation. The fallback is checked at half-second intervals and stops once the session is ready; it never triggers optimization.

The controls and panel adapt to viewport size and the game's UI scale. The panel uses a narrow layout where needed, scrollable content and a minimum readable panel text size when the game reduces UI scale. Larger game scales remain respected. Resolution and DPI changes update the open panel. Other mods' overlays are not automatically detected.

### Update Compatibility

Building types, guild specialties, slot layouts and category identifiers come from game data. Priorities use stable internal identifiers rather than translated building names. New building types using supported workplace components can therefore participate without adding their names to the mod.

The workplace adapter and native action bridge are version-sensitive. A new component implementation or changed game API may still require an update. Unknown workplaces are preserved rather than assigned using guessed rules. Newly discovered types initially inherit their category priority; changes to their new settings take effect on the next run.

### Source Layout

```text
Content/Mods/WorkerOptimizer/     Blueprint assets, widgets and mod descriptor
Automation/WorkerOptimizer/      Asset generators, tests and packaging scripts
Plugins/WorkerOptimizerEditor/   Editor-only authoring and test support
```

`BP_WorkforceSnapshot` and `BP_WorkplaceAdapter` handle discovery. `BP_JobEligibility` and `BP_JobScorer` provide eligibility and scoring. `BP_StaffingPlanner`, `BP_AssignmentSolver` and `BP_PlanSearch` produce the plan. `BP_ActionPlan`, `BP_ActionBridge` and `BP_ApplicationRunner` validate and apply it. `BP_AutoAssignment` manages scheduling, and `BP_Logbook` manages run history. `BP_PrioritySettings`, `BP_SettingsModel`, `BP_HotkeyConfig`, `BP_Startup`, `BP_MapLoad` and the `WBP_` widgets handle preferences, lifecycle and the interface.

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

Include the game version, other active mods, resident/building/school counts, reserve and priority settings, the expected result, the actual result and the button tooltip. Before/after screenshots of assignments are useful.

The game's mod log is located at:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\Logs\modlog.txt
```

Relevant entries begin with `WorkerOptimizer` or `Worker Optimizer`. Review logs for personal information before sharing them. Do not upload your entire save or log directory.

## Acknowledgments

Built using the community [Whiskerwood modkit](https://github.com/Whiskerwood-Modding/Whiskerwood-Project). Whiskerwood and its game assets belong to their respective owners. This is an unofficial community mod; see the [third-party notices](../THIRD_PARTY_NOTICES.md) for attribution.
