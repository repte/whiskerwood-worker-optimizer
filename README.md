<div align="center">

<img src="docs/assets/worker-optimizer.png" alt="Worker Optimizer: auto-assign workers to their best jobs" width="360">

# Worker Optimizer

**Auto-assign workers to their best jobs.**

Automatically assign **Whiskerwood** residents to suitable buildings with **one click**, matching guild specialties and productivity while keeping builders free.

![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D4)
![Tested game version: 0.7.209.0](https://img.shields.io/badge/tested_on-0.7.209.0-2E8B57)
![Status: Development](https://img.shields.io/badge/status-development-D99A20)

[Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514) · [Download](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.1.1-dev) · [Documentation](docs/GUIDE.md) · [How it works](docs/GUIDE.md#how-it-works)

</div>

**Published release: v0.1.1-dev.** Workshop and the download above still provide this version. This repository also contains the **unreleased 0.2.0-local.7 source preview**, whose final in-game test is in progress.

## At a Glance

- **Match skills to jobs:** assign residents using guild specialties, productivity and eligibility.
- **Keep construction staffed:** leave a configurable reserve free. Default **1**; **0** disables it.
- **Cover the basics first:** select feasible minimum crews in priority order, then fill extra positions, subject to the reserve and eligibility.
- **Set your priorities:** strict or weighted mode, category priorities and building-type overrides.
- **Leave protected workers alone:** paused and unsupported workplaces are skipped.

Building types are discovered from game data; unfamiliar workplace implementations may still need a mod update.

## Source Preview: 0.2.0

- **A redesigned interface:** responsive General, Priorities and Logbook tabs, searchable building priorities and run details.
- **Your schedule:** run once or enable assignment at day start or every 5, 10 or 15 real-time minutes. Automatic assignment is off by default; paused games wait until resume.
- **17 game languages:** follows the game's language, with English fallback. See the [language list](docs/GUIDE.md#languages).

One request stays active through at most two automatic replans. The start button stays locked while busy; extra clicks neither cancel nor restart it. These features are **not yet in the published release**. See [preview status and testing](docs/PREVIEW.md).

## Install

Subscribe on [Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514), wait for the download, then restart the game. Remove any separate local installation first.

For manual installation, download **WorkerOptimizer-v0.1.1-dev.zip** from [Releases](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.1.1-dev), not the source-code ZIP. Close the game and extract its `WorkerOptimizer` folder into `mods`:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\mods\WorkerOptimizer\
  WorkerOptimizer.pak
  WorkerOptimizer.uplugin
```

No Python or Unreal Editor needed to play. Use either Workshop or manual installation, not both.

## Play

| Control | Action |
| :--- | :--- |
| Arrow button, lower left | Optimize once |
| **Ctrl + Alt + O** | Show/hide controls; rebind through the gear |
| Gear | Hotkey settings in v0.1.1-dev; General, Priorities and Logbook tabs in the source preview |
| **Settings > Mods** | Set the free-builder reserve and assignment priorities in v0.1.1-dev |

Resume the simulation to process assignments. In the source preview, use the gear or logbook button to inspect settings and run results.

> [!IMPORTANT]
> **Development build: use a separate test save.** Automated tests, UI checks and packaging passed on 6 October 2026. The final in-game test of 0.2.0-local.7 is in progress. See [changes](docs/CHANGELOG.md) and [limits](docs/GUIDE.md#verification-and-known-limits).

---

Unofficial community mod built with the [Whiskerwood modkit](https://github.com/Whiskerwood-Modding/Whiskerwood-Project) by Buckminsterfullerene and Whiskerwood-Modding. Game assets belong to their respective owners.

[MIT license](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)
