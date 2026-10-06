# Changelog

## 0.2.0 Source Preview (Unreleased)

Current source version: **0.2.0-local.7**, 6 October 2026. Workshop and the published download remain **v0.1.1-dev**. This entry describes source changes, not a new downloadable release. See [preview status and testing](PREVIEW.md).

- Redesigned the native UMG interface with responsive General, Priorities and Logbook tabs, searchable building priorities and expandable categories.
- Added optional automatic assignment at day start or every 5, 10 or 15 real-time minutes. Automatic assignment defaults to Off. Paused time counts toward minute intervals; due work waits until resume without accumulating missed runs.
- Added a logbook with results, confirmed changes, grouped reasons and All/Problems filters. History retains up to 50 runs per identified save slot, separately from the game save.
- Expanded localization to all 17 game languages, including regional Chinese and Spanish entries, with English fallback.
- Extended minimum-crew planning to workplaces whose initial worker can occupy any eligible slot. Feasible crews are selected in priority order before additional workers; the builder reserve and native role requirements remain binding.
- Capture scoring values once per plan so ordinary speed/productivity fluctuations do not abort a request. Relevant workplace or eligibility changes allow at most two automatic replans using the same settings and logbook entry.
- Keep the start button locked with a busy indicator throughout a request. Additional clicks do not restart or cancel it. Confirmed changes are retained; unresolved native commands prevent overlapping requests.
- Fixed native logbook selection and category expansion events in local.7, aligned history columns, and improved panel text size and scrolling at reduced game UI scale.
- Expanded automated coverage for scheduling, history, localization, assignment changes and native UI events; hardened package checks to reject editor helpers and test probes.

Validation on 6 October 2026: the complete automated test run, full cook and package checks passed. Four native UMG frames with synthetic editor data passed interaction and geometry checks and were visually reviewed. The final shipping-game test of **0.2.0-local.7 is in progress**. Large-settlement performance, all-language presentation and broader live workflows remain to be validated.

## 0.1.1-dev

Published Workshop and downloadable release.

- Added a startup fallback for new colonies and missed load-completion events. It waits for the game's completed initialization phase and a valid player controller.
- Made the controls adapt to viewport size and DPI, moving above the bottom toolbar on compact layouts.
- Kept the hotkey panel within the viewport and enabled wrapping labels.
- Added startup and layout regressions plus native widget pixel checks.
- Assignment rules, construction reserve and hotkeys are unchanged.

Validation at release: automated suites and 10 native widget pixel checks passed; the startup/layout repair had not yet completed in-game validation.

## 0.1.0-dev

Initial development release: guild-aware assignment, minimum operating crews, configurable builder reserve, strict/weighted priorities, protected workplaces and localized settings.
