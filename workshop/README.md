# Workshop Update: v0.3.0-preview

**Prepared, not submitted.** These files are ready for the user's manual update of the existing Workshop item. Preparing this folder does not publish or change the live item.

- App ID: `2489330`
- Existing item ID: `3814077514`
- Title: `Worker Optimizer`
- [Workshop page](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514)
- Visibility: Public
- Current tags: Feature Addition, Quality of Life, Worker Management, Mod, Assignment, Auto, Work

Use only the v0.3.0-preview build's `WorkerOptimizer.pak` and `WorkerOptimizer.uplugin` after the current package verification passes. Update item `3814077514`; do not create another item. Keep the current title, visibility and tags.

Use `description.bbcode` for the description, `changenotes.txt` for the update notes, and the existing `preview.jpg` emblem for the preview. Keep this JPEG unchanged. `Prepare-Preview.ps1` is retained as a helper but is not needed for this update.

This preview exposes only the always-visible manual assignment icon. Settings and logbook code/assets remain present but inaccessible; saved automatic schedules and visibility shortcuts are disabled. Old priority overrides and strict/weighted mode selections are ignored, while the saved builder reserve is respected. Feasible minimum crews are selected before best-fit extra staffing. Moves account for native dependencies instead of using a global fire-all batch. Replacing a required worker explicitly handles affected optional workers; protected optional occupants keep the corresponding required incumbents fixed.

**In-game acceptance is pending and will be performed by the user.** Earlier release tests do not validate this package or its changed native assignment request path. Confirm the current automated and package verification results separately. Supported native effects are checked immediately after each call returns, and only observed effects are counted. Rejection or a missing observed effect ends the request without a persistent lock after result processing. This preview does not guarantee successful live assignment.

Documentation and source: [GitHub](https://github.com/repte/whiskerwood-worker-optimizer).
