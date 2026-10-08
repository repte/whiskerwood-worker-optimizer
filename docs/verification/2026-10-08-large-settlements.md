# Large-settlement performance candidate

Local candidate: `0.3.3-performance-preview`, built and installed locally on
8 October 2026 at the user's request. No Workshop publication was performed.
The reported player's save is not available, so shipping-game acceptance of that
specific settlement remains open.

## Verified Result

The existing exact planner completed all six 1,000-worker cases below 15 seconds
in two compiled editor measurements. No hybrid or approximate solver was added.
The maximum accumulated planner-call time was 14.554 seconds; the maximum observed
benchmark total, including Python observation, was 14.929 seconds. These are
host-specific measurements on the i7-12700K, not a universal wall-clock limit.

| 1,000-worker fixture | First planner calls | Repeat planner calls | First total | Repeat total |
| --- | ---: | ---: | ---: | ---: |
| Unique, reserve 1, equal builder quality | 5.607 s | 5.648 s | 5.821 s | 5.849 s |
| Unique, reserve 3, equal builder quality | 5.833 s | 5.738 s | 6.048 s | 5.942 s |
| Unique, reserve 3, varied builder quality | 12.726 s | 12.799 s | 13.214 s | 13.268 s |
| Tied productive quality, varied builders | 11.535 s | 11.413 s | 11.895 s | 11.749 s |
| Five priority tiers, strict | 14.548 s | 14.554 s | 14.929 s | 14.916 s |
| Five priority tiers, weighted | 6.204 s | 6.213 s | 6.423 s | 6.431 s |

The original 600-worker fixture now takes 2.205 seconds of planner calls and
2.290 seconds observed, versus the earlier 50.372/51.056 seconds. Its complete
assignment hash remains `0345281346638018e8a2d11e985e177e6dc8f8e3e6ceaf37f6891d883e514877`.
All six 1,000-worker assignment hashes and coverage/staffing/quality/reserve
objectives are unchanged across both final measurements and prior checkpoints.
The background game had already exited before Round5; earlier timing differences
should therefore not be attributed exclusively to code changes.

The complete `Test-Mod.ps1` editor suite passed with `WO_ALL_TESTS_PASS`, including
the new numerical, work, cancellation and restart regressions. Its strict log
checks reported no Python, Blueprint or script runtime errors. The fresh repeat
run also passed `WO_FINAL_PERFORMANCE_VERIFIED`. Both generated production assets
were unchanged by the tests and copied back to the release worktree after hash
verification. At benchmark completion no shipping cook, installation, Workshop
upload or real-player-save run had been done. The subsequent user-requested local
installation is recorded below; game acceptance remains pending.

Evidence is under `D:/TD/WoodMod/DeploymentCandidates/performance-1000/`: the first
final measurement and full-suite logs are in `Round9/`; repeated 600/1,000-worker
JSON, verification logs and the synchronized assets are in `FinalVerified/`.
The rest of this document is the chronological verification record. See
`Remaining Limits` for school search and in-game frame scheduling, which are not
covered by the 15-second planner benchmark.

## Local Installation

At the user's request, `Build-Mod.ps1` produced build
`20261008-112235-7c83b569`. The complete editor suite passed again with
`WO_ALL_TESTS_PASS`, followed by package-validation tests, a full Windows Shipping
cook (`BUILD SUCCESSFUL`) and package inventory/integrity checks
(`WO_PACKAGE_TESTS_PASS`). The solver and planner source-asset hashes still match
the final benchmark snapshots after packaging.

The delivered PAK contains 46 runtime assets in 92 entries, is 556,937 bytes,
and has SHA256
`200C36D3932B3DA6452B7CB11427BFB2E2180A8D51F9F61C109D36EDB95AB225`.
The matching descriptor identifies `0.3.3-performance-preview`, EngineVersion
`5.8`, with SHA256
`F9049B5D63ECEF76701DE3E440BD2F2A80FBBDD36B578FB1BF069CCBA738CFB6`.

With Whiskerwood confirmed closed, only `WorkerOptimizer.pak` and
`WorkerOptimizer.uplugin` were replaced in
`C:/Users/nikla/AppData/Local/Whiskerwood/Saved/mods/WorkerOptimizer/`.
Both installed hashes match the verified delivery. No duplicate WorkerOptimizer
package was found in local mods, the game directory or installed Workshop
content. Other mods, settings and saves were not changed. The game was not
launched and no in-game timing or acceptance result is claimed.

The prior `0.3.2-local-diagnostics` installation was backed up and hash-verified
before replacement under
`D:/TD/WoodMod/DeploymentCandidates/performance-1000/LocalInstall-20261008-112235/PreviousLocalMod/`.
That parent directory also contains the full-suite and cook logs plus the package
verification manifest. The delivery remains at
`D:/TD/WoodMod/Modkit/Saved/WorkerOptimizerBuilds/20261008-112235-7c83b569/Delivery/`.
Nothing was published to GitHub or Steam Workshop.

The later user-requested gameplay-layer icon change was tested and packaged as
combined build `20261008-115852-7696bc58`, then installed locally with a verified
backup. Its solver and planner assets still match these timing measurements.
See the [gameplay visibility verification](2026-10-08-gameplay-visibility.md)
for the final combined package identity and checks. That package supersedes the
performance-only local build above for release and Workshop preparation.

## Changes

- The matrix now processes up to its existing 64-item work budget per call.
  Setup, policy and native definition observation boundaries remain incremental.
  Failure and cancellation still stop further work.
- The solver removes unused empty columns, initializes distance labels during
  the first scan, resets only previously visited columns, and skips exact-zero
  potential updates. Nonzero arithmetic retains its original operation order.
- The strict planner skips priority levels with no real slots. The manual
  Workshop surface uses a single priority, making this relevant to normal runs.
  Construction reserve optimization remains a separate final pass.
- School search skips suffixes with duplicate teacher identities and teacherless
  alternatives once complete coverage has already been found. Feasible candidates
  retain their original order. Partial-coverage alternatives remain available.

The objective, minimum staffing, protected occupants, reserve, confirmation,
two-replan cap, cancellation and controller frame budget are preserved.

## Evidence

Measurements execute the actual compiled Blueprint classes. They include
Python-to-Unreal dispatch and are not shipping-game frame or button-to-result
measurements. The game was running in the background during the initial
measurements, but was no longer present from Round5 onward. Operation counts are
deterministic; elapsed times are host-specific.

The saved baseline uses 600 workers, 600 slots, 300 buildings and a reserve of
three. With one common priority it used 34,180,044 primitive work items and
220.819 seconds of accumulated planner-call time. With five populated priorities,
it used 201.017 seconds in strict mode and 94.736 seconds in weighted mode.
All three produced the known optimal coverage, staffing and productivity.

Baseline files and subsequent verification logs are under
`D:/TD/WoodMod/DeploymentCandidates/performance-600/`.

New regressions first failed against the unchanged compiled assets. The final
solver passed its original 96 exhaustive-oracle cases and 111 feasible new
oracle/dual cases. Dense 80-worker matching fell from 45,684 to 20,083 work items.
Tests include impossible mandatory masks, single-item budgets, reuse, exact-zero
updates and a large-bonus/small-score numerical regression using an independent
80-digit decimal oracle. A proposed lazy-subtraction optimization was rejected
after the compiled numerical regression detected a loss of 0.00875.

The final generation run passed all targeted solver, planner, reserve, matrix,
grouped matrix, search and grouped-search tests plus the public-flavor check.
School pruning retained the exact ordered 120-assignment identity oracle while
reducing candidate starts from 3,125 to 825. In the six-school grouped fixture,
full-coverage starts fell from 729 to 64; the partial-coverage case retained all
729 alternatives. Sparse-tier regressions preserve the known optimum across all
five single-priority cases, reserve/no-reserve cases and zero-slot definitions.

The optimized 600-worker single-priority fixture completed in 50.372 seconds of
accumulated planner-call time (51.056 seconds including Python observation),
versus 220.819 seconds before: 4.38 times faster. Work fell from 34,180,044 to
7,232,112 primitive items. The entire assignment hash is unchanged, as are all
coverage, staffing and productivity totals. This is a planner-only fixture,
not a measurement of a player's school search or the complete game workflow.

At the 600-worker checkpoint, the mixed-priority optimized benchmarks, full
editor suite and shipping cook had not been run. Targeted compiled tests and the
single-priority benchmark passed; this is not a release or gameplay-acceptance
claim. No package has been installed or published.

## 1,000-Worker Follow-Up

The user rejected the proposed local/hybrid optimizer and requested the existing
exact approach below 15 seconds at 1,000 workers. No approximation is being
introduced. The 600-worker checkpoint measured 139.546 seconds of accumulated
planner calls (141.449 seconds observed) at 1,000 workers, 1,000 slots and reserve
three. It performed 20,003,412 primitive steps. The under-15-second assertion
failed as expected; objective and reserve remained correct.

The follow-up removes per-cell Blueprint dispatch from dense phases and uses
direct scalar array references. Arithmetic order and logical work accounting
remain unchanged. Tests now count primitive work rather than assuming every
call completely consumes its budget. A traced two-row example terminates at
58 primitive steps; partial-budget phase yields are intentional.

An exact reserve certificate can omit the final reserve solve: every currently
selected reserve worker must have quality at least as high as every unselected
eligible worker. This attains the top-R upper bound without weakening the
productive objectives. Cases that fail the certificate retain the full solver.
The test suite explicitly includes varied qualities that require that fallback.

The mathematical literature was checked against the implementation:
[SciPy's assignment documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html)
describes the rectangular assignment problem and its Jonker-Volgenant variant;
[the original paper](https://doi.org/10.1007/BF02278710) describes shortest
augmenting paths. These are references, not replacement runtime dependencies.
A partial row-max warm start was rejected after an independent Decimal oracle
found a 0.00625 regression in a large-bonus fixture. That case is now tested.

### Intermediate 1,000-worker checkpoint

The first follow-up, before row-bound and matrix-fusion changes, measured:

| Fixture | Planner calls | Observed total | Reserve quality |
| --- | ---: | ---: | ---: |
| Unique best workers, reserve 1, equal builder quality | 65.215 s | 66.828 s | 1 |
| Unique best workers, reserve 3, equal builder quality | 64.605 s | 66.083 s | 3 |
| Unique best workers, reserve 3, varied builder quality | 118.130 s | 120.726 s | 1497 |
| Tied productive quality, reserve 3, varied builder quality | 107.837 s | 110.412 s | 32988 |

The current manual policy hard-codes real-building priority 2 and strict mode
(`generate_priority_settings.py`, `MANUAL_ONLY` branch). Stored overrides remain
preserved but are ignored by that workflow; `test_manual_surface.py` exercises
this explicitly. Mixed-priority cases therefore test supported internal APIs,
not an exposed current manual setting. The synthetic reserve priority -1 still
requires separate optimization when its upper-bound certificate does not hold.
This is a local source/release-contract check, not an inspection of the affected
player's installed Workshop files.

Every case retained its known optimal coverage, staffing and productive quality.
The reserve-three/equal-quality assignment hash also matched the 139.546-second
baseline. These results do not meet the target. Evidence is preserved in
`D:/TD/WoodMod/DeploymentCandidates/performance-1000/Round1/`.

### Exact follow-up under verification

- A cached row minimum can certify the same first augmenting step as a complete
  relaxation scan. The shortcut requires a free minimum-cost column, zero row
  and candidate-column potentials, and nonpositive real-column potentials.
  Dummy columns are included in the lower-bound check. Otherwise the unchanged
  full relaxation runs. This is not a heuristic or a different objective.
- At a terminal augmenting step, only visited potentials need updating. Distance
  labels are discarded before the next row, so their final subtraction is
  omitted. Continuing searches retain the original arithmetic order.
- Dense planner validation is batched; the redundant expanded score matrix is
  removed; per-row data is cached; solver costs and their first row minima are
  generated together. Generic solver callers still receive full validation.
  Planner-generated costs are bounded below the solver's numeric limit by the
  validated score and slot caps.
- Batch exits use explicit loop breaks. The Blueprint DSL's void return does
  not terminate a surrounding loop, which previously caused redundant tail
  iterations. Tests compare primitive work across single-item and batched calls.
- Building selection scans each active priority tier once in stable index order,
  instead of rescanning all buildings after each choice. Coverage edge scans are
  batched without changing traversal or queue order. The compiled old-asset
  regression failed as intended at 1,085 selection items versus its 176-item cap.

The compiled solver passed the original 96 oracle cases and 111 feasible
work/dual/numeric cases after the new shortcuts. Its isolated dense 200-worker
test measured 0.236-0.252 seconds, versus approximately 1.270 seconds previously.
Offline differential checks covered 2,003 relaxation scans and 10,000 row-bound
cases; all 2,061 certified row shortcuts selected the same column and delta bits.
An independent interpreter checked the actual fused-cell DSL against the legacy
two-stage formulas across 1,500 matrices (45,562 cells), including masks, score
bits, cached minima and row cursors. These isolated checks are not a complete
planner performance result.

### Second Compiled Checkpoint

The integrated row-bound, fused-matrix, stable-selection and coverage-batching
assets passed all targeted regressions. Measured on an Intel Core i7-12700K,
with the game running in the background:

| Fixture | Planner calls | Observed total |
| --- | ---: | ---: |
| Unique best workers, reserve 1, equal builder quality | 26.715 s | 27.605 s |
| Unique best workers, reserve 3, equal builder quality | 21.870 s | 22.335 s |
| Unique best workers, reserve 3, varied builder quality | 56.822 s | 58.014 s |
| Tied productive quality, reserve 3, varied builder quality | 43.803 s | 44.612 s |
| Five priority tiers, strict, reserve 3, equal builder quality | 83.857 s | 85.243 s |
| Five priority tiers, weighted, reserve 3, equal builder quality | 22.965 s | 23.433 s |

All four uniform-priority fixtures retained their previous complete assignment
hashes and exact expected objectives. The standard reserve-three fixture spent
11.19 seconds building its pass matrix, 5.77 seconds relaxing assignment edges,
and 3.80 seconds validating inputs. Its full baseline was 139.546 seconds.
Timings and corresponding compiled assets/source are preserved in
`D:/TD/WoodMod/DeploymentCandidates/performance-1000/Round2/`;
the integrated log is `Round2Measurement.log` in the parent directory.

A fused-cache test initially exposed an oracle mistake, not a production
arithmetic change: the DSL lowers unary minus to `0 - value`, producing positive
zero for a positive-zero score. The Python bit oracle now uses that same
operation, with an explicit signed-zero regression.

Next changes remain under verification: exact zero-label relaxation skipping,
retained-edge-only scoring for later passes, and an implicit first-pass score
representation using the unchanged Hungarian algorithm. The implicit regression
was first run against dense assets: all 18 reference comparisons passed, then
the intended no-materialized-matrix assertion failed. It compares every score
bit, assignment, matching, dual potentials and complete-plan result. Rounded
row-minimum ties disable only the shortcut when the earliest winner cannot be
certified; the exact ordinary scan remains available.

The 15-second target is not met at this checkpoint.

### Third Compiled Checkpoint

The implicit first pass, sparse later-pass construction and zero-label skipping
passed all targeted compiled regressions, including the independently built
dense reference (assignment, matching and dual-potential bits), first-pass
score/mask bits, sparse refinement, malformed initializer shapes, reuse and
single-item/batched budgets. All four uniform-case assignment hashes are
unchanged from the second checkpoint.

| Fixture | Planner calls | Observed total |
| --- | ---: | ---: |
| Unique best workers, reserve 1, equal builder quality | 12.162 s | 12.512 s |
| Unique best workers, reserve 3, equal builder quality | 12.234 s | 12.560 s |
| Unique best workers, reserve 3, varied builder quality | 46.744 s | 47.736 s |
| Tied productive quality, reserve 3, varied builder quality | 37.461 s | 38.150 s |
| Five priority tiers, strict, reserve 3, equal builder quality | 60.369 s | 61.346 s |
| Five priority tiers, weighted, reserve 3, equal builder quality | 12.346 s | 12.666 s |

The standard reserve-three case spends 4.996 seconds validating source rows and
6.089 seconds in relaxation. Its dense first-pass construction has disappeared.
The varied-quality unique case still spends 23.552 seconds in relaxation,
12.950 seconds in first refinement and 3.991 seconds updating potentials. The
tied variant retains a dense feasible graph and spends another 6.960 seconds
building its later pass. Three fixtures meet the target; the difficult fixtures
do not. This is not a blanket under-15-second claim for arbitrary settlements.

Evidence: `D:/TD/WoodMod/DeploymentCandidates/performance-1000/ImplicitBuild.log`
and the corresponding source, assets and benchmark JSON in `Round3/` alongside
that log. The full `Test-Mod.ps1` editor suite also passed on this checkpoint,
including `WO_ALL_TESTS_PASS` and all required markers, without runtime/Python
errors. Its two logs are preserved inside `Round3/`. Package and in-game
verification remain pending. No package has been installed or published.

### Fourth Compiled Checkpoint

The second-minimum relaxation bound and scalar refinement fusion passed the
targeted compiled regressions. The new bound regression originally read stale
implicit descriptors during later dense passes; it now checks both `PassScores`
and inherited solver `Scores` against the dense oracle. The test-only probe
class cache is keyed by parent class, so test order cannot replace the disabled
reference class with an unrelated probe class. No production change was needed
for these harness corrections. The additional large-bonus rounded-tie case also
passed its dense-reference assignment and dual-bit comparison.

| Fixture | Planner calls | Observed total |
| --- | ---: | ---: |
| Unique best workers, reserve 1, equal builder quality | 12.170 s | 12.507 s |
| Unique best workers, reserve 3, equal builder quality | 12.229 s | 12.553 s |
| Unique best workers, reserve 3, varied builder quality | 42.515 s | 43.509 s |
| Tied productive quality, reserve 3, varied builder quality | 37.507 s | 38.205 s |
| Five priority tiers, strict, reserve 3, equal builder quality | 60.089 s | 61.106 s |
| Five priority tiers, weighted, reserve 3, equal builder quality | 12.598 s | 12.926 s |

All six assignment hashes and exact known objectives match the third checkpoint.
The varied unique fixture now spends 19.95 seconds in relaxation, 12.13 seconds
in refinement, 5.09 seconds in validation and 3.95 seconds updating potentials.
The tied fixture still spends 7.23 seconds building its later matrix. This is a
limited improvement, not completion of the under-15-second target.

Evidence: `D:/TD/WoodMod/DeploymentCandidates/performance-1000/StrongBoundMeasure.log`
and source, compiled assets and benchmark JSON in `Round4/`. The separate build
log intentionally retains the earlier harness failure. The complete editor suite
then passed (`WO_ALL_TESTS_PASS`, `WO_ROUND4_FULL_VERIFIED`) without Python/runtime
errors; its logs are `Round4/FullVerify*.log`. Before that full run, the next sparse
refinement regression correctly failed on the dense baseline: 109 work units
instead of the initial 47-unit retained-edge expectation. Its finalized bounded
implementation also accounts for one explicit initialization work unit.

Next source-only work is independently modeled: defer the first dense score
matrix, visit only eligible first-refinement ranges, refine later passes through
retained edges, and native-copy exact constant row templates. A validation-cache
regression first passed its state oracle but failed its single-read assertion;
the candidate cached formulation preserved 63,419 cells and 143 invalid-input
rejections, including post-fixed-mask statistics. These are not runtime timing
claims. Two further solver certificates were investigated but are not integrated:
a fresh next-argmin cache saves 748,500 reserve-scan visits while adding roughly
one million potential-phase comparisons, and the second-minimum root shortcut
adds no hits in the faithful 1,000-worker varied-reserve trace.

### Fifth Compiled Checkpoint

Deferred first-pass matrix allocation, candidate-range first refinement,
in-place retained-edge later refinement and native constant-row copying passed
the targeted compiled tests. Primitive and budgets 1/3/64, restart during
refinement, tolerance boundaries, fixed workers, exact mask/CSR order and
double-bit cache comparisons all passed. All six assignment hashes and known
objectives remain unchanged from Round4.

| Fixture | Planner calls | Observed total |
| --- | ---: | ---: |
| Unique best workers, reserve 1, equal builder quality | 12.079 s | 12.408 s |
| Unique best workers, reserve 3, equal builder quality | 12.241 s | 12.561 s |
| Unique best workers, reserve 3, varied builder quality | 38.742 s | 39.660 s |
| Tied productive quality, reserve 3, varied builder quality | 27.256 s | 27.790 s |
| Five priority tiers, strict, reserve 3, equal builder quality | 40.543 s | 41.229 s |
| Five priority tiers, weighted, reserve 3, equal builder quality | 12.549 s | 12.863 s |

The unique varied fixture still spends 19.87 seconds in relaxation, 8.38 seconds
in refinement, 5.17 seconds in validation and 3.94 seconds updating potentials.
The strict mixed fixture spends 21.38 seconds in refinement and 5.87 seconds
building later matrices. Three cases remain above target. Scalar validation
caching produced no meaningful measured speedup; no benefit is claimed for it.

Evidence: `D:/TD/WoodMod/DeploymentCandidates/performance-1000/DeferredBuild.log`
and the corresponding source, assets and JSON in `Round5/`. The previously
observed background game process was no longer present before these timings;
we did not close it. Timing deltas should not be attributed exclusively to code.
The complete editor suite subsequently passed (`WO_ALL_TESTS_PASS` and
`WO_ROUND5_FULL_VERIFIED` in `Round5/NativeProbe3.log`). That same wrapper also
records a separate test-probe input failure described below; it is not a clean
whole-wrapper success claim. The next refinement regression correctly failed
on Round5 at 203 work units versus the independently calculated 83.

Further candidates remain outside production. A native double-sort relaxation
probe compares exact distance labels and free/index tie handling, including
signed-zero payloads. Its initial compiled attempt stopped at a test-only
noncontiguous SwitchInt case, before any timing measurements. An extended
refinement certificate bounds nonwinning real edges by
`(RowSecondMinCost - U) - max(V[1:WorkerCount+1]) > 0.00001`.
The maximum must exclude V[0], and the threshold is the actual existing
1e-5 tolerance, not 1e-6. Offline operation counts and models are not compiled
performance evidence.

The native probe subsequently passed all 23 compiled comparisons, including
signed-zero payloads and 11 potential-cache overhead comparisons. Python editor
array property assignment normalized negative zero before execution; the final
fixture generates it inside the Blueprint VM and verifies every input bit before
measuring. Native selection took approximately 0.1-1.6 ms for certified traced
states versus 6-10 ms for the probe's dense baseline. Its largest individual
native call was 0.53 ms in the successful run. These are isolated phase timings,
not an end-to-end speedup forecast; the probe's instrumentation also differs from
the production dense loop. Evidence: `performance-1000/NativeProbe/` containing
the source, compiled-run log and detailed JSON. The compiled solver integration
subsequently passed 192 native-enabled/native-disabled comparisons with 84 native
hits and all six native phases exercised (`WO_NATIVE_SOLVER_TESTS_PASS` in
`performance-1000/NativeBuild.log`). The combined planner build and timings remain
under verification.

### Sixth Compiled Checkpoint

The native exact relaxation and real-maxV singleton refinement integration passed
all targeted compiled tests. All six assignment hashes and known objectives are
unchanged from Round5. No Python, Blueprint or script runtime errors were reported
in this run (`WO_NATIVE_INTEGRATION_TARGETED_PASS` and
`WO_NATIVE_INTEGRATION_MEASURED` in `performance-1000/Round6/NativeBuild.log`).

| Fixture | Planner calls | Observed total |
| --- | ---: | ---: |
| Unique best workers, reserve 1, equal builder quality | 7.775 s | 8.040 s |
| Unique best workers, reserve 3, equal builder quality | 7.956 s | 8.215 s |
| Unique best workers, reserve 3, varied builder quality | 17.931 s | 18.557 s |
| Tied productive quality, reserve 3, varied builder quality | 24.144 s | 24.672 s |
| Five priority tiers, strict, reserve 3, equal builder quality | 36.772 s | 37.407 s |
| Five priority tiers, weighted, reserve 3, equal builder quality | 8.217 s | 8.476 s |

The unique varied fixture now spends only 0.061 seconds in refinement, but still
6.19 seconds in native relaxation, 4.98 seconds updating potentials and 5.15
seconds in validation. The tied fixture retains 9.65 seconds of refinement and
7.65 seconds of native relaxation. The mixed strict fixture retains 20.21 seconds
of refinement and 5.77 seconds building later matrices. Three cases remain above
target. Sources, compiled assets and both complete benchmark JSON reports are
saved in `performance-1000/Round6/`; this is a targeted-suite checkpoint, not a
new complete-suite success claim.

### Seventh Compiled Checkpoint

The next isolated source checkpoint preserves two exact invariants:

- During one refinement pass, rows with a complete real-column prefix, identical
  constant real score and identical row potential have the same tight real edges.
  Required-column bonuses and column potentials are fixed during that pass. Plain
  and minimum rows have separate caches. Nonuniform, partial and fixed rows fall
  back unless separately certified. Dummy edges are still checked individually.
- After native relaxation, the masked label array equals the original distance
  labels on every unused column. A zero-delta continuation changes no labels, so
  only the newly used column and subsequently visited sparse labels need updating.
  Nonzero updates, ordinary relaxation, fallback, terminal matching and new rows
  invalidate this cache. The original distance labels are never replaced by sorted
  values, preserving the existing arithmetic and signed-zero payloads.

Actual-emitted model tests reduced the 32-by-32 refinement fixture from 1,026 to
130 work units, and the 40-worker mask fixture from 863 mask writes and 41 copies
to 5 and 2. Both use budgets 1/3/64. Independent validation covered 63,419 cells
and 143 rejected inputs, including post-fixed-mask metadata. Full solver lifecycle
comparison passed 1,038 cases plus 519 separately loaded Round6 reference solves;
all compared result and solver-state double bits match. These are model results,
not compiled timing claims. The corresponding compiled work tests then failed as
expected on Round6: 418 refinement units against the 318 ceiling, and 863 mask
writes with 41 copies against limits 16 and 4. Evidence is `ReuseRed.log`, markers
`WO_REFINEMENT_REUSE_RED_OBSERVED`, `WO_NATIVE_MASK_REUSE_RED_OBSERVED` and
`WO_ROUND7_REUSE_RED_VERIFIED`. The integrated compiled tests subsequently passed:
mask writes/copies are exactly 5/2 at budgets 1/3/64, and the refinement test
preserves all pass masks, CSR order and score bits, required-set invalidation,
partial/fixed/negative fallbacks, cancellation and restart.

| Fixture | Planner calls | Observed total |
| --- | ---: | ---: |
| Unique best workers, reserve 1, equal builder quality | 7.056 s | 7.283 s |
| Unique best workers, reserve 3, equal builder quality | 7.417 s | 7.655 s |
| Unique best workers, reserve 3, varied builder quality | 14.276 s | 14.778 s |
| Tied productive quality, reserve 3, varied builder quality | 12.871 s | 13.228 s |
| Five priority tiers, strict, reserve 3, equal builder quality | 16.322 s | 16.715 s |
| Five priority tiers, weighted, reserve 3, equal builder quality | 7.625 s | 7.855 s |

All six assignment hashes and objectives match Round6. Five cases are below the
15-second target; the strict mixed-priority case is not. Validation now costs
5.85-6.09 seconds, including the additional full-row metadata. Mixed strict later
matrix building still costs 5.83 seconds. No Python, Blueprint or script runtime
errors were reported. Evidence: source, assets and JSON in `Round7/`, with
`WO_REUSE_INTEGRATION_TARGETED_PASS` and `WO_REUSE_INTEGRATION_MEASURED` in its
`ReuseBuild.log`. This is still a targeted-suite checkpoint.

The next source-only candidate short-circuits streaming row statistics: a value
no greater than the second maximum cannot alter the maximum, first column or
prefix maximum. Global MaxScore needs comparison only when a row maximum is
promoted. Validation order and every arithmetic operation remain unchanged.
The actual-emitted 10,000-cell unique fixture first failed at 99,903 comparisons
against a 62,000 ceiling, then passed at 56,046; the tied fixture uses 60,600.
Independent intermediate-state checks, invalid raw values and fixed-owner masking
pass offline. A new compiled per-cell test also seeds negative zero inside the
VM to avoid Python input normalization; compiled verification and timing are
pending at that source checkpoint. Frozen candidate source is in
`Round8SourceBeforeCompile/`.

### Eighth Compiled Checkpoint

The validation short circuit passed 70 compiled intermediate-state comparisons,
including VM-seeded negative zero and rejection before fixed-worker masking.
The first verification wrapper stopped because two offline-oracle import files
were missing from the test mirror, after generation and the existing planner and
reserve tests had passed. The missing test-only dependencies were copied; no
production change was needed. The fresh `ValidationMeasure.log` then passed the
complete targeted suite without Python, Blueprint or script runtime errors.

| Fixture | Planner calls | Observed total |
| --- | ---: | ---: |
| Unique best workers, reserve 1, equal builder quality | 5.796 s | 6.010 s |
| Unique best workers, reserve 3, equal builder quality | 5.971 s | 6.183 s |
| Unique best workers, reserve 3, varied builder quality | 12.908 s | 13.388 s |
| Tied productive quality, reserve 3, varied builder quality | 11.573 s | 11.918 s |
| Five priority tiers, strict, reserve 3, equal builder quality | 14.944 s | 15.315 s |
| Five priority tiers, weighted, reserve 3, equal builder quality | 6.293 s | 6.507 s |

All assignment hashes and objectives match Round7. Validation decreased to
4.53-4.72 seconds. The strict case is narrowly below 15 seconds of planner calls,
but its observed total still exceeds 15 seconds; this is not accepted as the
final timing checkpoint. Evidence, including the separate initial harness error,
is preserved in `Round8/`.

The next minimal candidate applies the same exact ordering to later-pass row
minimum caches: compare against the second minimum first, and inspect the minimum
only if needed. The invariant is `minimum <= second minimum`, including duplicate
minima. No template, field, arithmetic expression or work accounting changes.
The emitted-model regression first failed at 20,000 minimum-array reads against
an 11,000 ceiling, then passed at 10,337-10,497 on the same 10,000-cell shapes.
All 150,080 randomized cells and seeded caches preserve min1/min2/winner bits
and every write. Existing compiled sparse tests now also check both inherited
and planner second-minimum arrays for empty/forbidden rows. This candidate changes
only BuildPass and BatchBuildPass. The compiled targeted suite then passed,
including the strengthened sparse-cache assertions. Both six-case timing runs
and the complete editor suite passed, as summarized in `Verified Result` above.

## Remaining Limits

School search still considers distinct feasible profile combinations exactly.
Many different teacher profiles across many schools can therefore remain costly;
this change does not impose an approximation or an arbitrary candidate cutoff.
World changes can require the existing bounded replans. Native application still
performs at most one confirmed action per frame. A representative player save is
needed to measure the full in-game workflow.

The controller's EventTick pump has a soft 2 ms time slice (checked after each
call) and a 64-call cap. At 60 ticks per second, a rough 15-second CPU budget
therefore spans about 125 seconds of frame time before other phases; this is a
scheduling estimate, not a measured game result. The soft limit can overshoot by
one call. Application also consumes at least one tick per fire/hire action, so
1,000 actions alone require at least 16.7 seconds at 60 ticks per second. The
under-15-second planner target must not be described as an end-to-end game-time
guarantee. Controller scheduling and action confirmation are unchanged here.
