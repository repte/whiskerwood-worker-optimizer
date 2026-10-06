# Assignment Recovery Hotfix

Pre-release: `0.2.1-hotfix.1`. Shipping-game acceptance remains
with the player; the open game and its installed Workshop files are untouched.

## Scope

- Manual and scheduled runs share the same recovery path.
- A confirmed late result can trigger one of the existing two automatic
  replans under the same frozen settings and report.
- An unresolved command has its original 10-second confirmation deadline plus
  10 seconds of recovery grace. Each tick observes the result before checking
  the cutoff. An already observable result is accepted even if the game was
  not ticking at the cutoff.
- If still unresolved, publish a failed report immediately and stop the busy
  animation. Keep admission locked until an exact late receipt or world reload.
- A terminal report is immutable. Confirmed changes at closure are retained;
  the final confirmation window and unsettled totals remain explicitly unknown.
- Correct the `bridge.` prefix in recoverable pre-dispatch rejection guards.
- Timeout diagnostics include action, worker ID, building ID, slot, current
  occupant/workplace where readable, and confirmed/queued counts.

No native command is resent blindly, no pending lock is cleared by time alone,
and no terminal request resumes its stale action queue. The optimizer, reserve,
priorities, frame budget and scheduling settings are unchanged.

## Evidence

The player's live session logged `action_timeout` at 22:52:20 on 2026-10-06
while the HUD continued displaying assignment activity. Native dispatch is void
and asynchronous; its successful invocation is not an acknowledgement that the
game accepted the operation. The cause of this specific missing native effect
has not been proved.

The old assets fail the focused regressions in
`Modkit/Saved/Logs/WorkerOptimizer-Hotfix-Red2.log`:

- Missing pending-action details in timeout diagnostics.
- No automatic recovery after a timed-out command receives a late receipt.
- Terminal timeout keeps the busy animation.
- Logbook classifies timeout as a partial-result warning, not a failure.

An additional regression covers the mismatched rejection guard prefix, both
manual and day-start terminal timeout paths, no repeat dispatch, report
publication, retained locking, and a late receipt after terminal closure.

## Automated Verification

- Focused checks passed in `WorkerOptimizer-Hotfix-ClockRepair3.log`, including
  controller recovery, timeout diagnostics, terminal HUD state and logbook status.
- Two consecutive scheduling-clock regenerations passed structural checks.
  The authoring tool's undirected cleanup retained obsolete bodies through
  parameter links. The controller generator now clears its generated function
  bodies while preserving signatures before rewriting them.
- Fresh controller regeneration and controller regressions passed in
  `WorkerOptimizer-Hotfix-CleanController.log`.
- The full production-Blueprint suite passed in `WorkerOptimizer-AllTests.log`
  at 21:50:46 UTC on 6 October 2026, including scheduling-clock precision and
  native UI notification checks that caught the obsolete authoring nodes.
- Package-validation regressions passed, including non-runtime asset rejection.

These checks execute the compiled production Blueprints in the editor. Native
game behavior is supplied at explicit test boundaries; they do not establish
that the affected shipping-game save now accepts every assignment command.

## Package Verification

Full cook and delivery verification passed for build
`20261006-234715-bd1c00c8`. The PAK contains 46 runtime assets in 92 entries,
is 515,700 bytes, and passed integrity, completeness and editor-content
exclusion checks. The descriptor version is `0.2.1-hotfix.1`.

PAK SHA-256:
`2065CBA956C770F0F293166117F39060C743DDC0CCC8243F9217BDC610AD9580`

GitHub and the locally prepared Workshop update use this same verified PAK.
Workshop preparation is not publication; the owner submits that update.

## Player Check

Use a test copy of the affected settlement. Try manual assignment and day start
with the simulation running. Confirm actual workplaces and preserved builder
reserve. If the native action is still rejected, inspect the visible failed
report and the detailed `WorkerOptimizer stopped:` entry in `modlog.txt`.
This hotfix does not claim every native rejection can be recovered safely.
