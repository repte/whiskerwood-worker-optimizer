<div align="center">

<img src="docs/assets/worker-optimizer.png" alt="Worker Optimizer: assign workers with one manual icon" width="360">

# Worker Optimizer

**Assign Whiskerwood workers to suitable jobs with one click.**

![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D4)
![Preview: v0.3.0-preview](https://img.shields.io/badge/preview-v0.3.0--preview-d99020)

[Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514) · [Download preview](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.3.0-preview) · [Documentation](docs/GUIDE.md) · [How it works](docs/GUIDE.md#how-it-works)

</div>

**v0.3.0-preview** targets Whiskerwood **0.7.209.0 on Windows**. **The user's in-game test is pending.** The Workshop upload is prepared separately and **not submitted**; the GitHub preview does not update the live Workshop item.

## At a Glance

- **One manual icon:** always visible, with no settings gear, logbook view, visibility shortcut or automatic schedule.
- **Minimum crews first:** cover feasible operating crews before filling extra positions by guild specialty, productivity and eligibility.
- **Equal building priority:** old category priorities, building overrides and strict/weighted choices are ignored.
- **Saved builder reserve:** keep the existing reserve, or **1** when unset; **0** disables it. This preview has no reserve editor.
- **Protected workers:** paused and unsupported workplaces are left alone. Native dismissal dependencies are handled explicitly.

The former settings and logbook code/assets remain present but inaccessible. See [preview changes and limits](docs/releases/v0.3.0-preview.md).

## Install

Download **[WorkerOptimizer-v0.3.0-preview.zip](https://github.com/repte/whiskerwood-worker-optimizer/releases/download/v0.3.0-preview/WorkerOptimizer-v0.3.0-preview.zip)**, not the source-code ZIP. Close the game and extract its `WorkerOptimizer` folder here:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\mods\WorkerOptimizer\
  WorkerOptimizer.pak
  WorkerOptimizer.uplugin
```

No Python or Unreal Editor is needed. Use either the local package or the [Workshop subscription](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514), never both. Steam installs only the version actually submitted there.

## Play

Click the lower-left assignment icon once. It stays busy until the request completes; extra clicks do not restart or cancel it. Only observed effects count, and a returned failure does not leave a persistent lock after result processing.

> [!WARNING]
> For best results, run worker assignment calculations at night or just after a new day starts. Running them during the day may cause assignment errors.

Use a separate test save and check workers in the game's building and resident windows. Shortages and eligibility can leave buildings unstaffed; confirmed changes are not automatically rolled back. [Guide and troubleshooting](docs/GUIDE.md) · [Changelog](docs/CHANGELOG.md)

---

Unofficial community mod built with the [Whiskerwood modkit](https://github.com/Whiskerwood-Modding/Whiskerwood-Project) by Buckminsterfullerene and Whiskerwood-Modding. Game assets belong to their respective owners.

[MIT license](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)

[![DuoQueue](https://duoqueue.app/promo/duoq-workshop-banner-whiskerwood.png)](https://duoqueue.app/en/)
