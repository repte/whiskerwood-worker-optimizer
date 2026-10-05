<div align="center">

# Worker Optimizer

**Better job matches. Free builders. One click.**

A worker-assignment mod for **Whiskerwood**.

![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D4)
![Tested game version: 0.7.209.0](https://img.shields.io/badge/tested_on-0.7.209.0-2E8B57)
![Status: Development](https://img.shields.io/badge/status-development-D99A20)

[Download](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.1.0-dev) · [Documentation](docs/GUIDE.md) · [How it works](docs/GUIDE.md#how-it-works) · [Build from source](docs/GUIDE.md#building-and-testing)

</div>

## At a Glance

- **Match skills to jobs:** assign residents using guild specialties, productivity and eligibility.
- **Keep construction staffed:** leave a configurable reserve free. Default **1**; **0** disables it.
- **Cover the basics first:** minimum operating crews before extra workers, subject to the reserve and eligibility.
- **Set your priorities:** strict or weighted mode, category priorities and building-type overrides.
- **Leave protected workers alone:** paused and unsupported workplaces are skipped.

No background rebalancing. New building types are discovered from game data; unfamiliar workplace implementations may still need a mod update.

## Install

Download **WorkerOptimizer-v0.1.0-dev.zip** from [Releases](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.1.0-dev), not the source-code ZIP. Close the game and extract its `WorkerOptimizer` folder into `mods`:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\mods\WorkerOptimizer\
  WorkerOptimizer.pak
  WorkerOptimizer.uplugin
```

No Python or Unreal Editor needed to play. **Steam Workshop release pending.**

## Play

| Control | Action |
| :--- | :--- |
| Arrow button, lower left | Optimize once; click again during a run to cancel further changes |
| **Ctrl + Alt + O** | Show/hide controls; rebind through the gear |
| **Settings > Mods** | Set the free-builder reserve and assignment priorities |

Resume the simulation to process assignments. Cancellation does not undo completed changes.

**Languages:** English, German, Polish and French follow the game language. Dutch is prepared, but not selectable in the current game's language menu.

> [!IMPORTANT]
> **Development build: use a separate test save.** 29 automated suites and a small-settlement live test passed. Large cities and special roles need broader testing. See [verification and limits](docs/GUIDE.md#verification-and-known-limits).

---

Unofficial community mod built with the [Whiskerwood modkit](https://github.com/Whiskerwood-Modding/Whiskerwood-Project) by Buckminsterfullerene and Whiskerwood-Modding. Game assets belong to their respective owners.

[MIT license](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)
