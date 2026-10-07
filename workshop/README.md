# Workshop Update: v0.3.1-preview

**Prepared, not submitted.** These files are ready for the user's manual update of the existing Workshop item. Preparing this folder does not publish or change the live item.

- App ID: `2489330`
- Existing item ID: `3814077514`
- Title: `Worker Optimizer`
- [Workshop page](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514)
- Visibility: Public
- Current tags: Feature Addition, Quality of Life, Worker Management, Mod, Assignment, Auto, Work

Use only the final, verified v0.3.1-preview delivery's `WorkerOptimizer.pak` and `WorkerOptimizer.uplugin`. Update item `3814077514`; do not create another item. Keep the current title, visibility and tags.

Use `description.bbcode` for the description, `changenotes.txt` for the update notes, and the existing `preview.jpg` emblem for the preview. Keep this JPEG unchanged. `Prepare-Preview.ps1` is retained as a helper but is not needed for this update.

This preview keeps one-click assignment, feasible minimum crews before extra staffing, and the saved construction reserve. It now skips the unsupported native ResourceBuilding family, including GranaryResourceBuilding used by prefab `tinywarehouse`, and preserves their existing occupants. This avoids the specific rejected hire that could stop a run at those workplaces.

The focused workplace tests, full automated editor suite, Windows cook and package checks passed for this fix; see the [verification record](../docs/verification/2026-10-07-native-workplace-capability.md). Final delivery packaging uses the new external version metadata.

**In-game acceptance is pending and will be performed by the user.** Test a separate save, preferably at night or just after a new day starts; daytime assignment may cause errors. These checks do not guarantee successful live assignment. Nothing in this folder submits the Workshop update.

Documentation and source: [GitHub](https://github.com/repte/whiskerwood-worker-optimizer).
