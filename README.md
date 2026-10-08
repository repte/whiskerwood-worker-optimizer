<div align="center">

<img src="docs/assets/worker-optimizer.png" alt="Worker Optimizer: auto-assign workers with one click" width="360">

# Worker Optimizer

**Auto-assign your Whiskerwood workers to suitable jobs with one click.**

![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D4)
![Version: v0.3.3-performance-preview](https://img.shields.io/badge/version-v0.3.3--performance--preview-d99020)

[Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514) · [GitHub release](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.3.3-performance-preview) · [Preview notes](docs/releases/v0.3.3-performance-preview.md) · [Documentation](docs/GUIDE.md)

</div>

## At a Glance

- **One-click assignment:** evaluate your current settlement and assign workers from an icon in the gameplay HUD.
- **Better job matches:** consider each resident's guild specialty, productivity and job requirements.
- **Minimum crews first:** fill feasible minimum crews before adding suitable workers to extra positions.
- **Construction reserve:** keep residents available for building, using your saved reserve or **1 resident** by default.
- **Preserve protected workers:** leave paused buildings and unsupported warehouse workplaces unchanged.
- **Faster exact planning:** reduce repeated work without replacing the existing exact assignment approach.

## Play

Click the assignment icon in the lower-left corner. Worker Optimizer evaluates the current workforce, prioritizes minimum crews and then fills extra positions. The icon shows when assignment is running and becomes available again when the run ends.

The icon uses the same native gameplay-HUD visibility checks as the Campfire Panel mod: it belongs to the gameplay layer, hides in menus and while the HUD is hidden, loading or saving, and is not hidden merely by pausing the simulation or reaching the end of day. Hiding the icon does not cancel a running assignment.

> [!WARNING]
> For best results, run worker assignment calculations at night or just after a new day starts. Running them during the day may cause assignment errors.

> [!NOTE]
> **Version: v0.3.3-performance-preview**, targeting Whiskerwood **0.7.209.0 on Windows**. The Workshop update is prepared, not submitted. Public in-game acceptance remains pending; use a separate save. See [preview details](docs/releases/v0.3.3-performance-preview.md).

Six compiled-editor planner benchmarks with 1,000 workers took **5.61-14.55 seconds** on the test machine. These measure planner calls, not the entire in-game operation, and are not a runtime guarantee. [Measurements and limits](docs/verification/2026-10-08-large-settlements.md).

## Install

**Steam Workshop:** [Worker Optimizer](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514) currently offers **v0.3.1-preview**. The **v0.3.3-performance-preview** update is prepared, not submitted. Restart the game after Steam downloads an update.

**Manual installation:** Use the packaged [WorkerOptimizer-v0.3.3-performance-preview.zip](https://github.com/repte/whiskerwood-worker-optimizer/releases/download/v0.3.3-performance-preview/WorkerOptimizer-v0.3.3-performance-preview.zip), not the source-code ZIP. Close the game and extract its `WorkerOptimizer` folder here:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\mods\WorkerOptimizer\
  WorkerOptimizer.pak
  WorkerOptimizer.uplugin
```

No Python or Unreal Editor is needed. Use either the local package or the Workshop subscription, never both.

[Guide and troubleshooting](docs/GUIDE.md) · [Changelog](docs/CHANGELOG.md)

---

Unofficial community mod built with the [Whiskerwood modkit](https://github.com/Whiskerwood-Modding/Whiskerwood-Project) by Buckminsterfullerene and Whiskerwood-Modding. Game assets belong to their respective owners.

[MIT license](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)

[![DuoQueue](https://duoqueue.app/promo/duoq-workshop-banner-whiskerwood.png)](https://duoqueue.app/en/)
