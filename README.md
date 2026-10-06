<div align="center">

<img src="docs/assets/worker-optimizer.png" alt="Worker Optimizer: auto-assign workers to their best jobs" width="360">

# Worker Optimizer

**Auto-assign workers to their best jobs.**

Automatically assign **Whiskerwood** residents to suitable buildings with **one click**, matching guild specialties and productivity while keeping builders free.

![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D4)
![Tested game version: 0.7.209.0](https://img.shields.io/badge/tested_on-0.7.209.0-2E8B57)
![Release: v0.2.1-hotfix.1](https://img.shields.io/badge/release-v0.2.1--hotfix.1-2E8B57)

[Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514) · [Download v0.2.1-hotfix.1](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.2.1-hotfix.1) · [Documentation](docs/GUIDE.md) · [How it works](docs/GUIDE.md#how-it-works)

</div>

**v0.2.1-hotfix.1 is available on Steam Workshop and GitHub.** Subscribe on [Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514) for automatic updates, or download the release for manual installation.

> [!NOTE]
> **[Assignment hotfix: v0.2.1-hotfix.1](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.2.1-hotfix.1)** adds automatic recovery after delayed confirmations and replaces endless loading with a clear failure when confirmation remains unavailable. The Workshop update is live. This remains a GitHub pre-release; its in-game test is pending. [Details and limits](docs/releases/0.2.1-hotfix.1.md).

## At a Glance

- **Match skills to jobs:** assign residents using guild specialties, productivity and eligibility.
- **Keep construction staffed:** leave a configurable reserve free. Default **1**; **0** disables it.
- **Cover the basics first:** select feasible minimum crews in priority order, then fill extra positions, subject to the reserve and eligibility.
- **Set your priorities:** strict or weighted mode, category priorities and building-type overrides.
- **Leave protected workers alone:** paused and unsupported workplaces are skipped.

Building types are discovered from game data; unfamiliar workplace implementations may still need a mod update.

## New in 0.2.0

- **A redesigned interface:** responsive General, Priorities and Logbook tabs, searchable building priorities and run details.
- **Your schedule:** run once or enable assignment at day start or every 5, 10 or 15 real-time minutes. Automatic assignment is off by default; paused games wait until resume.
- **17 game languages:** follows the game's language, with English fallback. See the [language list](docs/GUIDE.md#languages).

One request stays active through at most two automatic replans. The start button stays locked while busy; extra clicks neither cancel nor restart it. See [release validation and known limits](docs/PREVIEW.md).

## Install

**Recommended: [Subscribe on Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3814077514).** Wait for Steam to finish downloading, then restart the game. Existing subscribers receive the update through Steam. Remove any separate local `WorkerOptimizer` installation before using the Workshop version.

For manual installation, download **[WorkerOptimizer-v0.2.1-hotfix.1.zip](https://github.com/repte/whiskerwood-worker-optimizer/releases/download/v0.2.1-hotfix.1/WorkerOptimizer-v0.2.1-hotfix.1.zip)** from [Releases](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.2.1-hotfix.1), not the source-code ZIP. Close the game and extract its `WorkerOptimizer` folder into `mods`:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\mods\WorkerOptimizer\
  WorkerOptimizer.pak
  WorkerOptimizer.uplugin
```

No Python or Unreal Editor needed to play. Use either Workshop or manual installation, not both.

## Play

> [!WARNING]
> For best results, run worker assignment calculations at night or just after a new day starts. Running them during the day may cause assignment errors.

| Control | Action |
| :--- | :--- |
| Arrow button, lower left | Optimize once |
| **Ctrl + Alt + O** | Show/hide controls; rebind through the gear |
| Gear | Open General, Priorities and Logbook tabs |
| Logbook button | Inspect run history and results |

Resume the simulation to process assignments. Use General to set the builder reserve, assignment mode and optional schedule; use Priorities to choose which workplaces matter most.

> [!IMPORTANT]
> **Try a separate save first.** For **v0.2.0**, automated tests, UI checks, packaging and the final in-game test passed on 6 October 2026. The **v0.2.1-hotfix.1** in-game test is still pending. All-language presentation, large settlements and extended sessions still need broader validation. See [changes](docs/CHANGELOG.md) and [limits](docs/GUIDE.md#verification-and-known-limits).

---

Unofficial community mod built with the [Whiskerwood modkit](https://github.com/Whiskerwood-Modding/Whiskerwood-Project) by Buckminsterfullerene and Whiskerwood-Modding. Game assets belong to their respective owners.

[MIT license](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)

---

[![DuoQueue](https://duoqueue.app/promo/duoq-workshop-banner-whiskerwood.png)](https://duoqueue.app/en/)
