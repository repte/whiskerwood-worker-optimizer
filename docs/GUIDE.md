# Worker Optimizer Documentation

[Back to README](../README.md)

[Settings](#usage) · [Implementation](#how-it-works) · [Build](#building-and-testing) · [Testing and limits](#verification-and-known-limits) · [Troubleshooting](#reporting-problems)

Assign residents to suitable workplaces with one click, while keeping a configurable number free for construction.

Worker Optimizer matches residents to jobs using guild specialties, productivity and job eligibility. It gives buildings their minimum operating crews before filling additional positions, with category priorities and building-type overrides to control where workers are needed most.

## Features

- A small action button in the lower-left corner of the game.
- A rebindable visibility shortcut, defaulting to **Ctrl + Alt + O**.
- One reassignment run per click, with no automatic background rebalancing.
- A configurable reserve of unassigned residents for construction: **1 by default**, **0 to disable**, adjustable up to **100**.
- Minimum operating crews before additional workers, subject to eligibility and the construction reserve.
- Strict or weighted priorities, with five priority levels and building-type overrides.
- Paused buildings and their current workers left untouched.
- Dynamic discovery of building definitions instead of a hardcoded building list.
- Unsupported workplaces skipped and reported, with their workers protected.
- Translations for English, German, Polish, French and Dutch.

## Status

Available on [Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514). Built for **Whiskerwood 0.7.209.0 for Windows**.

Version **0.1.1-dev** passes 30 automated suites and 10 native widget pixel checks. Core assignment was live-tested in version 0.1.0-dev; the new startup/layout repair has not yet been tested in-game. Larger settlements, complex school arrangements and interactions with other mods need further testing. Use a separate test save before trying it in an established settlement.

## Installation

For Workshop installation, subscribe, wait for Steam to download and restart the game. Remove any separate local WorkerOptimizer installation first.

For manual installation, close Whiskerwood before installing or replacing the mod. Place the packaged files in this directory:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\mods\WorkerOptimizer\
  WorkerOptimizer.pak
  WorkerOptimizer.uplugin
```

Start the game and load a settlement. The action button and settings gear appear in the lower-left corner.

The packaged mod does not require Python, Unreal Editor or the development tools. To uninstall, close the game and remove only the `WorkerOptimizer` folder from `mods`. Do not remove any save files.

## Usage

Click the arrow button to run the optimizer. Click it again during a run to cancel further changes. Cancellation does not undo assignments already completed by the game.

**Ctrl + Alt + O** hides or shows the controls without changing assignments. Use the adjacent gear to change this shortcut. Assignment preferences are in the game's **Settings > Mods** menu.

| Setting | Behavior |
| --- | --- |
| Assignment mode: strict | Higher priority tiers take precedence over lower tiers after minimum-crew selection. |
| Assignment mode: weighted | Priorities influence the productivity score, allowing trade-offs between priorities and productivity. |
| Residents kept free for building | Minimum number of eligible residents to leave unassigned. This reserve takes precedence over building staffing. |
| Category priority | Sets a default priority from Very low to Very high. |
| Building-type priority | Overrides the category for every building of that type, or inherits the category setting. |

The reserve counts eligible, movable residents only. Workers protected in paused or unsupported buildings do not count toward it, and construction-yard employees are not unassigned builders. If fewer eligible residents are available than requested, all available residents remain free.

For example, with five available residents and three buildings that each need one worker to operate, a reserve of two leaves one worker in each building. A higher-priority building does not take a second worker at the expense of another building's feasible minimum crew. If there are too few eligible residents to supply all minimum crews, priorities determine which crews can be staffed.

Global game pause also pauses the optimizer. Resume the simulation to let a queued run complete. The visibility shortcut works while paused.

The mod follows the game language and falls back to English for unsupported languages. Dutch translations are included, but Whiskerwood 0.7.209.0 does not offer Dutch in its language menu. There is no separate mod language selector.

## How It Works

The runtime is implemented in Unreal Engine Blueprints and UMG widgets, built with the [Whiskerwood modkit](https://github.com/Whiskerwood-Modding/Whiskerwood-Project). Python scripts author and test the Blueprint assets in the editor; they are not part of the running mod.

Each run has five stages:

1. **Capture the settlement.** Read player-owned workplaces, their slots and current occupants, then collect eligible residents. Exclude paused or unsupported workplaces and protect their occupants.
2. **Score possible assignments.** Check education and role requirements, then calculate productivity for each hypothetical workplace. Employment-dependent modifiers are adjusted for the destination instead of blindly reusing the resident's current displayed productivity. School assignments use teacher/student eligibility and learning-rate scoring.
3. **Plan staffing.** Reserve the requested free residents, select feasible minimum crews, then fill additional positions according to the selected priority mode. The assignment solver uses a shortest-augmenting-path approach; strict tiers retain earlier optimal results while resolving later tiers. Empty slots are represented explicitly.
4. **Validate the result.** Reject duplicate assignments, invalid roles and inconsistent snapshots before applying changes. Teacher-dependent school assignments are checked as complete plans.
5. **Apply and confirm.** Send the game's native fire/hire actions one at a time and check the actual workplace and slot after each action. Stop on an unexpected state change or timeout. The mod does not directly overwrite the game's workforce arrays.

Among otherwise equal production outcomes, the reserve selection favors residents with better neutral productivity, carrying capacity and movement speed. This is a tie-breaking heuristic, not a prediction of exact construction time.

Planning advances incrementally across ticks. A map-load session owns the controller, action bridge and widget, prevents duplicate controls and cleans up its references when the world ends. Loading a save never starts an optimization automatically.

Startup listens for the native load-completion event and also checks `ProjectArcoGameModeBase.CurrentInitPhase`. Once the phase is `DONE` and a player controller exists, a missing event no longer prevents session creation. The fallback is checked at half-second intervals and stops once the session is ready; it never triggers optimization.

The controls use viewport dimensions divided by Unreal's current DPI scale. Below 1600 logical units of width they move upward to clear the bottom toolbar. The hotkey panel is constrained to the available width. Placement refreshes after resolution or DPI changes without resizing either icon. Other mods' overlays are not automatically detected.

### Update Compatibility

Building types, guild specialties, slot layouts and category identifiers come from game data. Priorities use stable internal identifiers rather than translated building names. New building types using supported workplace components can therefore participate without adding their names to the mod.

The workplace adapter and native action bridge are version-sensitive. A new component implementation or changed game API may still require an update. Unknown workplaces are preserved rather than assigned using guessed rules. Newly discovered types initially inherit their category priority; changes to their new settings take effect on the next run.

### Source Layout

```text
Content/Mods/WorkerOptimizer/     Blueprint assets, widgets and mod descriptor
Automation/WorkerOptimizer/      Asset generators, tests and packaging scripts
Plugins/WorkerOptimizerEditor/   Editor-only authoring and test support
```

`BP_WorkforceSnapshot` and `BP_WorkplaceAdapter` handle discovery. `BP_JobEligibility` and `BP_JobScorer` provide eligibility and scoring. `BP_StaffingPlanner`, `BP_AssignmentSolver` and `BP_PlanSearch` produce the plan. `BP_ActionPlan`, `BP_ActionBridge` and `BP_ApplicationRunner` validate and apply it. `BP_PrioritySettings`, `BP_HotkeyConfig`, `BP_Startup`, `BP_MapLoad` and `WBP_WorkerOptimizer` handle preferences and the user interface.

The editor helper is a development dependency only. It is excluded from the packaged mod. Runtime assets reference existing game content; the mod package does not bundle the game or Unreal Engine.

## Building and Testing

Set up the official modkit and its required custom Unreal Engine build first, following the [modkit setup instructions](https://github.com/Whiskerwood-Modding/Whiskerwood-Project#setup). An installed copy of Whiskerwood is required. The tested development environment used the custom Unreal Engine 5.8.3 build on Windows and modkit commit `a1a958377bda68a12a7749faf477de7514042984`.

Use this source as an overlay on a separate modkit checkout, preserving the directories shown above. Build the editor-only `WorkerOptimizerEditor` plugin as part of the project and ensure it is enabled. Open the project with the required custom engine; a stock engine installation is not a substitute.

Copy `Content/Mods/WorkerOptimizer`, `Automation/WorkerOptimizer` and `Plugins/WorkerOptimizerEditor` into the corresponding modkit directories. Also copy `docs/WorkerOptimizer/SPIELTEST.md` to `Docs/WorkerOptimizer/SPIELTEST.md`; the packaging script includes this checklist beside the deliverable. Do not replace the modkit's root README or license. No game content, engine binaries or locally built editor binaries are included in this repository.

The optional `inspect_native.py` investigation helper needs `capstone` and `pefile` under `Intermediate/WorkerOptimizerTools`. It is not required for building or playing the mod. The other editor scripts use the modkit's bundled tooling.

From the modkit root, with the engine path adjusted for your installation:

```powershell
./Automation/WorkerOptimizer/Test-Mod.ps1 -EngineRoot 'D:\WWEngine'
./Automation/WorkerOptimizer/Build-Mod.ps1 -EngineRoot 'D:\WWEngine'
```

The build script runs the test suites, performs a full cook and verifies the mod package's content inventory and integrity. It does not install or publish the mod. It packages the existing Blueprint assets; changes to generator scripts must first be applied to those assets in the editor.

The installable output is:

```text
Saved/WorkerOptimizerBuilds/<build-id>/Delivery/WorkerOptimizer/
```

Only the `.pak` and `.uplugin` files in that folder are installation inputs. The larger intermediate Windows archive is not a standalone game and must not be distributed as one.

## Verification and Known Limits

The 30 automated suites cover assignment planning, priorities, minimum crews, protected workers, reserve selection, localization, settings migration, hotkeys, lifecycle and action confirmation. Reserve tests include 72 exhaustive-oracle cases. Startup/layout regressions cover missed events and 30 viewport/DPI combinations; native render checks cover five logical sizes from 400x300 to 3440x1440 in idle and settings states. Editor tests cannot prove native game behavior because the modkit contains native-function stubs.

Live testing on 5 October 2026 confirmed:

- Reserves of 0, 1 and 2 produced the expected number of free residents in a five-resident settlement, with all three workplaces staffed.
- Appropriate guild assignments were visible in resident profiles, including the game's +50 guild-specialty productivity contribution.
- The visibility shortcut worked while paused and persisted across restart.
- English, German, French and Polish settings refreshed correctly after changing the game language.

Remaining limits include large-city performance, complex school configurations, special bonus-slot production effects, live priority trade-offs and workplace changes during queued actions. Exact school search can become expensive as the number of distinct teacher choices grows.

The optimizer maximizes its staffing and productivity objectives, not total economic value, resource balance or travel efficiency. Keeping residents free does not guarantee construction progress when materials or other game conditions prevent building.

## Reporting Problems

Include the game version, other active mods, resident/building/school counts, reserve and priority settings, the expected result, the actual result and the button tooltip. Before/after screenshots of assignments are useful.

The game's mod log is located at:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\Logs\modlog.txt
```

Relevant entries begin with `WorkerOptimizer` or `Worker Optimizer`. Review logs for personal information before sharing them. Do not upload your entire save or log directory.

## Acknowledgments

Built using the Whiskerwood modkit by Buckminsterfullerene and Whiskerwood-Modding. Whiskerwood and its game assets belong to their respective owners. This is an unofficial community mod.
