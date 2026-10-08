# Prepared Workshop Update: v0.3.3-performance-preview

**Prepared, not submitted.** This folder contains the copy for the next update to the existing Workshop item. Version: [v0.3.3-performance-preview](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.3.3-performance-preview); package: [WorkerOptimizer-v0.3.3-performance-preview.zip](https://github.com/repte/whiskerwood-worker-optimizer/releases/download/v0.3.3-performance-preview/WorkerOptimizer-v0.3.3-performance-preview.zip). The live Workshop version remains v0.3.1-preview. Public in-game acceptance remains pending.

- App ID: `2489330`
- Existing item ID: `3814077514`
- Title: `Worker Optimizer`
- [Workshop page](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514)
- Visibility: Public
- Current tags: Feature Addition, Quality of Life, Worker Management, Mod, Assignment, Auto, Work

Use the verified v0.3.3-performance-preview delivery from combined build `20261008-115852-7696bc58`: `WorkerOptimizer.pak` and `WorkerOptimizer.uplugin`, including the gameplay-layer icon fix. Its complete editor suite, Windows Shipping cook and package checks passed on 8 October 2026. The PAK contains 46 runtime assets / 92 entries (557,151 bytes), SHA256 `BF93CC988DEE20DD02C89C287A1F84D8834DD5CA89FFE1D8A355BB9AD86F4843`. See the [combined verification record](../docs/verification/2026-10-08-gameplay-visibility.md). Update item `3814077514`; do not create another item. Keep the current title, visibility and tags.

Use `description.bbcode` for the description, `changenotes.txt` for the update notes, and the existing `preview.jpg` emblem for the preview. Keep this JPEG unchanged. `Prepare-Preview.ps1` is retained as a helper but is not needed for this update.

This preview keeps the existing exact assignment approach, feasible minimum crews, protected workers and the saved construction reserve. Six compiled-editor 1,000-worker planner cases measured 5.61-14.55 seconds on the test machine. These are planner-call timings, not guaranteed total in-game duration. See the [performance evidence](../docs/verification/2026-10-08-large-settlements.md).

The assignment icon uses the same native gameplay-HUD visibility checks as the Campfire Panel mod: visible only in the gameplay layer, hidden in menus, with hidden HUD, during loading or saving, and in replay. Simulation pause and end of day do not themselves hide it. Hiding the icon does not cancel or restart an active request.

Back up the existing WorkerOptimizer uploader configuration and payload, replace only this mod's files with the verified delivery, and preserve the item ID and JPEG. **Preparation stops before Upload; no Workshop publication is authorized by this preparation step.** After an actual submission, update the publication status separately.

**Public in-game acceptance is pending and will be performed by the user.** Test a separate save, preferably at night or just after a new day starts; daytime assignment may cause errors. Include gameplay-layer visibility, request continuity while hidden and complete large-settlement runtime. Editor and package checks do not guarantee successful live assignment.

Documentation and source: [GitHub](https://github.com/repte/whiskerwood-worker-optimizer).
