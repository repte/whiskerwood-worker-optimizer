"""Generate coverage-first staffing policy around the native assignment solver."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl
from planner_cost_dsl import (IMPLICIT_VARIABLES, accumulate_row_statistics, allowed_score,
                              first_pass_row_minimum, implicit_row_setup, implicit_score)
from planner_refine_bound_dsl import max_real_v_start, max_real_v_step, singleton_real_range
from planner_refine_cache_dsl import constant_real_score
from planner_refine_reconstruct_dsl import (RECONSTRUCTION_VARIABLES, start_reconstruction, start_payload,
    full_real_certificate, cache_lookup, cache_store, append_row, retain_dummy, finish_reconstruction)
from planner_validation_dsl import statistics as validation_statistics

ROOT = "/Game/Mods/WorkerOptimizer"
parent = unreal.load_class(None, ROOT + "/BP_AssignmentSolver.BP_AssignmentSolver_C")
assert parent, "Generate and test the assignment solver first"
bp = unreal.load_asset(ROOT + "/BP_StaffingPlanner")
if bp is None:
    bp = BP.create(ROOT, "BP_StaffingPlanner", parent)

types = {
    "bool": "PlanDone PlanSucceeded StrictMode FixedConfigured ReserveConfigured FlexibleConfigured FirstPass BuildMinimum BuildRealAllowed BuildDummyAllowed",
    "int": "State SlotCount WorkerCount BuildingCount CurrentBuilding CurrentSlot RootSlot QueueHead SearchRow FoundWorker AugmentRow PreviousWorker BestPriority Tier LowestTier BuildIndex BuildEnd ScanRow ScanWorker ScanPriority PlanValidationIndex PlanValidationEnd TierCount RealSlotCount ReserveCount PolicyCursor ReserveMovable ReserveRow DispatchState PolicyWork SolveColumns DummyRemaining UnionRow MatrixCells BuildBaseOffset BuildBuilding BuildMode BuildMultiplier SelectionTier SelectionCursor BuildRowOffset RetainedCursor RetainedEnd",
    "float": "MaxScore FillBonus CoverageBonus ColumnBonus EdgeScore ReducedCost TierScore BuilderTotal ReserveMinimumQuality StatsFirstScore StatsMaximumScore StatsPrefixScore MinimumScore MinimumScratch RefineRowPotential",
    "float[]": "BaseScores PassScores ExpectedScores ReserveQuality ExpandedScores PassRowMinCost RowFirstScore RowMaximumScore RowPrefixScore",
    "int[]": "SlotBuildings Priorities PlanAssignment CoverageSlotMatch CoverageWorkerMatch SavedSlotMatch SavedWorkerMatch ParentRow Queue MinimumCount SlotCountByBuilding ExpectedCounts FixedSlots FixedOwners PendingFixed DummyBuildings OpenCount OptionalOpenCount BuildingFirstRow BuildingLastRow NextBuildingRow PassRowMinColumn RetainedColumns RetainedRowOffsets",
    "bool[]": "Minimum Accepted Processed Visited ReservedWorker AllowedEdges AllowedEmpty RequiredWorker FlexibleMinimum BuildingHasFixed BuildingFilled ActiveTiers ReserveSelected",
}
types["int"] += " StatsOffset StatsEnd StatsFirstColumn StatsMaximumColumn MinimumColumn"
types["int[]"] += " RowFirstColumn RowMaximumColumn BuildingDummyStart BuildingDummyEnd"
types["float"] += " StatsSecondScore MinimumSecondScore"
types["float[]"] += " RowSecondScore PassRowSecondMinCost"
types["bool"] += " RetainedReady TemplatesReady BuildRowReady RefineInitialized RefineRowReady RefineSparse RefineDummyPhase"
types["int"] += " RefineRangeEnd RefineRead RefineWrite TemplatePlainColumn TemplateMinimumColumn"
types["float"] += " ValidatedScore TemplatePlainCost TemplatePlainSecond TemplateMinimumCost TemplateMinimumSecond"
types["float[]"] += " SentinelRow TemplatePlainRow TemplateMinimumRow"
types["bool"] += " RefineMaxVReady"
types["int"] += " RefineMaxVCursor RefineWinner"
types["float"] += " RefineMaxRealV"
for kind, names in RECONSTRUCTION_VARIABLES.items():
    types[kind] += ' ' + names
existing = set(BP.list_variables(bp))
for kind, names in types.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)

graphs = {}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
functions = ("FailPlan", "StartPlan", "RequireFixedSlots", "RequireFlexibleMinimum", "KeepUnassigned", "ValidateBlock", "SelectBuilding", "BeginCoverage", "CoverageStep", "BeginPass", "BuildPass", "SolvePass", "RefinePass", "PolicyStep", "BatchValidateBlock", "BatchExpandedScores", "BatchBuildPass", "BatchRefinePass", "BatchCoverage", "AdvancePlan")
for name in functions:
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
if "StartPlan" not in existing_graphs:
    for name, kind, array in (
        ("InputScores", "float", True), ("InputBuildings", "int", True),
        ("InputMinimum", "bool", True), ("InputPriorities", "int", True),
        ("InputWorkers", "int", False), ("InputStrict", "bool", False),
    ):
        BP.add_function_param(graphs["StartPlan"], name, kind, True, ContainerType.ARRAY if array else None)
if "RequireFixedSlots" not in existing_graphs:
    BP.add_function_param(graphs["RequireFixedSlots"], "InputFixed", "int", True, ContainerType.ARRAY)
    BP.add_function_param(graphs["RequireFixedSlots"], "Result", "bool", False)
if "KeepUnassigned" not in existing_graphs:
    BP.add_function_param(graphs["KeepUnassigned"], "Requested", "int", True)
    BP.add_function_param(graphs["KeepUnassigned"], "Movable", "int", True)
    BP.add_function_param(graphs["KeepUnassigned"], "Quality", "float", True, ContainerType.ARRAY)
    BP.add_function_param(graphs["KeepUnassigned"], "Result", "bool", False)
if "RequireFlexibleMinimum" not in existing_graphs:
    BP.add_function_param(graphs["RequireFlexibleMinimum"], "InputFlexible", "bool", True, ContainerType.ARRAY)
    BP.add_function_param(graphs["RequireFlexibleMinimum"], "Result", "bool", False)
BP.compile_blueprint(bp)
context = graphs["AdvancePlan"]
all_types = BP.find_node_types(context, "", [])


def node(ending):
    matches = [n for n in all_types if n.lower().endswith("|" + ending.lower())]
    for preferred in ("Variables|Default|" + ending, "CallFunction|" + ending):
        for match in matches:
            if match.lower() == preferred.lower():
                return match
    if len(matches) != 1:
        raise RuntimeError(f"Ambiguous node {ending}: {matches}")
    return matches[0]


def g(name):
    return f"({node('Get' + name)})"


def s(name, value):
    return f"({node('Set' + name)} {value})"


def a(name, index):
    return f'(Utilities|Array|Get(aref) :Array {g(name)} :"Dimension 1" {index})'


def set_a(name, index, value):
    return f"(Utilities|Array|SetArrayElem :TargetArray {g(name)} :Index {index} :Item {value})"


def reset(name, size):
    return f"(Utilities|Array|Clear {g(name)}) (Utilities|Array|Resize {g(name)} {size})"


def call(name, args=""):
    return f"({node(name)} {args})"


def length(name):
    return f"(Utilities|Array|Length {g(name)})"


code = {}
code["FailPlan"] = f"(fn FailPlan () {s('PlanDone', 'true')} {s('PlanSucceeded', 'false')})"
code["StartPlan"] = f"""
(fn StartPlan (InputScores InputBuildings InputMinimum InputPriorities InputWorkers InputStrict)
  {call('FailPlan')}
  {s('FixedConfigured', 'false')}
  {s('FlexibleConfigured', 'false')}
  {s('ReserveConfigured', 'false')} {s('ReserveCount', '0')}
  {s('FirstPass', 'true')} {s('ImplicitFirstPass', 'false')} {s('MatrixCells', '0')}
  {s('RetainedReady', 'false')} {s('RefineInitialized', 'false')}
  (Utilities|Array|Clear {g('PassScores')}) (Utilities|Array|Clear {g('AllowedEdges')})
  (Utilities|Array|Clear {g('RowFirstColumn')}) (Utilities|Array|Clear {g('RowMaximumColumn')})
  (Utilities|Array|Clear {g('RowFirstScore')}) (Utilities|Array|Clear {g('RowMaximumScore')}) (Utilities|Array|Clear {g('RowPrefixScore')})
  (Utilities|Array|Clear {g('RowSecondScore')})
  (Utilities|Array|Clear {g('RowAllReal')}) (Utilities|Array|Clear {g('RowUniformScore')})
  {s('StatsAllReal', 'true')} {s('StatsUniformScore', 'true')}
  {s('StatsOffset', '0')} {s('StatsEnd', 'InputWorkers')} {s('StatsFirstColumn', '0')} {s('StatsMaximumColumn', '0')}
  {s('StatsFirstScore', '-1e20')} {s('StatsMaximumScore', '-1e20')} {s('StatsPrefixScore', '-1e20')}
  {s('StatsSecondScore', '-1e20')}
  {s('SelectionTier', '4')} {s('SelectionCursor', '0')}
  {s('BuilderTotal', '0.0')}
  (Utilities|Array|Clear {g('PlanAssignment')})
  {s('SlotCount', '(Utilities|Array|Length InputBuildings)')}
  {s('RealSlotCount', g('SlotCount'))}
  {s('BuildingCount', '(Utilities|Array|Length InputPriorities)')}
  (if (or (or (< InputWorkers 0) (> InputWorkers 10000)) (or (> {g('SlotCount')} 10000) (> {g('BuildingCount')} 10000))) (return))
  (if (!= (Utilities|Array|Length InputMinimum) {g('SlotCount')}) (return))
  (if (!= (Utilities|Array|Length InputScores) (* {g('SlotCount')} InputWorkers)) (return))
  {s('WorkerCount', 'InputWorkers')} {s('StrictMode', 'InputStrict')}
  {s('BaseScores', 'InputScores')} {s('SlotBuildings', 'InputBuildings')}
  {s('Minimum', 'InputMinimum')} {s('Priorities', 'InputPriorities')}
  {reset('PlanAssignment', g('SlotCount'))}
  {reset('CoverageSlotMatch', g('SlotCount'))}
  {reset('CoverageWorkerMatch', 'InputWorkers')}
  {reset('FixedSlots', g('SlotCount'))} {reset('FixedOwners', 'InputWorkers')}
  {reset('ParentRow', 'InputWorkers')} {reset('Visited', 'InputWorkers')}
  {reset('ReservedWorker', 'InputWorkers')}
  {reset('ReserveSelected', 'InputWorkers')}
  {reset('RequiredWorker', 'InputWorkers')}
  {reset('AllowedEmpty', g('SlotCount'))}
  {reset('ExpectedCounts', '5')} {reset('ExpectedScores', '5')}
  {reset('ActiveTiers', '5')} {s('LowestTier', '5')}
  {reset('Accepted', g('BuildingCount'))} {reset('Processed', g('BuildingCount'))}
  {reset('MinimumCount', g('BuildingCount'))} {reset('SlotCountByBuilding', g('BuildingCount'))}
  {reset('FlexibleMinimum', g('BuildingCount'))} {reset('OpenCount', g('BuildingCount'))} {reset('OptionalOpenCount', g('BuildingCount'))}
  {reset('BuildingHasFixed', g('BuildingCount'))} {reset('BuildingFilled', g('BuildingCount'))}
  {reset('BuildingFirstRow', g('BuildingCount'))} {reset('BuildingLastRow', g('BuildingCount'))} {reset('NextBuildingRow', g('SlotCount'))}
  {reset('BuildingDummyStart', g('BuildingCount'))} {reset('BuildingDummyEnd', g('BuildingCount'))}
  (Utilities|Array|Clear {g('DummyBuildings')}) (Utilities|Array|Clear {g('ExpandedScores')})
  (Utilities|Array|Clear {g('RetainedColumns')}) (Utilities|Array|Clear {g('RetainedRowOffsets')})
  {s('PlanDone', 'false')}
  {s('MaxScore', '0.0')} {s('PlanValidationIndex', '0')}
  {s('PolicyCursor', '0')} {s('LastStepWork', '0')} {s('State', '10')})
"""
code["RequireFlexibleMinimum"] = f"""(fn RequireFlexibleMinimum (InputFlexible)
  (if (or {g('PlanDone')} (or {g('FlexibleConfigured')} (or (!= {g('State')} 10) (!= {g('PolicyCursor')} 0)))) (return false))
  (if (!= (Utilities|Array|Length InputFlexible) {g('BuildingCount')}) {call('FailPlan')} (return false))
  {s('FlexibleConfigured', 'true')} {s('FlexibleMinimum', 'InputFlexible')} (return true))"""

code["RequireFixedSlots"] = f"""
(fn RequireFixedSlots (InputFixed)
  (if (or {g('PlanDone')} (or {g('FixedConfigured')} (or (!= {g('State')} 10) (!= {g('PolicyCursor')} 0)))) (return false))
  (if (!= (Utilities|Array|Length InputFixed) {g('RealSlotCount')}) {call('FailPlan')} (return false))
  {s('FixedConfigured', 'true')} {s('PendingFixed', 'InputFixed')} (return true))
"""

code["KeepUnassigned"] = f"""
(fn KeepUnassigned (Requested Movable Quality)
  (if (or {g('PlanDone')} (or {g('ReserveConfigured')} (or (!= {g('State')} 10) (!= {g('PolicyCursor')} 0)))) (return false))
  (if (or (< Requested 0) (or (< Movable 0) (> Movable {g('WorkerCount')}))) {call('FailPlan')} (return false))
  (if (!= (Utilities|Array|Length Quality) {g('WorkerCount')}) {call('FailPlan')} (return false))
  {s('ReserveCount', '(select (< Requested Movable) Requested Movable)')}
  (if (> (+ {g('SlotCount')} {g('ReserveCount')}) 10000) {call('FailPlan')} (return false))
  {s('ReserveConfigured', 'true')} {s('ReserveMovable', 'Movable')} {s('ReserveQuality', 'Quality')}
  (return true))
"""

def validation_cell(stop):
    return f"""
    {s('ValidatedScore', a('BaseScores', 'n'))}
    (bind value {g('ValidatedScore')})
    (if (not (and (>= value -1e20) (<= value 1e6))) {call('FailPlan')} {stop})
    (if {g('FixedConfigured')}
      {s('ScanRow', f'(/ n {g("WorkerCount")})')} {s('ScanWorker', f'(- n (* {g("ScanRow")} {g("WorkerCount")}))')}
      (bind fixedWorker {a('FixedSlots', g('ScanRow'))}) (bind fixedOwner {a('FixedOwners', g('ScanWorker'))})
      (if (or (and (>= fixedWorker 0) (!= fixedWorker {g('ScanWorker')}))
        (and (>= fixedOwner 0) (!= fixedOwner {g('ScanRow')})))
        {set_a('BaseScores', 'n', '-1e20')} {s('ValidatedScore', '-1e20')}))
    {validation_statistics(g, s, value='value', column=f'(+ (- n {g("StatsOffset")}) 1)')}
    {s('PlanValidationIndex', f'(+ n 1)')}
    (if (== {g('PlanValidationIndex')} {g('StatsEnd')})
      (Utilities|Array|Add {g('RowFirstColumn')} {g('StatsFirstColumn')})
      (Utilities|Array|Add {g('RowMaximumColumn')} {g('StatsMaximumColumn')})
      (Utilities|Array|Add {g('RowFirstScore')} {g('StatsFirstScore')})
      (Utilities|Array|Add {g('RowMaximumScore')} {g('StatsMaximumScore')})
      (Utilities|Array|Add {g('RowPrefixScore')} {g('StatsPrefixScore')})
      (Utilities|Array|Add {g('RowSecondScore')} {g('StatsSecondScore')})
      (Utilities|Array|Add {g('RowAllReal')} {g('StatsAllReal')})
      (Utilities|Array|Add {g('RowUniformScore')} {g('StatsUniformScore')})
      {s('StatsAllReal', 'true')} {s('StatsUniformScore', 'true')}
      {s('StatsOffset', g('StatsEnd'))} {s('StatsEnd', f'(+ {g("StatsEnd")} {g("WorkerCount")})')}
      {s('StatsFirstColumn', '0')} {s('StatsMaximumColumn', '0')}
      {s('StatsFirstScore', '-1e20')} {s('StatsMaximumScore', '-1e20')} {s('StatsPrefixScore', '-1e20')} {s('StatsSecondScore', '-1e20')})
"""


validation_finish = f"""
  (bind capacity (+ {g('SlotCount')} 1))
  {s('FillBonus', f'(+ (* (+ (* {g("MaxScore")} 5.0) 1.0) capacity) 1.0)')}
  {s('CoverageBonus', f'(+ (* (+ (+ {g("FillBonus")} (* {g("MaxScore")} 5.0)) 1.0) capacity) 1.0)')}
  {s('ColumnBonus', f'(+ (* (+ (+ (+ {g("CoverageBonus")} {g("FillBonus")} ) (* {g("MaxScore")} 5.0)) 1.0) capacity) 1.0)')}
  {s('PolicyCursor', '0')} {s('CurrentBuilding', '-1')} {s('BestPriority', '-1')} {s('State', '19')}
"""
code["ValidateBlock"] = f"""
(fn ValidateBlock ()
  (bind n {g('PlanValidationIndex')})
  (if (< n {length('BaseScores')}) {validation_cell('(return)')} (return))
  {validation_finish})
"""
code["BatchValidateBlock"] = f"""
(fn BatchValidateBlock ()
  (for work (range {g('StepWorkLimit')})
    {s('LastStepWork', '(+ work 1)')}
    (bind n {g('PlanValidationIndex')})
    (if (< n {length('BaseScores')}) {validation_cell('(break)')}
      (else {validation_finish} (break)))))
"""

code["SelectBuilding"] = f"""
(fn SelectBuilding ()
  (if (< {g('SelectionTier')} 0) {s('Tier', '4')} {s('PolicyCursor', '0')} {s('State', '20')} (return))
  (if (not {a('ActiveTiers', g('SelectionTier'))})
    {s('SelectionTier', f'(- {g("SelectionTier")} 1)')} {s('SelectionCursor', '0')} (return))
  (bind b {g('SelectionCursor')})
  (if (>= b {g('BuildingCount')})
    {s('SelectionTier', f'(- {g("SelectionTier")} 1)')} {s('SelectionCursor', '0')} (return))
  (if (and (not {a('Processed', 'b')}) (== {a('Priorities', 'b')} {g('SelectionTier')}))
    {s('CurrentBuilding', 'b')} {s('BestPriority', g('SelectionTier'))}
    {set_a('Processed', g('CurrentBuilding'), 'true')}
    {s('SavedSlotMatch', g('CoverageSlotMatch'))} {s('SavedWorkerMatch', g('CoverageWorkerMatch'))}
    {s('CurrentSlot', a('BuildingFirstRow', g('CurrentBuilding')))} {s('State', '2')})
  {s('SelectionCursor', '(+ b 1)')})
"""

code["BeginCoverage"] = f"""
(fn BeginCoverage ()
  (bind r {g('CurrentSlot')})
  (if (< r 0)
    (if (and (== r -1) (and {a('FlexibleMinimum', g('CurrentBuilding'))} (not {a('BuildingHasFixed', g('CurrentBuilding'))})))
      {s('RootSlot', f'(+ {g("SlotCount")} {g("CurrentBuilding")})')} {s('ScanWorker', '0')} {s('State', '21')}
      {s('CurrentSlot', '-2')} (return))
    {set_a('Accepted', g('CurrentBuilding'), 'true')}
    {s('PolicyCursor', '0')} {s('CurrentBuilding', '-1')} {s('BestPriority', '-1')} {s('State', '1')} (return))
  (if (and (and (== {a('SlotBuildings', 'r')} {g('CurrentBuilding')}) {a('Minimum', 'r')}) (< {a('FixedSlots', 'r')} 0))
    {s('RootSlot', 'r')} {s('ScanWorker', '0')} {s('State', '21')})
  {s('CurrentSlot', a('NextBuildingRow', 'r'))})
"""

virtual_building = f"(- {g('SearchRow')} {g('SlotCount')})"
reset_union = f"(if (>= {g('SearchRow')} {g('SlotCount')}) {s('UnionRow', a('BuildingFirstRow', virtual_building))} (else {s('UnionRow', '0')}))"
code["CoverageStep"] = f"""
(fn CoverageStep ()
  (if (>= {g('QueueHead')} {length('Queue')})
    {s('CoverageSlotMatch', g('SavedSlotMatch'))} {s('CoverageWorkerMatch', g('SavedWorkerMatch'))}
    {s('PolicyCursor', '0')} {s('CurrentBuilding', '-1')} {s('BestPriority', '-1')} {s('State', '1')} (return))
  {s('SearchRow', a('Queue', g('QueueHead')))} {s('QueueHead', f'(+ {g("QueueHead")} 1)')}
  {s('FoundWorker', '-1')} {s('ScanWorker', '0')} {reset_union} {s('State', '24')})
"""

code["BeginPass"] = f"""
(fn BeginPass ()
  ; Empty tiers have a constant zero objective, so they cannot restrict a plan.
  (if {g('StrictMode')}
    (for skipped (range 5)
      (if (< {g('Tier')} 0) (break))
      (if {a('ActiveTiers', g('Tier'))} (break))
      {s('Tier', f'(- {g("Tier")} 1)')}))
  (if {g('FirstPass')}
    {s('ImplicitScores', g('BaseScores'))} {s('ImplicitWorkerCount', g('WorkerCount'))}
    {s('ImplicitFillBonus', g('FillBonus'))} {s('ImplicitCoverageBonus', g('CoverageBonus'))} {s('ImplicitColumnBonus', g('ColumnBonus'))}
    {' '.join(reset(name, g('SlotCount')) for name, (_, array) in IMPLICIT_VARIABLES.items() if array and name != 'ImplicitScores')}
    {reset('PassRowMinCost', g('SlotCount'))} {reset('PassRowMinColumn', g('SlotCount'))}
    {reset('PassRowSecondMinCost', g('SlotCount'))}
    (else
      (Utilities|Array|Clear {g('PassScores')})
      (Utilities|Array|Clear {g('SentinelRow')}) (Utilities|Array|Clear {g('TemplatePlainRow')})
      (Utilities|Array|Clear {g('TemplateMinimumRow')})
      {s('TemplatePlainCost', '1e20')} {s('TemplatePlainSecond', '1e20')} {s('TemplatePlainColumn', '1')}
      {s('TemplateMinimumCost', '1e20')} {s('TemplateMinimumSecond', '1e20')} {s('TemplateMinimumColumn', '1')}))
  {s('TemplatesReady', 'false')} {s('BuildRowReady', 'false')} {s('RefineInitialized', 'false')}
  {s('BuildIndex', '0')} {s('ScanRow', '0')} {s('ScanWorker', '0')} {s('BuildBaseOffset', '0')}
  {s('BuildRowOffset', '0')} {s('RetainedCursor', '0')} {s('RetainedEnd', '0')}
  {s('State', '4')})
"""

base_pass_score = a('BaseScores', f'(+ {g("BuildBaseOffset")} {g("ScanWorker")})')
# Row properties are stored explicitly; DSL bind only aliases a pure graph pin.
build_row_setup = f"""
    {s('BuildBuilding', a('SlotBuildings', g('ScanRow')))}
    {s('BuildMinimum', a('Minimum', g('ScanRow')))}
    {s('BuildRealAllowed', f'(or {a("Accepted", g("BuildBuilding"))} (>= {a("FixedSlots", g("ScanRow"))} 0))')}
    {s('BuildDummyAllowed', f'(and (< {a("FixedSlots", g("ScanRow"))} 0) (not (and {g("BuildMinimum")} {a("Accepted", g("BuildBuilding"))})))')}
    {s('ScanPriority', a('Priorities', g('BuildBuilding')))}
    {s('BuildMultiplier', f'(+ {g("ScanPriority")} 1)')} {s('BuildMode', '0')}
    (if (and (>= {g('ScanPriority')} 0) (>= {g('Tier')} 0))
      (if (not {g('StrictMode')}) {s('BuildMode', '2')}
        (elif (== {g('ScanPriority')} {g('Tier')}) {s('BuildMode', '1')}))
      (elif (and (< {g('ScanPriority')} 0) (< {g('Tier')} 0)) {s('BuildMode', '3')}))
"""
score_allowed_edge = allowed_score(
    g, s, output='EdgeScore', base=base_pass_score, mode=g('BuildMode'),
    multiplier=g('BuildMultiplier'), minimum=g('BuildMinimum'),
    required=a('RequiredWorker', g('ScanWorker')), fill=g('FillBonus'),
    coverage=g('CoverageBonus'), column=g('ColumnBonus'),
    real=f'(< {g("ScanWorker")} {g("WorkerCount")})')
build_implicit_row = f"""
  {build_row_setup}
  {set_a('ImplicitModes', g('ScanRow'), g('BuildMode'))}
  {set_a('ImplicitMultipliers', g('ScanRow'), g('BuildMultiplier'))}
  {set_a('ImplicitMinimumRows', g('ScanRow'), g('BuildMinimum'))}
  {set_a('ImplicitRealRows', g('ScanRow'), g('BuildRealAllowed'))}
  {set_a('ImplicitDummyRows', g('ScanRow'), g('BuildDummyAllowed'))}
  {set_a('ImplicitFixedWorkers', g('ScanRow'), a('FixedSlots', g('ScanRow')))}
  {set_a('ImplicitDummyStarts', g('ScanRow'), a('BuildingDummyStart', g('BuildBuilding')))}
  {set_a('ImplicitDummyEnds', g('ScanRow'), a('BuildingDummyEnd', g('BuildBuilding')))}
  {first_pass_row_minimum(g, s, score_output='MinimumScore', column_output='MinimumColumn', scratch_output='MinimumScratch', first_column=a('RowFirstColumn', g('ScanRow')), first_score=a('RowFirstScore', g('ScanRow')), maximum_column=a('RowMaximumColumn', g('ScanRow')), maximum_score=a('RowMaximumScore', g('ScanRow')), prefix_score=a('RowPrefixScore', g('ScanRow')), mode=g('BuildMode'), multiplier=g('BuildMultiplier'), minimum=g('BuildMinimum'), fixed=a('FixedSlots', g('ScanRow')), real_allowed=g('BuildRealAllowed'), dummy_allowed=g('BuildDummyAllowed'), dummy_start=a('BuildingDummyStart', g('BuildBuilding')), dummy_end=a('BuildingDummyEnd', g('BuildBuilding')), fill=g('FillBonus'), coverage=g('CoverageBonus'), column=g('ColumnBonus'), second_score=a('RowSecondScore', g('ScanRow')), second_output='MinimumSecondScore')}
  {set_a('PassRowMinCost', g('ScanRow'), f'(- {g("MinimumScore")})')}
  {set_a('PassRowMinColumn', g('ScanRow'), g('MinimumColumn'))}
  {set_a('PassRowSecondMinCost', g('ScanRow'), f'(- {g("MinimumSecondScore")})')}
  {s('ScanRow', f'(+ {g("ScanRow")} 1)')} {s('BuildIndex', f'(+ {g("BuildIndex")} 1)')}
"""
def template_minimum(prefix):
    return f"""
    (if (< (- {g('EdgeScore')}) {g(prefix + 'Cost')})
      {s(prefix + 'Second', g(prefix + 'Cost'))}
      {s(prefix + 'Cost', f'(- {g("EdgeScore")})')}
      {s(prefix + 'Column', f'(+ {g("ScanWorker")} 1)')}
      (elif (< (- {g('EdgeScore')}) {g(prefix + 'Second')})
        {s(prefix + 'Second', f'(- {g("EdgeScore")})')}))
"""


template_cell = f"""
  (Utilities|Array|Add {g('SentinelRow')} -1e20)
  {s('EdgeScore', '-1e20')}
  (if (< {g('ScanWorker')} {g('WorkerCount')})
    {s('EdgeScore', '0.0')}
    (if {a('RequiredWorker', g('ScanWorker'))} {s('EdgeScore', f'(+ {g("EdgeScore")} {g("ColumnBonus")})')}))
  (Utilities|Array|Add {g('TemplatePlainRow')} {g('EdgeScore')})
  {template_minimum('TemplatePlain')}
  {s('EdgeScore', '-1e20')}
  (if (< {g('ScanWorker')} {g('WorkerCount')})
    {s('EdgeScore', f'(+ 0.0 {g("CoverageBonus")})')}
    (if {a('RequiredWorker', g('ScanWorker'))} {s('EdgeScore', f'(+ {g("EdgeScore")} {g("ColumnBonus")})')}))
  (Utilities|Array|Add {g('TemplateMinimumRow')} {g('EdgeScore')})
  {template_minimum('TemplateMinimum')}
  {s('ScanWorker', f'(+ {g("ScanWorker")} 1)')}
"""
build_row_finish = f"""
  {s('ScanRow', f'(+ {g("ScanRow")} 1)')}
  {s('BuildBaseOffset', f'(+ {g("BuildBaseOffset")} {g("WorkerCount")})')}
  {s('BuildRowOffset', f'(+ {g("BuildRowOffset")} {g("SolveColumns")})')}
  {s('BuildRowReady', 'false')}
"""
# Sorted unique CSR columns certify a complete real-worker prefix in O(1).
build_sparse_row = f"""
  {build_row_setup}
  {s('RetainedCursor', a('RetainedRowOffsets', g('ScanRow')))}
  {s('RetainedEnd', a('RetainedRowOffsets', f'(+ {g("ScanRow")} 1)'))}
  {s('BuildRowReady', 'true')} {s('BuildRealAllowed', 'false')}
  (if (and (== {g('BuildMode')} 0) (> {g('WorkerCount')} 0))
    (if (>= (- {g('RetainedEnd')} {g('RetainedCursor')}) {g('WorkerCount')})
      (if (== {a('RetainedColumns', f'(- (+ {g("RetainedCursor")} {g("WorkerCount")}) 1)')} (- {g('WorkerCount')} 1))
        {s('BuildRealAllowed', 'true')})))
  (if {g('BuildRealAllowed')}
    (if {g('BuildMinimum')}
      (Utilities|Array|AppendArray {g('PassScores')} {g('TemplateMinimumRow')})
      {set_a('PassRowMinCost', g('ScanRow'), g('TemplateMinimumCost'))}
      {set_a('PassRowSecondMinCost', g('ScanRow'), g('TemplateMinimumSecond'))}
      {set_a('PassRowMinColumn', g('ScanRow'), g('TemplateMinimumColumn'))}
      (else
        (Utilities|Array|AppendArray {g('PassScores')} {g('TemplatePlainRow')})
        {set_a('PassRowMinCost', g('ScanRow'), g('TemplatePlainCost'))}
        {set_a('PassRowSecondMinCost', g('ScanRow'), g('TemplatePlainSecond'))}
        {set_a('PassRowMinColumn', g('ScanRow'), g('TemplatePlainColumn'))}))
    {s('RetainedCursor', f'(+ {g("RetainedCursor")} {g("WorkerCount")})')}
    (else
      (Utilities|Array|AppendArray {g('PassScores')} {g('SentinelRow')})
      {set_a('PassRowMinCost', g('ScanRow'), '1e20')}
      {set_a('PassRowSecondMinCost', g('ScanRow'), '1e20')}
      {set_a('PassRowMinColumn', g('ScanRow'), '1')}))
"""
build_sparse_cell = f"""
  (if (not {g('BuildRowReady')}) {build_sparse_row}
    (else
    {s('ScanWorker', a('RetainedColumns', g('RetainedCursor')))}
    (bind n (+ {g('BuildRowOffset')} {g('ScanWorker')}))
    {score_allowed_edge}
    {set_a('PassScores', 'n', g('EdgeScore'))}
    (if (< (- {g('EdgeScore')}) {a('PassRowSecondMinCost', g('ScanRow'))})
      (if (< (- {g('EdgeScore')}) {a('PassRowMinCost', g('ScanRow'))})
        {set_a('PassRowSecondMinCost', g('ScanRow'), a('PassRowMinCost', g('ScanRow')))}
        {set_a('PassRowMinCost', g('ScanRow'), f'(- {g("EdgeScore")})')}
        {set_a('PassRowMinColumn', g('ScanRow'), f'(+ {g("ScanWorker")} 1)')}
        (else {set_a('PassRowSecondMinCost', g('ScanRow'), f'(- {g("EdgeScore")})')})))
    {s('RetainedCursor', f'(+ {g("RetainedCursor")} 1)')}))
  {s('BuildIndex', f'(+ {g("BuildIndex")} 1)')}
  (if (>= {g('RetainedCursor')} {g('RetainedEnd')})
    {build_row_finish})
"""
build_has_work = f'(or (< {g("ScanRow")} {g("SlotCount")}) (and (not {g("FirstPass")}) (not {g("TemplatesReady")})))'
build_item = f"""
  (if {g('FirstPass')} {build_implicit_row}
    (elif (not {g('TemplatesReady')})
      (if (< {g('ScanWorker')} {g('SolveColumns')}) {template_cell}
        (else {s('TemplatesReady', 'true')} {s('ScanWorker', '0')}))
      (else {build_sparse_cell})))
"""
initialize_pass = f"""
  (if {g('FirstPass')}
    {call('InitializeImplicitFirstPass', f':RowCount {g("SlotCount")} :ColumnCount {g("SolveColumns")}')}
    (else
      {call('Initialize', f':IncomingScores {g("PassScores")} :RowCount {g("SlotCount")} :ColumnCount {g("SolveColumns")}')}
      ; Validated base scores and the slot cap bound generated costs below 1e20.
      {s('ValidationIndex', length('PassScores'))} {s('SolverState', '1')}
      {call('RestrictDummies', f':Mask {g("AllowedEmpty")}')}))
  {s('RowMinCost', g('PassRowMinCost'))} {s('RowMinColumn', g('PassRowMinColumn'))}
  {s('RowSecondMinCost', g('PassRowSecondMinCost'))}
  {s('NativePlannerTrusted', 'true')} {s('NativeCsrReady', 'false')}
  (if (and (not {g('FirstPass')}) {g('RetainedReady')})
    {s('NativeRowOffsets', g('RetainedRowOffsets'))} {s('NativeColumns', g('RetainedColumns'))}
    {s('NativeCsrReady', 'true')})
  {s('FirstPass', 'false')} {s('State', '5')}
"""
code["BuildPass"] = f"""
(fn BuildPass ()
  (if {build_has_work} {build_item} (return))
  {initialize_pass})
"""

code["SolvePass"] = f"""
(fn SolvePass ()
  (if (not {g('Succeeded')}) {call('FailPlan')} (return))
  {s('TierCount', '0')} {s('TierScore', '0.0')} {s('PolicyCursor', '0')} {s('State', '7')})
"""

row_potential = g('RefineRowPotential')
worker_potential = a('V', f"(+ {g('ScanWorker')} 1)")
refine_pass_start = f"""
  {s('RefineInitialized', 'true')} {s('RefineRowReady', 'false')}
  {max_real_v_start(g, s)}
  {s('RefineSparse', f'(and {g("RetainedReady")} (not {g("ImplicitFirstPass")}))')}
  {s('ScanRow', '0')} {s('ScanWorker', '0')} {s('BuildRowOffset', '0')}
  {s('RefineRead', '0')} {s('RefineWrite', '0')}
  (if (not {g('RefineSparse')})
    (Utilities|Array|Clear {g('RetainedColumns')})
    {reset('RetainedRowOffsets', f'(+ {g("SlotCount")} 1)')})
  (if {g('ImplicitFirstPass')}
    (Utilities|Array|Clear {g('PassScores')}) {reset('AllowedEdges', g('MatrixCells'))})
"""
refine_row_finish = f"""
  {s('ScanRow', f'(+ {g("ScanRow")} 1)')} {s('ScanWorker', '0')}
  {s('BuildRowOffset', f'(+ {g("BuildRowOffset")} {g("SolveColumns")})')}
  {s('RefineRowReady', 'false')}
"""
refine_row_setup = f"""
  {s('RefineRowPotential', a('U', f'(+ {g("ScanRow")} 1)'))}
  {s('RefineRowReady', 'true')}
  (if {g('RefineSparse')}
    {s('RetainedEnd', a('RetainedRowOffsets', f'(+ {g("ScanRow")} 1)'))})
  {set_a('RetainedRowOffsets', g('ScanRow'), g('RefineWrite'))}
  {set_a('PassRowMinCost', g('ScanRow'), '1e20')}
  {set_a('PassRowMinColumn', g('ScanRow'), '1')}
  {set_a('PassRowSecondMinCost', g('ScanRow'), '1e20')}
"""
refine_start_dummy = f"""
  {s('RefineDummyPhase', 'true')} {s('ScanWorker', g('ImplicitDummyStart'))}
  {s('RefineRangeEnd', g('ImplicitDummyStart'))}
  (if {g('ImplicitDummyAllowed')} {s('RefineRangeEnd', g('ImplicitDummyEnd'))})
  (if (>= {g('ScanWorker')} {g('RefineRangeEnd')}) {refine_row_finish})
"""
refine_implicit_row = f"""
  {refine_row_setup}
  {implicit_row_setup(g, s, a, g('ScanRow'))}
  {s('RefineDummyPhase', 'false')} {s('ScanWorker', '0')} {s('RefineRangeEnd', '0')}
  (if {g('ImplicitRealAllowed')}
    {s('RefineRangeEnd', g('WorkerCount'))}
    (if (>= {g('ImplicitFixedWorker')} 0)
      {s('ScanWorker', g('ImplicitFixedWorker'))}
      {s('RefineRangeEnd', f'(+ {g("ScanWorker")} 1)')})
    {singleton_real_range(g, s, a)})
  (if (>= {g('ScanWorker')} {g('RefineRangeEnd')}) {refine_start_dummy})
"""
refine_implicit_cell = f"""
  (bind n (+ {g('BuildRowOffset')} {g('ScanWorker')}))
  {implicit_score(g, s, a, g('ScanWorker'), output='EdgeScore')}
  (if (>= {g('EdgeScore')} 0.0)
    {s('ReducedCost', f'(- (- (- {g("EdgeScore")}) {row_potential}) {worker_potential})')}
    (if (and (>= {g('ReducedCost')} -0.00001) (<= {g('ReducedCost')} 0.00001))
      {set_a('AllowedEdges', 'n', 'true')}
      (Utilities|Array|Add {g('RetainedColumns')} {g('ScanWorker')})
      {s('RefineWrite', f'(+ {g("RefineWrite")} 1)')}))
  {s('ScanWorker', f'(+ {g("ScanWorker")} 1)')}
  (if (>= {g('ScanWorker')} {g('RefineRangeEnd')})
    (if {g('RefineDummyPhase')} {refine_row_finish}
      (else {refine_start_dummy})))
"""
refine_dense_edge = f"""
  (bind n (+ {g('BuildRowOffset')} {g('ScanWorker')}))
  {s('ReducedCost', f'(- (- (- {a("PassScores", "n")}) {row_potential}) {worker_potential})')}
  (if (and (>= {g('ReducedCost')} -0.00001) (<= {g('ReducedCost')} 0.00001))
    (if {g('RefineSparse')}
      {set_a('RetainedColumns', g('RefineWrite'), g('ScanWorker'))}
      (else (Utilities|Array|Add {g('RetainedColumns')} {g('ScanWorker')})))
    {s('RefineWrite', f'(+ {g("RefineWrite")} 1)')}
    (else {set_a('AllowedEdges', 'n', 'false')} {set_a('PassScores', 'n', '-1e20')}))
"""
refine_sparse_cell = f"""
  (if (not {g('RefineRowReady')}) {refine_row_setup})
  (if (< {g('RefineRead')} {g('RetainedEnd')})
    {s('ScanWorker', a('RetainedColumns', g('RefineRead')))}
    {refine_dense_edge}
    {s('RefineRead', f'(+ {g("RefineRead")} 1)')})
  (if (>= {g('RefineRead')} {g('RetainedEnd')}) {refine_row_finish})
"""
# Direct dense callers have no CSR until their first refinement completes.
refine_pass_cell = f"""
  (if (not {g('RefineRowReady')}) {refine_row_setup})
  (if (< {g('ScanWorker')} {g('SolveColumns')})
    (if {a('AllowedEdges', f'(+ {g("BuildRowOffset")} {g("ScanWorker")})')} {refine_dense_edge})
    {s('ScanWorker', f'(+ {g("ScanWorker")} 1)')})
  (if (>= {g('ScanWorker')} {g('SolveColumns')}) {refine_row_finish})
"""
refine_pass_finish = f"""
  (if {g('RefineSparse')} (Utilities|Array|Resize {g('RetainedColumns')} {g('RefineWrite')}))
  {set_a('RetainedRowOffsets', g('SlotCount'), g('RefineWrite'))}
  {s('RetainedReady', 'true')}
  {s('PolicyCursor', '0')} {s('State', '30')}
"""
legacy_refine_item = f"""
  (if (not {g('RefineInitialized')}) {refine_pass_start}
    (elif (not {g('RefineMaxVReady')}) {max_real_v_step(g, s, a)}
      (elif (>= {g('ScanRow')} {g('SlotCount')}) {refine_pass_finish}
        (elif {g('ImplicitFirstPass')}
          (if (not {g('RefineRowReady')}) {refine_implicit_row}
            (else {refine_implicit_cell}))
          (elif {g('RefineSparse')} {refine_sparse_cell}
            (else {refine_pass_cell}))))))
  {s('BuildIndex', f'(+ {g("BuildIndex")} 1)')}
"""

reconstruct_start = f"""
  {s('RefineInitialized', 'true')} {s('RefineStage', '0')}
  {s('ScanRow', '0')} {s('ScanWorker', '0')} {s('BuildRowOffset', '0')}
  {max_real_v_start(g, s)} {s('RefineMaxVReady', f'(== {g("WorkerCount")} 0)')}
  {start_reconstruction(g, s)}
"""
reconstruct_finish_row = f"""
  {s('ScanRow', f'(+ {g("ScanRow")} 1)')} {s('ScanWorker', '0')}
  {s('BuildRowOffset', f'(+ {g("BuildRowOffset")} {g("SolveColumns")})')}
  {s('RefineStage', '0')}
"""
# A full real prefix has its dummy suffix exactly W entries after the start.
# Partial later rows keep ordinary CSR traversal, including singleton rows.
reconstruct_real_end = f"""
  (if {g('ImplicitFirstPass')}
    (if (>= {g('ScanWorker')} {g('RefineRangeEnd')}) {s('RefineStage', '2')})
    (elif {g('RefineSingleton')} {s('RefineStage', '2')}
      (elif (>= {g('RefineRead')} {g('RefineOldEnd')}) {s('RefineStage', '2')}
        (else (if (>= {a('RetainedColumns', g('RefineRead'))} {g('WorkerCount')}) {s('RefineStage', '2')})))))
"""
reconstruct_row = f"""
  {s('RefineRowPotential', a('U', f'(+ {g("ScanRow")} 1)'))}
  {set_a('PassRowMinCost', g('ScanRow'), '1e20')}
  {set_a('PassRowMinColumn', g('ScanRow'), '1')}
  {set_a('PassRowSecondMinCost', g('ScanRow'), '1e20')}
  {s('RefineSingleton', 'false')} {s('RefineConstantReal', 'false')} {s('RefineConstantScore', '0.0')}
  (if {g('ImplicitFirstPass')}
    {implicit_row_setup(g, s, a, g('ScanRow'))}
    {s('BuildMinimum', g('ImplicitMinimum'))}
    (else {build_row_setup}
      {s('RefineOldStart', a('RetainedRowOffsets', g('ScanRow')))}
      {s('RefineOldEnd', a('RetainedRowOffsets', f'(+ {g("ScanRow")} 1)'))}))
  {full_real_certificate(g, s, a)}
  (if {g('RefineFullReal')}
    (if {g('ImplicitFirstPass')}
      {constant_real_score(g, s, a, mode=g('ImplicitMode'), multiplier=g('ImplicitMultiplier'), minimum=g('ImplicitMinimum'), fill=g('ImplicitFillBonus'), coverage=g('ImplicitCoverageBonus'), column=g('ImplicitColumnBonus'))}
      (else {constant_real_score(g, s, a)})))
  (if (or (and {g('ImplicitFirstPass')} {g('ImplicitRealAllowed')}) {g('RefineFullReal')})
    {s('RefineWinner', a('RowMinColumn', g('ScanRow')))}
    (if (and (> {g('RefineWinner')} 0) (<= {g('RefineWinner')} {g('WorkerCount')}))
      (if (> (- (- {a('RowSecondMinCost', g('ScanRow'))} {g('RefineRowPotential')}) {g('RefineMaxRealV')}) 0.00001)
        {s('RefineSingleton', 'true')})))
  {cache_lookup(g, s)}
  (if {g('RefineCacheHit')}
    {s('RefineStage', '2')}
    (if (not {g('ImplicitFirstPass')}) {s('RefineRead', f'(+ {g("RefineOldStart")} {g("WorkerCount")})')})
    (else
      {start_payload(g, s)} {s('RefineStage', '1')}
      (if {g('ImplicitFirstPass')}
        {s('ScanWorker', '0')} {s('RefineRangeEnd', '0')}
        (if {g('ImplicitRealAllowed')}
          {s('RefineRangeEnd', g('WorkerCount'))}
          (if (>= {g('ImplicitFixedWorker')} 0)
            {s('ScanWorker', g('ImplicitFixedWorker'))} {s('RefineRangeEnd', f'(+ {g("ScanWorker")} 1)')}))
        (if {g('RefineSingleton')}
          {s('ScanWorker', f'(- {g("RefineWinner")} 1)')} {s('RefineRangeEnd', f'(+ {g("ScanWorker")} 1)')})
        (else
          {s('RefineRead', g('RefineOldStart'))}
          (if {g('RefineSingleton')}
            {s('ScanWorker', f'(- {g("RefineWinner")} 1)')}
            {s('RefineRead', f'(+ {g("RefineOldStart")} {g("WorkerCount")})')})))
      (if {g('ImplicitFirstPass')}
        (if (>= {g('ScanWorker')} {g('RefineRangeEnd')}) {s('RefineStage', '2')})
        (elif (not {g('RefineSingleton')}) {reconstruct_real_end}))))
"""
reconstruct_load_score = f"""
  (if {g('ImplicitFirstPass')}
    {implicit_score(g, s, a, g('ScanWorker'), output='EdgeScore')}
    (else {s('EdgeScore', a('PassScores', f'(+ {g("BuildRowOffset")} {g("ScanWorker")})'))}))
"""
reconstruct_tight = f'(and (>= {g("ReducedCost")} -0.00001) (<= {g("ReducedCost")} 0.00001))'
reconstruct_reduced = s('ReducedCost', f'(- (- (- {g("EdgeScore")}) {row_potential}) {worker_potential})')
reconstruct_real = f"""
  (if (and (not {g('ImplicitFirstPass')}) (not {g('RefineSingleton')}))
    {s('ScanWorker', a('RetainedColumns', g('RefineRead')))})
  {reconstruct_load_score}
  (if (>= {g('EdgeScore')} 0.0)
    {reconstruct_reduced}
    (if {reconstruct_tight}
      {set_a('RefineRowMask', g('ScanWorker'), 'true')}
      (if (not {g('ImplicitFirstPass')}) {set_a('RefineRowScores', g('ScanWorker'), g('EdgeScore'))})
      (Utilities|Array|Add {g('RefineRealColumns')} {g('ScanWorker')})))
  (if {g('ImplicitFirstPass')} {s('ScanWorker', f'(+ {g("ScanWorker")} 1)')}
    (elif (not {g('RefineSingleton')}) {s('RefineRead', f'(+ {g("RefineRead")} 1)')}))
  {reconstruct_real_end}
"""
reconstruct_append = f"""
  {cache_store(g, s)} {append_row(g)} {s('RefineStage', '3')}
  (if {g('ImplicitFirstPass')}
    {s('ScanWorker', g('ImplicitDummyStart'))} {s('RefineRangeEnd', g('ImplicitDummyStart'))}
    (if {g('ImplicitDummyAllowed')} {s('RefineRangeEnd', g('ImplicitDummyEnd'))})
    (if (>= {g('ScanWorker')} {g('RefineRangeEnd')}) {reconstruct_finish_row})
    (else (if (>= {g('RefineRead')} {g('RefineOldEnd')}) {reconstruct_finish_row})))
"""
reconstruct_dummy = f"""
  (if (not {g('ImplicitFirstPass')}) {s('ScanWorker', a('RetainedColumns', g('RefineRead')))})
  {reconstruct_load_score}
  (if (>= {g('EdgeScore')} 0.0)
    {reconstruct_reduced}
    (if {reconstruct_tight} {retain_dummy(g, set_a)}))
  (if {g('ImplicitFirstPass')}
    {s('ScanWorker', f'(+ {g("ScanWorker")} 1)')}
    (if (>= {g('ScanWorker')} {g('RefineRangeEnd')}) {reconstruct_finish_row})
    (else {s('RefineRead', f'(+ {g("RefineRead")} 1)')}
      (if (>= {g('RefineRead')} {g('RefineOldEnd')}) {reconstruct_finish_row})))
"""
refine_item = f"""
  (if (not {g('RefineInitialized')})
    {s('RefineReconstruct', f'(or {g("ImplicitFirstPass")} (and {g("RetainedReady")} (== {length("SentinelRow")} {g("SolveColumns")})))')})
  (if {g('RefineReconstruct')}
    (if (not {g('RefineInitialized')}) {reconstruct_start}
      (elif (not {g('RefineMaxVReady')}) {max_real_v_step(g, s, a)}
        (elif (>= {g('ScanRow')} {g('SlotCount')})
          {finish_reconstruction(g, s)} {s('PolicyCursor', '0')} {s('State', '30')}
          (elif (== {g('RefineStage')} 0) {reconstruct_row}
            (elif (== {g('RefineStage')} 1) {reconstruct_real}
              (elif (== {g('RefineStage')} 2) {reconstruct_append}
                (else {reconstruct_dummy})))))))
    {s('BuildIndex', f'(+ {g("BuildIndex")} 1)')}
    (else {legacy_refine_item}))
"""
code["RefinePass"] = f"""
(fn RefinePass ()
  {refine_item})
"""

policy_worker_score = a('BaseScores', f'(+ (* i {g("WorkerCount")}) worker)')
coverage_index = f"(+ (* {g('ScanRow')} {g('WorkerCount')}) w)"
coverage_edge = f"""
  (if (and (not {a('Visited', 'w')}) (>= {a('BaseScores', coverage_index)} 0.0))
    {set_a('Visited', 'w', 'true')} {set_a('ParentRow', 'w', g('SearchRow'))}
    (if (< {a('CoverageWorkerMatch', 'w')} 0) {s('FoundWorker', 'w')} {s('State', '22')}
      (else (Utilities|Array|Add {g('Queue')} {a('CoverageWorkerMatch', 'w')})))
    {s('ScanWorker', '(+ w 1)')} {reset_union}
    (else
      (if (>= {g('SearchRow')} {g('SlotCount')}) {s('UnionRow', a('NextBuildingRow', g('ScanRow')))}
        (else {s('ScanWorker', '(+ w 1)')}))))
"""
# Structured branches let a batch continue skipped workers without returning
# from its loop, while retaining one unit per worker or virtual-row probe.
coverage_scan_item = f"""
  (bind w {g('ScanWorker')})
  (if (< w {g('WorkerCount')})
    (if {a('Visited', 'w')} {s('ScanWorker', '(+ w 1)')} {reset_union}
      (else
        (if (>= {g('SearchRow')} {g('SlotCount')})
          (if (< {g('UnionRow')} 0) {s('ScanWorker', '(+ w 1)')} {reset_union}
            (else
              {s('ScanRow', g('UnionRow'))}
              (if (>= {a('FixedSlots', g('ScanRow'))} 0)
                {s('UnionRow', a('NextBuildingRow', g('ScanRow')))}
                (else {coverage_edge}))))
          (else {s('ScanRow', g('SearchRow'))} {coverage_edge}))))
    (else {s('State', '3')}))
"""
# Each helper executes one primitive item or one constant-size transition.
# Solver Advance owns the entire budget when delegated; never nest two budgets.
code["PolicyStep"] = f"""
(fn PolicyStep ()
  (bind state {g('State')}) (bind i {g('PolicyCursor')})
  (switch int state
    (:0 {call('ValidateBlock')})
    (:1 {call('SelectBuilding')})
    (:2 {call('BeginCoverage')})
    (:3 {call('CoverageStep')})
    (:4 {call('BuildPass')})
    (:5 {call('SolvePass')})
    (:6 {call('RefinePass')})
    (:10
      (if (< i {g('BuildingCount')})
        {set_a('BuildingFirstRow', 'i', '-1')} {set_a('BuildingLastRow', 'i', '-1')}
        (if (or (< {a('Priorities', 'i')} 0) (> {a('Priorities', 'i')} 4)) {call('FailPlan')})
        {s('PolicyCursor', '(+ i 1)')}
        (else {s('PolicyCursor', '0')} {s('State', '11')})))
    (:11
      (if (< i {g('RealSlotCount')})
        {set_a('PlanAssignment', 'i', '-1')} {set_a('CoverageSlotMatch', 'i', '-1')}
        {set_a('FixedSlots', 'i', '-1')} {set_a('AllowedEmpty', 'i', 'true')}
        {set_a('NextBuildingRow', 'i', '-1')}
        (bind building {a('SlotBuildings', 'i')})
        (if (or (< building 0) (>= building {g('BuildingCount')})) {call('FailPlan')}
          (else
            (bind tier {a('Priorities', 'building')})
            {set_a('ActiveTiers', 'tier', 'true')}
            (if (< tier {g('LowestTier')}) {s('LowestTier', 'tier')})
            {set_a('SlotCountByBuilding', 'building', f'(+ {a("SlotCountByBuilding", "building")} 1)')}
            (if {a('Minimum', 'i')} {set_a('MinimumCount', 'building', f'(+ {a("MinimumCount", "building")} 1)')})
            (if (< {a('BuildingFirstRow', 'building')} 0) {set_a('BuildingFirstRow', 'building', 'i')}
              (else {set_a('NextBuildingRow', a('BuildingLastRow', 'building'), 'i')}))
            {set_a('BuildingLastRow', 'building', 'i')}))
        {s('PolicyCursor', '(+ i 1)')}
        (else {s('PolicyCursor', '0')} {s('State', '12')})))
    (:12
      (if (< i {g('BuildingCount')})
        (if (== {a('SlotCountByBuilding', 'i')} 0) {set_a('Processed', 'i', 'true')}
          (else
            (if (and (== {a('MinimumCount', 'i')} 0) (not {a('FlexibleMinimum', 'i')})) {call('FailPlan')})
            (if (and (> {a('MinimumCount', 'i')} 0) {a('FlexibleMinimum', 'i')}) {call('FailPlan')})))
        {s('PolicyCursor', '(+ i 1)')}
        (else {s('PolicyCursor', '0')} {s('State', '13')})))
    (:13
      (if (< i {g('WorkerCount')})
        {set_a('CoverageWorkerMatch', 'i', '-1')} {set_a('FixedOwners', 'i', '-1')} {s('PolicyCursor', '(+ i 1)')}
        (else {s('PolicyCursor', '0')} {s('State', '14')})))
    (:14
      (if (and {g('FixedConfigured')} (< i {g('RealSlotCount')}))
        (bind worker {a('PendingFixed', 'i')})
        (if (or (< worker -1) (>= worker {g('WorkerCount')})) {call('FailPlan')}
          (elif (>= worker 0)
            (if (or (>= {a('FixedOwners', 'worker')} 0)
              (not (>= {a('BaseScores', f'(+ (* i {g("WorkerCount")}) worker)')} 0.0))) {call('FailPlan')}
              (else
                {set_a('FixedOwners', 'worker', 'i')} {set_a('CoverageWorkerMatch', 'worker', 'i')}
                {set_a('CoverageSlotMatch', 'i', 'worker')} {set_a('AllowedEmpty', 'i', 'false')}
                {set_a('RequiredWorker', 'worker', 'true')} {set_a('FixedSlots', 'i', 'worker')}))))
        {s('PolicyCursor', '(+ i 1)')}
        (else {s('PolicyCursor', '0')} {s('State', '15')})))
    (:15
      (if (and (> {g('ReserveCount')} 0) (< i {g('WorkerCount')}))
        (bind quality {a('ReserveQuality', 'i')})
        (if (not (and (>= quality 0.0) (<= quality 1000000.0))) {call('FailPlan')})
        {s('PolicyCursor', '(+ i 1)')}
        (else {s('State', '16')})))
    (:16
      (if (> {g('ReserveCount')} 0)
        (Utilities|Array|Add {g('Priorities')} -1) (Utilities|Array|Add {g('Accepted')} true)
        (Utilities|Array|Add {g('Processed')} true) (Utilities|Array|Add {g('MinimumCount')} {g('ReserveCount')})
        (Utilities|Array|Add {g('SlotCountByBuilding')} {g('ReserveCount')})
        (Utilities|Array|Add {g('FlexibleMinimum')} false) (Utilities|Array|Add {g('BuildingHasFixed')} false)
        (Utilities|Array|Add {g('OpenCount')} 0) (Utilities|Array|Add {g('OptionalOpenCount')} 0) (Utilities|Array|Add {g('BuildingFilled')} false)
        (Utilities|Array|Add {g('BuildingFirstRow')} -1) (Utilities|Array|Add {g('BuildingLastRow')} -1)
        (Utilities|Array|Add {g('BuildingDummyStart')} 0) (Utilities|Array|Add {g('BuildingDummyEnd')} 0)
        {s('ReserveRow', '0')} {s('State', '17')}
        (else
          (if (or (== {g('SlotCount')} 0) (== {g('WorkerCount')} 0))
            {s('PlanDone', 'true')} {s('PlanSucceeded', 'true')}
            (else {s('State', '0')})))))
    (:17
      (if (< {g('ReserveRow')} {g('ReserveCount')})
        (Utilities|Array|Add {g('SlotBuildings')} {g('BuildingCount')}) (Utilities|Array|Add {g('Minimum')} true)
        (Utilities|Array|Add {g('FixedSlots')} -1) (Utilities|Array|Add {g('AllowedEmpty')} false)
        (Utilities|Array|Add {g('PlanAssignment')} -1) (Utilities|Array|Add {g('CoverageSlotMatch')} -1)
        (Utilities|Array|Add {g('NextBuildingRow')} -1)
        {s('FoundWorker', '-1')} {s('ScanWorker', '0')} {s('State', '18')}
        (else
          {s('SlotCount', f'(+ {g("RealSlotCount")} {g("ReserveCount")})')}
          {s('BuildingCount', f'(+ {g("BuildingCount")} 1)')} {s('State', '0')})))
    (:18
      (bind w {g('ScanWorker')})
      (if (< w {g('WorkerCount')})
        (bind eligible (and (< w {g('ReserveMovable')}) (< {a('FixedOwners', 'w')} 0)))
        (Utilities|Array|Add {g('BaseScores')} (select eligible {a('ReserveQuality', 'w')} -1e20))
        (if (and eligible (and (< {g('FoundWorker')} 0) (< {a('CoverageWorkerMatch', 'w')} 0))) {s('FoundWorker', 'w')})
        {s('ScanWorker', '(+ w 1)')}
        (else
          (if (< {g('FoundWorker')} 0) {call('FailPlan')}
            (else
              (bind row (+ {g('RealSlotCount')} {g('ReserveRow')}))
              {set_a('CoverageSlotMatch', 'row', g('FoundWorker'))} {set_a('CoverageWorkerMatch', g('FoundWorker'), 'row')}
              {s('ReserveRow', f'(+ {g("ReserveRow")} 1)')} {s('State', '17')})))))
    (:21
      {reset('Visited', g('WorkerCount'))}
      {s('ScanWorker', g('WorkerCount'))}
      (Utilities|Array|Clear {g('Queue')}) (Utilities|Array|Add {g('Queue')} {g('RootSlot')})
      {s('QueueHead', '0')} {s('State', '3')})
    (:24 {coverage_scan_item})
    (:22
      (if (>= {g('FoundWorker')} 0)
        {s('AugmentRow', a('ParentRow', g('FoundWorker')))} {s('PreviousWorker', a('CoverageSlotMatch', g('AugmentRow')))}
        {set_a('CoverageSlotMatch', g('AugmentRow'), g('FoundWorker'))}
        {set_a('CoverageWorkerMatch', g('FoundWorker'), g('AugmentRow'))} {s('FoundWorker', g('PreviousWorker'))}
        (else {s('State', '2')})))
    (:7
      (if (or (< i {g('SolveColumns')}) (< i {g('BuildingCount')}))
        (if (< i {g('SolveColumns')}) {set_a('ReservedWorker', 'i', 'false')})
        (if (< i {g('BuildingCount')}) {set_a('BuildingFilled', 'i', 'false')}) {s('PolicyCursor', '(+ i 1)')}
        (else {s('PolicyCursor', '0')} {s('State', '8')})))
    (:8
      (if (< i {g('SlotCount')})
        (bind building {a('SlotBuildings', 'i')}) (bind worker {a('Assignment', 'i')})
        (if (and (>= worker 0) (< worker {g('SolveColumns')}))
          {set_a('ReservedWorker', 'worker', 'true')}
          (bind n (+ (* i {g('SolveColumns')}) worker))
          (if {g('ImplicitFirstPass')}
            {implicit_row_setup(g, s, a, 'i')}
            {implicit_score(g, s, a, 'worker', output='EdgeScore')}
            (if (< {g('EdgeScore')} 0.0) {call('FailPlan')})
            (else (if (not {a('AllowedEdges', 'n')}) {call('FailPlan')})))
          (if (and (>= {a('FixedSlots', 'i')} 0) (!= worker {a('FixedSlots', 'i')})) {call('FailPlan')})
          (if (< worker {g('WorkerCount')})
            {set_a('BuildingFilled', 'building', 'true')}
            (if (== {a('Priorities', 'building')} {g('Tier')})
              {s('TierCount', f'(+ {g("TierCount")} 1)')} {s('TierScore', f'(+ {g("TierScore")} {policy_worker_score})')}))
          (else {call('FailPlan')}))
        {s('PolicyCursor', '(+ i 1)')}
        (else {s('PolicyCursor', '0')} {s('State', '9')})))
    (:9
      (if (< i {g('SolveColumns')})
        (if (and {a('RequiredWorker', 'i')} (not {a('ReservedWorker', 'i')})) {call('FailPlan')}) {s('PolicyCursor', '(+ i 1)')}
        (else {s('PolicyCursor', '0')} {s('State', '31')})))
    (:31
      (if (< i {g('BuildingCount')})
        (if (and {a('FlexibleMinimum', 'i')} (and {a('Accepted', 'i')} (not {a('BuildingFilled', 'i')}))) {call('FailPlan')})
        {s('PolicyCursor', '(+ i 1)')}
        (else
          (if (>= {g('Tier')} 0)
            {set_a('ExpectedCounts', g('Tier'), g('TierCount'))} {set_a('ExpectedScores', g('Tier'), g('TierScore'))})
          (if (or (< {g('Tier')} 0) (and (== {g('ReserveCount')} 0) (or (not {g('StrictMode')}) (== {g('Tier')} {g('LowestTier')}))))
            {s('BuilderTotal', '0.0')} {s('PolicyCursor', g('RealSlotCount'))} {s('State', '25')}
            (elif (or (not {g('StrictMode')}) (== {g('Tier')} {g('LowestTier')}))
              {s('ReserveMinimumQuality', '1e20')} {s('PolicyCursor', g('RealSlotCount'))} {s('State', '33')}
              (else {s('BuildIndex', '0')} {s('State', '6')}))))))
    (:33
      (if (< i {g('SlotCount')})
        (bind worker {a('Assignment', 'i')})
        (if (or (< worker 0) (>= worker {g('WorkerCount')})) {call('FailPlan')}
          (elif (or (>= worker {g('ReserveMovable')}) (or (>= {a('FixedOwners', 'worker')} 0) {a('ReserveSelected', 'worker')}))
            {call('FailPlan')}
            (else
              {set_a('ReserveSelected', 'worker', 'true')}
              (bind quality {a('ReserveQuality', 'worker')})
              (if (< quality {g('ReserveMinimumQuality')}) {s('ReserveMinimumQuality', 'quality')}))))
        {s('PolicyCursor', '(+ i 1)')}
        (else {s('PolicyCursor', '0')} {s('State', '34')})))
    (:34
      ; The current reserve is globally top-R exactly when no eligible outsider
      ; exceeds its lowest quality. This certificate needs no rounded sum.
      (if (< i {g('WorkerCount')})
        (if (and (and (< i {g('ReserveMovable')}) (< {a('FixedOwners', 'i')} 0))
          (and (not {a('ReserveSelected', 'i')}) (> {a('ReserveQuality', 'i')} {g('ReserveMinimumQuality')})))
          {s('BuildIndex', '0')} {s('State', '6')}
          (else {s('PolicyCursor', '(+ i 1)')}))
        (else {s('BuilderTotal', '0.0')} {s('PolicyCursor', g('RealSlotCount'))} {s('State', '25')})))
    (:25
      (if (< i {g('SlotCount')})
        (bind worker {a('Assignment', 'i')})
        (if (< worker 0) {call('FailPlan')}
          (else {s('BuilderTotal', f'(+ {g("BuilderTotal")} {policy_worker_score})')}))
        {s('PolicyCursor', '(+ i 1)')}
        (else
          {s('PlanAssignment', g('Assignment'))} (Utilities|Array|Resize {g('PlanAssignment')} {g('RealSlotCount')})
          {s('PolicyCursor', '0')} {s('State', '32')})))
    (:32
      (if (< i {g('RealSlotCount')})
        (if (>= {a('PlanAssignment', 'i')} {g('WorkerCount')}) {set_a('PlanAssignment', 'i', '-1')})
        {s('PolicyCursor', '(+ i 1)')}
        (else
          (if {g('StrictMode')} {s('Tier', '0')} {s('PolicyCursor', '0')} {s('TierCount', '0')} {s('TierScore', '0.0')} {s('State', '27')}
            (else {s('PlanDone', 'true')} {s('PlanSucceeded', 'true')})))))
    (:27
      (if (< i {g('RealSlotCount')})
        (bind building {a('SlotBuildings', 'i')}) (bind worker {a('PlanAssignment', 'i')})
        (if (and (>= worker 0) (== {a('Priorities', 'building')} {g('Tier')}))
          {s('TierCount', f'(+ {g("TierCount")} 1)')}
          {s('TierScore', f'(+ {g("TierScore")} {policy_worker_score})')})
        {s('PolicyCursor', '(+ i 1)')}
        (else
          (bind difference (- {g('TierScore')} {a('ExpectedScores', g('Tier'))}))
          (if (or (!= {g('TierCount')} {a('ExpectedCounts', g('Tier'))}) (or (> difference 0.0001) (< difference -0.0001))) {call('FailPlan')}
            (else (if (== {g('Tier')} 4) {s('PlanDone', 'true')} {s('PlanSucceeded', 'true')}
              (else {s('Tier', f'(+ {g("Tier")} 1)')} {s('PolicyCursor', '0')} {s('TierCount', '0')} {s('TierScore', '0.0')})))))))
    (:29 {call('FailPlan')})
    (:30
      (if (< i {g('SolveColumns')})
        (if (< {a('V', '(+ i 1)')} -0.00001) {set_a('RequiredWorker', 'i', 'true')})
        {s('PolicyCursor', '(+ i 1)')}
        (else {s('Tier', f'(select {g("StrictMode")} (- {g("Tier")} 1) -1)')} {call('BeginPass')})))
    (:19
      (if (< i {g('SlotCount')})
        (bind b {a('SlotBuildings', 'i')})
        (if (>= {a('FixedSlots', 'i')} 0) {set_a('BuildingHasFixed', 'b', 'true')}
          (else {set_a('OpenCount', 'b', f'(+ {a("OpenCount", "b")} 1)')}
            (if (not {a('Minimum', 'i')}) {set_a('OptionalOpenCount', 'b', f'(+ {a("OptionalOpenCount", "b")} 1)')})))
        {s('PolicyCursor', '(+ i 1)')}
        (elif (< i (+ {g('SlotCount')} {g('BuildingCount')}))
          (Utilities|Array|Add {g('CoverageSlotMatch')} -1) {s('PolicyCursor', '(+ i 1)')}
          (else {s('PolicyCursor', '0')} {s('State', '1')}))))
    (:20
      (if (< i {g('BuildingCount')})
        {s('CurrentBuilding', 'i')} {s('DummyRemaining', a('OpenCount', 'i'))}
        (if {a('Accepted', 'i')}
          (if {a('FlexibleMinimum', 'i')}
            (if (not {a('BuildingHasFixed', 'i')}) {s('DummyRemaining', f'(- {g("DummyRemaining")} 1)')})
            (else {s('DummyRemaining', a('OptionalOpenCount', 'i'))})))
        (if (< {g('DummyRemaining')} 0) {call('FailPlan')})
        {set_a('BuildingDummyStart', 'i', f'(+ {g("WorkerCount")} {length("DummyBuildings")})')}
        {set_a('BuildingDummyEnd', 'i', f'(+ (+ {g("WorkerCount")} {length("DummyBuildings")}) {g("DummyRemaining")})')}
        {s('PolicyCursor', '(+ i 1)')} {s('State', '23')}
        (else
          {s('SolveColumns', f'(+ {g("WorkerCount")} {length("DummyBuildings")})')}
          (if (> {g('SolveColumns')} 10000) {call('FailPlan')} (return))
          {s('MatrixCells', f'(* {g("SlotCount")} {g("SolveColumns")})')}
          (Utilities|Array|Resize {g('RequiredWorker')} {g('SolveColumns')})
          (Utilities|Array|Resize {g('ReservedWorker')} {g('SolveColumns')})
          {s('BuildIndex', '0')} {s('State', '26')})))
    (:23
      (if (> {g('DummyRemaining')} 0)
        (Utilities|Array|Add {g('DummyBuildings')} {g('CurrentBuilding')}) {s('DummyRemaining', f'(- {g("DummyRemaining")} 1)')}
        (else {s('State', '20')})))
    (:26 {s('PolicyCursor', '0')} {s('State', '28')})
    (:28
      (if (< i {g('SlotCount')}) {set_a('AllowedEmpty', 'i', 'false')} {s('PolicyCursor', '(+ i 1)')}
        (else {s('CurrentBuilding', '-1')} {call('BeginPass')})))
    (:Default {call('FailPlan')})))
"""
# Keep the one-item entry points for callers that explicitly advance PolicyStep.
# Dense phases avoid recreating that large function frame and switch per cell.
code["BatchExpandedScores"] = f"""
(fn BatchExpandedScores ()
  {s('LastStepWork', '1')} {s('PolicyCursor', '0')} {s('State', '28')})
"""

code["BatchBuildPass"] = f"""
(fn BatchBuildPass ()
  (for work (range {g('StepWorkLimit')})
    {s('LastStepWork', '(+ work 1)')}
    (if {build_has_work} {build_item}
      (else {initialize_pass}
        {s('LastStepWork', '(+ work 1)')} (break)))))
"""

code["BatchRefinePass"] = f"""
(fn BatchRefinePass ()
  (for work (range {g('StepWorkLimit')})
    {s('LastStepWork', '(+ work 1)')}
    {refine_item}
    (if (!= {g('State')} 6) (break))))
"""

code["BatchCoverage"] = f"""
(fn BatchCoverage ()
  (for work (range {g('StepWorkLimit')})
    {s('LastStepWork', '(+ work 1)')}
    {coverage_scan_item}
    (if (!= {g('State')} 24) (break))))
"""

code["AdvancePlan"] = f"""
(fn AdvancePlan ()
  {s('LastStepWork', '0')} (if {g('PlanDone')} (return))
  (if (<= {g('StepWorkLimit')} 0) {call('FailPlan')} (return))
  (if (and (== {g('State')} 5) (not {g('Done')})) {call('Advance')} (return))
  (if (== {g('State')} 0) {call('BatchValidateBlock')} (return))
  (if (== {g('State')} 26) {call('BatchExpandedScores')} (return))
  (if (== {g('State')} 4) {call('BatchBuildPass')} (return))
  (if (== {g('State')} 6) {call('BatchRefinePass')} (return))
  (if (== {g('State')} 24) {call('BatchCoverage')} (return))
  {s('PolicyWork', '0')}
  (for work (range {g('StepWorkLimit')})
    {s('PolicyWork', '(+ work 1)')} {call('PolicyStep')}
    (if (or {g('PlanDone')} (or (== {g('State')} 0) (or (== {g('State')} 5)
      (or (== {g('State')} 26) (or (== {g('State')} 4) (or (== {g('State')} 6) (== {g('State')} 24))))))) (break)))
  {s('LastStepWork', g('PolicyWork'))})
"""

for source in code.values():
    blueprint_dsl.parse(source)
for name in functions:
    unreal.log("WO_PLANNER_GENERATE " + name)
    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(graphs[name], code[name])
    Path(unreal.Paths.project_saved_dir(), f"WorkerOptimizer-Policy-{name}.dsl").write_text(code[name], encoding="utf-8")
with toolset_registry.tool_raising_exceptions():
    BP.compile_blueprint(bp, warnings_as_errors=True)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
unreal.log("WO_PLANNER_GENERATED")
exec(Path(__file__).with_name("test_planner.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_reserve.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_reserve_bound.py").read_text(encoding="utf-8"))
