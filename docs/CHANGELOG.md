# Changelog

## 0.3.0-preview - 7 October 2026

Single-icon preview. In-game validation is pending and will be performed by the user. Workshop files are prepared separately; no Workshop submission is included in this release workflow.

- Show only the manual assignment icon. Settings, priorities and logbook views remain in the code/assets but cannot be opened.
- Keep the icon visible and disable former visibility shortcuts, including saved bindings.
- Disable automatic schedules, including schedules saved by earlier releases.
- Ignore saved priority overrides and strict/weighted mode selections. Active supported buildings use the same priority.
- Preserve the saved builder reserve, or use the default of one when no value is saved. There is no reserve editor in this preview.
- Select feasible minimum crews before filling extra positions by worker suitability, subject to reserve and eligibility constraints.
- Apply dependency moves instead of a global fire-all batch: release the workers needed for the next target and its native dependencies, then hire.
- Account for the game's required-worker dismissal rule, which also clears optional workers. Explicitly release movable optional workers first and schedule their planned assignments afterward; keep required incumbents fixed where changing them would dismiss protected optional occupants.
- Check supported native assignment effects immediately after the call returns. Count only observed effects and release the request lock after terminal result processing; returned native failures cannot leave a persistent waiting state.
- Revise native assignment request handling. This change still needs acceptance in the shipping game; it does not guarantee every requested assignment will succeed.

See [preview validation and limits](releases/v0.3.0-preview.md).

## 0.2.1-hotfix.1 - 6 October 2026

Pre-release assignment recovery hotfix. In-game acceptance is pending.

- Automatically replan after a delayed native confirmation, within the existing two-replan limit.
- End unresolved manual and automatic requests with a visible failure and logbook entry instead of an endless busy indicator.
- Keep unconfirmed commands locked against duplicate dispatch, including after terminal failure.
- Fix recoverable pre-dispatch rejection matching and add targeted timeout diagnostics.
- Preserve priorities, builder reserve, assignment rules and the per-frame work budget.

See [hotfix validation and limits](releases/0.2.1-hotfix.1.md).

## 0.2.0 - 6 October 2026

First regular [GitHub release](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.2.0), available as [WorkerOptimizer-v0.2.0.zip](https://github.com/repte/whiskerwood-worker-optimizer/releases/download/v0.2.0/WorkerOptimizer-v0.2.0.zip) and on Steam Workshop. See [release validation](PREVIEW.md).

- Redesigned the native UMG interface with responsive General, Priorities and Logbook tabs, searchable building priorities and expandable categories.
- Added optional automatic assignment at day start or every 5, 10 or 15 real-time minutes. Automatic assignment defaults to Off. Paused time counts toward minute intervals; due work waits until resume without accumulating missed runs.
- Added a logbook with results, confirmed changes, grouped reasons and All/Problems filters. History retains up to 50 runs per identified save slot, separately from the game save.
- Expanded localization to all 17 game languages, including regional Chinese and Spanish entries, with English fallback.
- Extended minimum-crew planning to workplaces whose initial worker can occupy any eligible slot. Feasible crews are selected in priority order before additional workers; the builder reserve and native role requirements remain binding.
- Capture scoring values once per plan so ordinary speed/productivity fluctuations do not abort a request. Relevant workplace or eligibility changes allow at most two automatic replans using the same settings and logbook entry.
- Keep the start button locked with a busy indicator throughout a request. Additional clicks do not restart or cancel it. Confirmed changes are retained; unresolved native commands prevent overlapping requests.
- Fixed native logbook selection and category expansion events in local.7, aligned history columns, and improved panel text size and scrolling at reduced game UI scale.
- Expanded automated coverage for scheduling, history, localization, assignment changes and native UI events; hardened package checks to reject editor helpers and test probes.

Validation on 6 October 2026: the complete automated test run, full cook and package checks passed. Four native UMG frames with synthetic editor data passed interaction and geometry checks and were visually reviewed. The author confirmed the final shipping-game test of **0.2.0-local.7** passed. The release uses the byte-identical tested PAK, with only descriptor version and description metadata changed for **0.2.0**. Large-settlement performance, all-language presentation, extended sessions and broader live workflows still need further validation.

## 0.1.1-dev

Earlier development release, superseded by 0.2.0.

- Added a startup fallback for new colonies and missed load-completion events. It waits for the game's completed initialization phase and a valid player controller.
- Made the controls adapt to viewport size and DPI, moving above the bottom toolbar on compact layouts.
- Kept the hotkey panel within the viewport and enabled wrapping labels.
- Added startup and layout regressions plus native widget pixel checks.
- Assignment rules, construction reserve and hotkeys are unchanged.

Validation at release: automated suites and 10 native widget pixel checks passed; the startup/layout repair had not yet completed in-game validation.

## 0.1.0-dev

Initial development release: guild-aware assignment, minimum operating crews, configurable builder reserve, strict/weighted priorities, protected workplaces and localized settings.
