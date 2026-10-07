# Native Workplace Capability

## Status and Scope

Native inspection was performed against installed Whiskerwood **0.7.209.0** and
its matching reflection map. This documents a verified adapter defect and the
required compatibility boundary, **not a successful in-game repair**. Editor
fixtures, package checks and the user's subsequent game test are separate.

## Observed Failure

The live diagnostic identified two rejected hires into building ID 723,
`tinywarehouse`, slot 0. Worker 31 had education 9; worker 53 had education 0.
Both had no workplace, the target slot was empty, its requirement was 0, and
the detail-widget context matched the intended building. The first run had
confirmed one fire before this hire; the next rejected the hire as its first
action. These observations do not indicate a failed fire or an education-mask
mismatch.

A read-only spawn of the cooked tinywarehouse Blueprint in the editor identified
`GranaryResourceBuilding` as its worker-bearing native component. This establishes
the asset's component type, not successful native assignment in the editor.

## Verified Native Boundary

- `GranaryResourceBuilding` inherits `ResourceBuilding.m_workers`. A reflected
  workforce field does **not** establish native assignment capability.
- Both classes use the same `AgentEnterable.GetMutableWorkerAssignment`
  implementation, which returns null. Their shared `GetWorkerAssignmentDetails`
  therefore returns false.
- `SelectTool.ReceiveHudAction` checks those details before dispatching
  `hireWorkerForSlot`. False returns without dispatching the hire.
- The alternate `INCREASE_WORKERS` action also reads those details. With no
  returned slots, it performs no hire. The shared `AssignWorkerToSlot` itself
  also stops when the mutable workforce is null.
- These are synchronous rejections, not delayed assignment completion.

`ReadWorkplace` must exclude the `ResourceBuilding` native family from planning
before any worker is fired for its slots. This is a **version-bound native API
limitation**, not a list of building names or a claim about every possible game
employment mechanism. `ReadComponent` must continue reading its reflected slots
so existing occupants remain protected by the snapshot's unsupported-building
path. Exclusion must not make those incumbents available to other buildings.

## Bounded Component Check

All 20 component types in `Docs/WorkerOptimizer/WORKPLACE-COMPATIBILITY.json`
and their native subclasses in the reflection map were checked. There was one
additional native subclass: `GranaryResourceBuilding`.

Only `ResourceBuilding` and `GranaryResourceBuilding` had the null getter. The
other 19 returned a non-null address within their component instance directly:

`ConstructionYard`, `ConsumptionOffice`, `CoordinationOffice`, `DefensiveTower`,
`FarmBuilding`, `FoodDistributor`, `HarvestingCamp`, `Industry`,
`JobTicketDispenserBuilding`, `LogisticsHub`, `PackageDelivery`, `ResearchLab`,
`School`, `TaxOffice`, `TerraformBuilding`, `TerraformCamp`, `TradePort`,
`TriageBuilding` and `WorkDock`.

Each getter's vtable entry was compared with the installed executable; all
matched. This excludes the same null-getter defect in that inspected set. It
does not prove every building asset, admission condition or future subtype works.
Editor fixtures with writable `m_workers` do not reproduce shipping native
capability merely by supplying that field.

## Repair Verification

The focused editor regression failed against the previous adapter with
`ResourceBuilding exposes legacy slots but has no native assignable workforce`
(`WorkerOptimizer-NativeWorkplaceRED.log`). After adding the family guard to
`ReadWorkplace`, the same test passed (`WorkerOptimizer-NativeWorkplaceGREEN.log`,
`WO_WORKPLACE_TESTS_PASS`) for both `ResourceBuilding` and its granary subclass.

The regression verifies exclusion from planning, unchanged reflected slots,
protection of existing occupants even when their reported workplace is absent,
and admission of a neighboring `Industry`. Existing supported component and
ambiguous-workplace tests still pass. The change does not add a new hiring path,
retry rejected hires, or weaken native result confirmation. Shipping assignment
completion still requires the user's in-game acceptance test.

The full editor suite completed with `WO_ALL_TESTS_PASS`, followed by
`WO_PACKAGE_VALIDATION_TESTS_PASS`, a successful cook, and
`WO_PACKAGE_TESTS_PASS`. Local build `20261007-020343-ebffe6a9` contains 46 assets
and 92 entries; its 511849-byte package has SHA256
`AC695198689AF7B8EAFF77C09A471B7CF67DD2D575A48F2E3E9C1542D1AF4605`.

After the user closed the game, this package replaced only the local subscribed
Workshop copy. The prior diagnostic package was backed up, and the installed
hash was checked against the verified delivery. No save files were changed,
and nothing was published to GitHub or Workshop. Game acceptance is pending.

## Publication Build

For v0.3.1-preview the temporary diagnostic extension was removed. The
controller source, diagnostic tests and compiled controller match the existing
public baseline; only the workplace adapter, its regression test, compiled
adapter and external version descriptor differ in the runtime/source scope.

The final build `20261007-021632-78718a80` passed the full editor suite
(`WO_ALL_TESTS_PASS`), package validation, Windows cook and package integrity
checks (`WO_PACKAGE_TESTS_PASS`). The delivery contains 46 assets and 92 entries.
Its 509801-byte PAK has SHA256
`23286757F75BA0A70339B0594FFBDAC3B4CE44736B654CB6E652BD4844590F14`.
The source and build-project runtime assets were compared before packaging.
Shipping-game acceptance remains pending; Workshop submission is separate.

## Evidence

- Matching `Content/DynamicClasses/Whiskerwood-0.7.209.0.jmap.gz`, native class
  inheritance, reflected members and vtables; read-only `inspect_native.py`.
- Native inspection locations: shared details getter RVA `0x491d270`, null
  mutable getter `0x491d340`, shared assignment `0x49be9f0`, HUD hire details
  check `0x4b4c50f`, and `INCREASE_WORKERS` details check `0x4be22fa`.
  These addresses are investigation evidence only; the mod does not use them.
- Local modkit logs: `Saved/Logs/WorkerOptimizer-InspectTinyWarehouse.log`,
  lines 3211-3212, and `WorkerOptimizer-NativeWorkerActions.txt` for the HUD path.
- Adapter source: `Automation/WorkerOptimizer/generate_workplace.py`,
  `ReadWorkplace` versus `ReadComponent`.

The earlier [manual-core verification](2026-10-07-manual-core.md) checked native
hire/fire implementation pointers. That alone did not establish whether each
component exposes the workforce those implementations require.
