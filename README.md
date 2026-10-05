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

## At a Glance

- **Match skills to jobs:** assign residents using guild specialties, productivity and eligibility.
- **Keep construction staffed:** leave a configurable reserve free. Default **1**; **0** disables it.
- **Cover the basics first:** minimum operating crews before extra workers, subject to the reserve and eligibility.
- **Set your priorities:** strict or weighted mode, category priorities and building-type overrides.
- **Leave protected workers alone:** paused and unsupported workplaces are skipped.

**You choose when:** click to auto-assign once. No continuous background reassignment. Building types are discovered from game data; unfamiliar workplace implementations may still need a mod update.

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
| Arrow button, lower left | Optimize once; click again during a run to cancel further changes |
| **Ctrl + Alt + O** | Show/hide controls; rebind through the gear |
| **Settings > Mods** | Set the free-builder reserve and assignment priorities |

Resume the simulation to process assignments. Cancellation does not undo completed changes.

**Languages:** English, German, Polish and French follow the game language. Dutch is prepared, but not selectable in the current game's language menu.

> [!IMPORTANT]
> **Development build: use a separate test save.** 30 automated suites pass. Core assignment was live-tested in a small settlement; the 0.1.1 startup/layout repair still needs an in-game test. See [changes](docs/CHANGELOG.md) and [limits](docs/GUIDE.md#verification-and-known-limits).

---

Unofficial community mod built with the [Whiskerwood modkit](https://github.com/Whiskerwood-Modding/Whiskerwood-Project) by Buckminsterfullerene and Whiskerwood-Modding. Game assets belong to their respective owners.

[MIT license](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)
