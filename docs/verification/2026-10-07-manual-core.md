# Manual Assignment: Native Contract Verification

## Status

- Native inspection: completed against installed Whiskerwood **0.7.209.0**.
- Compiled Blueprint tests, full cook and package verification: **passed on 7 October 2026 (CEST)**.
- **In-game acceptance test: not run for this update. The user will perform it.**

## Reported Failure

The live log reproduced the same stopped run after reloading: 34 dispatched
actions, 33 confirmed changes, 30 fires and 3 hires. The outstanding target was
worker ID 30, building ID 724, slot 0; both workplace and occupant remained empty.

The exact education values of that worker and slot were **not captured**. The
admission defect below is verified in the code/native contract, but attributing
this particular saved-game failure to that defect still requires the user's
game test. No successful in-game repair is claimed here.

## Verified Native Contract

The inspection used the matching reflection data and the read-only development
helper `Automation/WorkerOptimizer/inspect_native.py`. The mod does not ship or
use binary addresses, patches, or a replacement native assignment implementation.

- `SelectTool.ReceiveHudAction` handles `hireWorkerForSlot` with agent ID in
  `HudAction.paramInt` and slot index in `paramFloat`. The building comes from
  the private detail widget's context. These argument conventions were correct.
- The native `ArcoSystems.cpp` handler records the action and **executes it in
  the same call**. Recording it is not evidence of a deferred assignment queue.
- `ADD_FREE_WORKER_TO_SLOT` resolves the workplace at the action's grid position,
  resolves the worker by ID, checks the actual slot's education requirement and
  calls `AgentEnterable.AssignWorkerToSlot` directly.
- The education check is `(education & requirement) == requirement`, matching
  `ArcoFunctionLibrary.CheckEducation`. Selector-only `ApprenticeOnly` and
  `SailorOnly` filtering is not an alternative admission rule for this action.
- All **40 hire/fire implementation pointers across the 20 reflected native
  workplace components** matched the installed executable. Their implementations
  use the shared immediate slot writer/clearer, wrappers around those methods,
  or School's equivalent immediate writer/clearer. No deferred slot-mutation
  branch was found in this inspected set. **This pointer check alone did not
  establish workforce capability.** Later inspection proved that
  `ResourceBuilding` and `GranaryResourceBuilding` return no native mutable
  workforce despite exposing `m_workers`; see the
  [native capability correction](2026-10-07-native-workplace-capability.md).
- The native `newEmployer` handler sets the worker's workplace synchronously;
  `lostEmployer` clears it synchronously. `Prototype_Agent.GetWorkplace` reads
  that workplace reference. The slot and worker-side workplace can therefore be
  checked after the native call returns, including school assignments.
- **Do not interpret `FireSpecificWorker`'s bool as generic success.** Its shared
  slot clearer returns the cleared slot's required-role flag. A successful fire
  from an optional slot can return false. Verify the observed state instead.
- The outer `FIRE_WORKER` handler uses that required-role flag: after firing a
  required worker, it also fires every occupied non-required slot in that
  workplace. This includes school student slots when firing their required
  teacher. Inspecting only the component's one-worker clearer misses this
  additional behavior. Action ordering must empty affected optional slots
  explicitly before firing a required incumbent, or otherwise account for all
  collateral effects; it must not assume a required-worker fire is isolated.

This evidence is scoped to the inspected game version and supported native
components, not unknown future workplace implementations.

## Corrections

`generate_job_eligibility.py` previously admitted some education combinations
using selector filters that the real hire action rejects. For example,
education 1 passed requirement 128 in the mod, but fails native hire admission.
The role check now uses the actual native mask. School students must first meet
their own slot's requirement; the existing teacher, learning-target and guild
checks remain additional restrictions.

`generate_action_bridge.py` retains the normal native action route and observes
its result immediately. `QueueAction` returns true only for the intended target
slot result. An unchanged or mismatched result returns a native-rejection reason;
an unavailable observation is not reported as success. No direct assignment
array mutation or bypass of native employer notifications was introduced.

The runner can consequently finish or report failure after the returned native
call without retaining a permanent lock for a supposedly queued command.
Dispatch attempts and confirmed changes remain distinct; the final confirmation
still checks both the exact slot and the worker's workplace.

The action plan explicitly clears movable optional occupants before firing a
native-required incumbent, then restores their planned assignments. The layout
pins existing required coworkers when firing them would dismiss a protected
optional occupant. Pinned, unchanged required workers are preservation, not new
hires; this also applies to an existing school teacher. Changed teachers, new
hires and optional workers that must be rehired still undergo admission checks.

## Verification Sources

- `Automation/WorkerOptimizer/generate_job_eligibility.py`:
  `EligibleData`, `CanFillSlot`, `LiveCanFillSlot`.
- `Automation/WorkerOptimizer/generate_action_bridge.py`:
  `ValidateAction`, `QueueAction`, `ConfirmNativeResult`.
- `Automation/WorkerOptimizer/generate_application_runner.py`:
  `AdvanceApplication`, `ObserveAction`, `FailApplication`.
- `generate_action_plan.py`, `generate_problem_layout.py` and
  `generate_score_matrix.py`: native dismissal dependencies and pinned incumbents.
- `test_manual_surface.py`, `test_manual_application.py`,
  `test_native_fire_dependencies.py` and `test_pinned_incumbents.py`: regressions
  reproduced before the corresponding implementation changes.
- Regression coverage: `test_job_eligibility.py` and `test_action_bridge.py`,
  plus the integrated runner/controller tests recorded below when complete.
- Existing local inspection records: `WorkerOptimizer-NativeSelectAction.txt`
  and `WorkerOptimizer-NativeWorkerActions.txt` in the modkit's `Saved/Logs`.

## Final Test Results

- Full suite: `WO_ALL_TESTS_PASS` in `WorkerOptimizer-AllTests.log`, with no Python,
  Blueprint or script-runtime errors. Includes manual-only access, minimum-first
  planning, native admission, dismissal dependencies, pinned teachers, shortages,
  reserve, paused protection, terminal recovery and restarting from the same icon.
- Targeted regressions passed after their recorded failures:
  `WO_MANUAL_SURFACE_TESTS_PASS`, `WO_MANUAL_APPLICATION_TESTS_PASS`,
  `WO_NATIVE_FIRE_DEPENDENCIES_TESTS_PASS`, `WO_PINNED_INCUMBENTS_TESTS_PASS`.
- Package validation passed: `WO_PACKAGE_VALIDATION_TESTS_PASS`.
- Full Windows cook/build: `BUILD SUCCESSFUL` and `WO_BUILD_MOD_PASS`, build ID
  `20261007-011440-b2dbf8c7`.
- PAK verification: `WO_PACKAGE_TESTS_PASS`, **46 runtime assets, 92 entries,
  509,801 bytes**; editor/test helpers excluded and archive integrity checked.
- PAK SHA-256:
  `3A205A5922F545AD9DBD9E4E33BCB475FFC743AA2AC4A96BF0DC202FB907C5CD`.
- The ten changed runtime source assets match the tested project's files.

Editor fixtures supply native observations at explicit boundaries; they cannot
establish shipping-game behavior. No game test or installed-mod replacement was
performed. The user's saved-game acceptance test remains separate.
