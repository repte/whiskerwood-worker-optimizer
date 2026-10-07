<div align="center">

<img src="docs/assets/worker-optimizer.png" alt="Worker Optimizer: auto-assign workers with one click" width="360">

# Worker Optimizer

**Auto-assign your Whiskerwood workers to suitable jobs with one click.**

![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D4)
![Preview: v0.3.1-preview](https://img.shields.io/badge/preview-v0.3.1--preview-d99020)

[Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514) · [Download preview](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.3.1-preview) · [Documentation](docs/GUIDE.md) · [How it works](docs/GUIDE.md#how-it-works)

</div>

## At a Glance

- **One-click assignment:** evaluate your current settlement and assign workers from an always-visible icon.
- **Better job matches:** consider each resident's guild specialty, productivity and job requirements.
- **Minimum crews first:** fill feasible minimum crews before adding suitable workers to extra positions.
- **Construction reserve:** keep residents available for building, using your saved reserve or **1 resident** by default.
- **Preserve protected workers:** leave paused buildings and unsupported warehouse workplaces unchanged.

## Play

Click the assignment icon in the lower-left corner. Worker Optimizer evaluates the current workforce, prioritizes minimum crews and then fills extra positions. The icon shows when assignment is running and becomes available again when the run ends.

> [!WARNING]
> For best results, run worker assignment calculations at night or just after a new day starts. Running them during the day may cause assignment errors.

> [!NOTE]
> **v0.3.1-preview** targets Whiskerwood **0.7.209.0 on Windows**. In-game validation is pending, so try a separate save first. Staffing depends on available workers and job requirements. See [preview details](docs/releases/v0.3.1-preview.md).

## Install

Download **[WorkerOptimizer-v0.3.1-preview.zip](https://github.com/repte/whiskerwood-worker-optimizer/releases/download/v0.3.1-preview/WorkerOptimizer-v0.3.1-preview.zip)**, not the source-code ZIP. Close the game and extract its `WorkerOptimizer` folder here:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\mods\WorkerOptimizer\
  WorkerOptimizer.pak
  WorkerOptimizer.uplugin
```

No Python or Unreal Editor is needed. Use either the local package or the [Workshop subscription](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514), never both. This Workshop update is prepared, not submitted; Steam installs only the version actually published there.

[Guide and troubleshooting](docs/GUIDE.md) · [Changelog](docs/CHANGELOG.md)

---

Unofficial community mod built with the [Whiskerwood modkit](https://github.com/Whiskerwood-Modding/Whiskerwood-Project) by Buckminsterfullerene and Whiskerwood-Modding. Game assets belong to their respective owners.

[MIT license](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)

[![DuoQueue](https://duoqueue.app/promo/duoq-workshop-banner-whiskerwood.png)](https://duoqueue.app/en/)
