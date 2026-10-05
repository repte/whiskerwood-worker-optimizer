"""Generate coverage-first staffing policy around the native assignment solver."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
parent = unreal.load_class(None, ROOT + "/BP_AssignmentSolver.BP_AssignmentSolver_C")
assert parent, "Generate and test the assignment solver first"
bp = unreal.load_asset(ROOT + "/BP_StaffingPlanner")
if bp is None:
    bp = BP.create(ROOT, "BP_StaffingPlanner", parent)

types = {
    "bool": "PlanDone PlanSucceeded StrictMode FixedConfigured ReserveConfigured",
    "int": "State SlotCount WorkerCount BuildingCount CurrentBuilding CurrentSlot RootSlot QueueHead SearchRow FoundWorker AugmentRow PreviousWorker BestPriority Tier BuildIndex BuildEnd ScanRow ScanWorker ScanPriority PlanValidationIndex PlanValidationEnd TierCount RealSlotCount ReserveCount",
    "float": "MaxScore FillBonus CoverageBonus ColumnBonus EdgeScore ReducedCost TierScore BuilderTotal",
    "float[]": "BaseScores PassScores ExpectedScores",
    "int[]": "SlotBuildings Priorities PlanAssignment CoverageSlotMatch CoverageWorkerMatch SavedSlotMatch SavedWorkerMatch ParentRow Queue MinimumCount SlotCountByBuilding ExpectedCounts FixedSlots FixedOwners",
    "bool[]": "Minimum Accepted Processed Visited ReservedWorker AllowedEdges AllowedEmpty RequiredWorker",
}
existing = set(BP.list_variables(bp))
for kind, names in types.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)

graphs = {}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
functions = ("FailPlan", "StartPlan", "RequireFixedSlots", "KeepUnassigned", "ValidateBlock", "SelectBuilding", "BeginCoverage", "CoverageStep", "BeginPass", "BuildPass", "SolvePass", "RefinePass", "AdvancePlan")
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
    return f'(Utilities|Array|Get(acopy) :Array {g(name)} :"Dimension 1" {index})'


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
  {s('ReserveConfigured', 'false')} {s('ReserveCount', '0')}
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
  {reset('RequiredWorker', 'InputWorkers')}
  {reset('AllowedEmpty', g('SlotCount'))}
  {reset('AllowedEdges', f'(* {g("SlotCount")} InputWorkers)')}
  {reset('ExpectedCounts', '5')} {reset('ExpectedScores', '5')}
  {reset('Accepted', g('BuildingCount'))} {reset('Processed', g('BuildingCount'))}
  {reset('MinimumCount', g('BuildingCount'))} {reset('SlotCountByBuilding', g('BuildingCount'))}
  {s('PlanDone', 'false')}
  (for b (range {g('BuildingCount')})
    (if (or (< {a('Priorities', 'b')} 0) (> {a('Priorities', 'b')} 4)) {call('FailPlan')} (break)))
  (if {g('PlanDone')} (return))
  (for r (range {g('SlotCount')})
    {set_a('PlanAssignment', 'r', '-1')} {set_a('CoverageSlotMatch', 'r', '-1')}
    {set_a('FixedSlots', 'r', '-1')}
    {set_a('AllowedEmpty', 'r', 'true')}
    (bind building {a('SlotBuildings', 'r')})
    (if (or (< building 0) (>= building {g('BuildingCount')})) {call('FailPlan')} (break))
    {set_a('SlotCountByBuilding', 'building', f'(+ {a("SlotCountByBuilding", "building")} 1)')}
    (if {a('Minimum', 'r')} {set_a('MinimumCount', 'building', f'(+ {a("MinimumCount", "building")} 1)')}))
  (if {g('PlanDone')} (return))
  (for b (range {g('BuildingCount')})
    (if (== {a('SlotCountByBuilding', 'b')} 0)
      {set_a('Processed', 'b', 'true')}
      (elif (== {a('MinimumCount', 'b')} 0) {call('FailPlan')} (break))))
  (if {g('PlanDone')} (return))
  (for w (range InputWorkers) {set_a('CoverageWorkerMatch', 'w', '-1')} {set_a('FixedOwners', 'w', '-1')})
  {s('MaxScore', '0.0')} {s('PlanValidationIndex', '0')} {s('State', '0')}
  (if (or (== {g('SlotCount')} 0) (== InputWorkers 0))
    {s('PlanDone', 'true')} {s('PlanSucceeded', 'true')}))
"""

code["RequireFixedSlots"] = f"""
(fn RequireFixedSlots (InputFixed)
  (if (or {g('PlanDone')} (or {g('FixedConfigured')} (or (!= {g('State')} 0) (!= {g('PlanValidationIndex')} 0)))) (return false))
  {s('FixedConfigured', 'true')}
  (if (!= (Utilities|Array|Length InputFixed) {g('SlotCount')}) {call('FailPlan')} (return false))
  (for r (range {g('SlotCount')})
    (bind worker (Utilities|Array|Get(acopy) :Array InputFixed :"Dimension 1" r))
    (if (or (< worker -1) (>= worker {g('WorkerCount')})) {call('FailPlan')} (return false))
    (if (>= worker 0)
      (if (>= {a('FixedOwners', 'worker')} 0) {call('FailPlan')} (return false))
      (if (not (>= {a('BaseScores', f'(+ (* r {g("WorkerCount")}) worker)')} 0.0)) {call('FailPlan')} (return false))
      {set_a('FixedOwners', 'worker', 'r')}
      {set_a('CoverageWorkerMatch', 'worker', 'r')}
      {set_a('CoverageSlotMatch', 'r', 'worker')}
      {set_a('AllowedEmpty', 'r', 'false')}
      {set_a('RequiredWorker', 'worker', 'true')}))
  {s('FixedSlots', 'InputFixed')}
  (return true))
"""

code["KeepUnassigned"] = f"""
(fn KeepUnassigned (Requested Movable Quality)
  (if (or {g('PlanDone')} (or {g('ReserveConfigured')} (or (!= {g('State')} 0) (!= {g('PlanValidationIndex')} 0)))) (return false))
  (if (or (< Requested 0) (or (< Movable 0) (> Movable {g('WorkerCount')}))) {call('FailPlan')} (return false))
  (if (!= (Utilities|Array|Length Quality) {g('WorkerCount')}) {call('FailPlan')} (return false))
  {s('ReserveConfigured', 'true')}
  {s('ReserveCount', '(select (< Requested Movable) Requested Movable)')}
  (if (== {g('ReserveCount')} 0) (return true))
  (if (> (+ {g('SlotCount')} {g('ReserveCount')}) 10000) {call('FailPlan')} (return false))
  (for w (range {g('WorkerCount')})
    (bind quality (Utilities|Array|Get(acopy) :Array Quality :"Dimension 1" w))
    (if (not (and (>= quality 0.0) (<= quality 1000000.0))) {call('FailPlan')} (return false)))
  ; Virtual mandatory jobs keep workers free without preselecting their identities.
  (Utilities|Array|Add {g('Priorities')} -1)
  (Utilities|Array|Add {g('Accepted')} true) (Utilities|Array|Add {g('Processed')} true)
  (Utilities|Array|Add {g('MinimumCount')} {g('ReserveCount')})
  (Utilities|Array|Add {g('SlotCountByBuilding')} {g('ReserveCount')})
  (for n (range {g('ReserveCount')})
    (bind row (+ {g('RealSlotCount')} n))
    (Utilities|Array|Add {g('SlotBuildings')} {g('BuildingCount')})
    (Utilities|Array|Add {g('Minimum')} true)
    (Utilities|Array|Add {g('FixedSlots')} -1)
    (Utilities|Array|Add {g('AllowedEmpty')} false)
    (Utilities|Array|Add {g('PlanAssignment')} -1)
    (Utilities|Array|Add {g('CoverageSlotMatch')} -1)
    {s('FoundWorker', '-1')}
    (for w (range {g('WorkerCount')})
      (bind eligible (and (< w Movable) (< {a('FixedOwners', 'w')} 0)))
      (Utilities|Array|Add {g('BaseScores')} (select eligible (Utilities|Array|Get(acopy) :Array Quality :"Dimension 1" w) -1e20))
      (Utilities|Array|Add {g('AllowedEdges')} eligible)
      (if (and eligible (and (< {g('FoundWorker')} 0) (< {a('CoverageWorkerMatch', 'w')} 0))) {s('FoundWorker', 'w')}))
    (if (< {g('FoundWorker')} 0) {call('FailPlan')} (return false))
    {set_a('CoverageSlotMatch', 'row', g('FoundWorker'))}
    {set_a('CoverageWorkerMatch', g('FoundWorker'), 'row')})
  {s('SlotCount', f'(+ {g("SlotCount")} {g("ReserveCount")})')}
  {s('BuildingCount', f'(+ {g("BuildingCount")} 1)')}
  (return true))
"""

code["ValidateBlock"] = f"""
(fn ValidateBlock ()
  (bind count {length('BaseScores')})
  {s('PlanValidationEnd', f'(select (< (+ {g("PlanValidationIndex")} 512) count) (+ {g("PlanValidationIndex")} 512) count)')}
  (for n (range {g('PlanValidationIndex')} {g('PlanValidationEnd')})
    (bind value {a('BaseScores', 'n')})
    (if (not (and (>= value -1e20) (<= value 1e6))) {call('FailPlan')} (break))
    {s('ScanRow', f'(/ n {g("WorkerCount")})')} {s('ScanWorker', f'(- n (* {g("ScanRow")} {g("WorkerCount")}))')}
    (bind fixedWorker {a('FixedSlots', g('ScanRow'))})
    (bind fixedOwner {a('FixedOwners', g('ScanWorker'))})
    (if (or (and (>= fixedWorker 0) (!= fixedWorker {g('ScanWorker')}))
            (and (>= fixedOwner 0) (!= fixedOwner {g('ScanRow')})))
      {set_a('BaseScores', 'n', '-1e20')})
    {set_a('AllowedEdges', 'n', '(>= value 0.0)')}
    (if (> value {g('MaxScore')}) {s('MaxScore', 'value')}))
  (if {g('PlanDone')} (return))
  {s('PlanValidationIndex', g('PlanValidationEnd'))}
  (if (< {g('PlanValidationIndex')} count) (return))
  (bind capacity (+ (select (< {g('SlotCount')} {g('WorkerCount')}) {g('SlotCount')} {g('WorkerCount')}) 1))
  {s('FillBonus', f'(+ (* (+ (* {g("MaxScore")} 5.0) 1.0) capacity) 1.0)')}
  {s('CoverageBonus', f'(+ (* (+ (+ {g("FillBonus")} (* {g("MaxScore")} 5.0)) 1.0) capacity) 1.0)')}
  {s('ColumnBonus', f'(+ (* (+ (+ (+ {g("CoverageBonus")} {g("FillBonus")} ) (* {g("MaxScore")} 5.0)) 1.0) capacity) 1.0)')}
  {s('State', '1')})
"""

code["SelectBuilding"] = f"""
(fn SelectBuilding ()
  {s('CurrentBuilding', '-1')} {s('BestPriority', '-1')}
  (for b (range {g('BuildingCount')})
    (if (and (not {a('Processed', 'b')}) (> {a('Priorities', 'b')} {g('BestPriority')}))
      {s('CurrentBuilding', 'b')} {s('BestPriority', a('Priorities', 'b'))}))
  (if (< {g('CurrentBuilding')} 0)
    {s('Tier', '4')} {call('BeginPass')} (return))
  {set_a('Processed', g('CurrentBuilding'), 'true')}
  {s('SavedSlotMatch', g('CoverageSlotMatch'))} {s('SavedWorkerMatch', g('CoverageWorkerMatch'))}
  {s('CurrentSlot', '0')} {s('State', '2')})
"""

code["BeginCoverage"] = f"""
(fn BeginCoverage ()
  {s('RootSlot', '-1')}
  (for r (range {g('CurrentSlot')} {g('SlotCount')})
    (if (and (and (== {a('SlotBuildings', 'r')} {g('CurrentBuilding')}) {a('Minimum', 'r')}) (< {a('FixedSlots', 'r')} 0))
      {s('RootSlot', 'r')} (break)))
  (if (< {g('RootSlot')} 0)
    {set_a('Accepted', g('CurrentBuilding'), 'true')} {s('State', '1')} (return))
  (for w (range {g('WorkerCount')}) {set_a('Visited', 'w', 'false')})
  (Utilities|Array|Clear {g('Queue')})
  (Utilities|Array|Add {g('Queue')} {g('RootSlot')})
  {s('QueueHead', '0')} {s('State', '3')})
"""

coverage_index = f"(+ (* {g('SearchRow')} {g('WorkerCount')}) w)"
code["CoverageStep"] = f"""
(fn CoverageStep ()
  (if (>= {g('QueueHead')} {length('Queue')})
    {s('CoverageSlotMatch', g('SavedSlotMatch'))} {s('CoverageWorkerMatch', g('SavedWorkerMatch'))}
    {s('State', '1')} (return))
  {s('SearchRow', a('Queue', g('QueueHead')))} {s('QueueHead', f'(+ {g("QueueHead")} 1)')}
  {s('FoundWorker', '-1')}
  (for w (range {g('WorkerCount')})
    (if (and (not {a('Visited', 'w')}) (>= {a('BaseScores', coverage_index)} 0.0))
      {set_a('Visited', 'w', 'true')} {set_a('ParentRow', 'w', g('SearchRow'))}
      (if (< {a('CoverageWorkerMatch', 'w')} 0)
        {s('FoundWorker', 'w')} (break)
        (else (Utilities|Array|Add {g('Queue')} {a('CoverageWorkerMatch', 'w')})))))
  (if (>= {g('FoundWorker')} 0)
    (while (>= {g('FoundWorker')} 0)
      {s('AugmentRow', a('ParentRow', g('FoundWorker')))}
      {s('PreviousWorker', a('CoverageSlotMatch', g('AugmentRow')))}
      {set_a('CoverageSlotMatch', g('AugmentRow'), g('FoundWorker'))}
      {set_a('CoverageWorkerMatch', g('FoundWorker'), g('AugmentRow'))}
      {s('FoundWorker', g('PreviousWorker'))})
    {s('CurrentSlot', f'(+ {g("RootSlot")} 1)')} {s('State', '2')}))
"""

code["BeginPass"] = f"""
(fn BeginPass ()
  {reset('PassScores', f'(* {g("SlotCount")} {g("WorkerCount")})')}
  {s('BuildIndex', '0')} {s('State', '4')})
"""

code["BuildPass"] = f"""
(fn BuildPass ()
  (bind count {length('BaseScores')})
  {s('BuildEnd', f'(select (< (+ {g("BuildIndex")} 256) count) (+ {g("BuildIndex")} 256) count)')}
  (for n (range {g('BuildIndex')} {g('BuildEnd')})
    {s('ScanRow', f'(/ n {g("WorkerCount")})')} {s('ScanWorker', f'(- n (* {g("ScanRow")} {g("WorkerCount")}))')}
    (bind building {a('SlotBuildings', g('ScanRow'))})
    {s('ScanPriority', a('Priorities', 'building'))} {s('EdgeScore', '-1e20')}
    (if (and (or {a('Accepted', 'building')} (>= {a('FixedSlots', g('ScanRow'))} 0)) {a('AllowedEdges', 'n')})
      {s('EdgeScore', '0.0')}
      (if (and (>= {g('ScanPriority')} 0) (>= {g('Tier')} 0))
       (if (not {g('StrictMode')})
        {s('EdgeScore', f'(+ {g("FillBonus")} (* {a("BaseScores", "n")} (+ {g("ScanPriority")} 1)))')}
        (elif (== {g('ScanPriority')} {g('Tier')})
          {s('EdgeScore', f'(+ {g("FillBonus")} {a("BaseScores", "n")})')})))
      (if (and (< {g('ScanPriority')} 0) (< {g('Tier')} 0)) {s('EdgeScore', a('BaseScores', 'n'))})
      (if {a('Minimum', g('ScanRow'))} {s('EdgeScore', f'(+ {g("EdgeScore")} {g("CoverageBonus")})')})
      (if {a('RequiredWorker', g('ScanWorker'))} {s('EdgeScore', f'(+ {g("EdgeScore")} {g("ColumnBonus")})')}))
    {set_a('PassScores', 'n', g('EdgeScore'))})
  {s('BuildIndex', g('BuildEnd'))}
  (if (< {g('BuildIndex')} count) (return))
  {call('Initialize', f':IncomingScores {g("PassScores")} :RowCount {g("SlotCount")} :ColumnCount {g("WorkerCount")}')}
  {call('RestrictDummies', f':Mask {g("AllowedEmpty")}')}
  {s('State', '5')})
"""

worker_index = f"(+ (* r {g('WorkerCount')}) worker)"
code["SolvePass"] = f"""
(fn SolvePass ()
  {call('Advance')}
  (if (not {g('Done')}) (return))
  (if (not {g('Succeeded')}) {call('FailPlan')} (return))
  {s('TierCount', '0')} {s('TierScore', '0.0')}
  (for w (range {g('WorkerCount')}) {set_a('ReservedWorker', 'w', 'false')})
  (for r (range {g('SlotCount')})
    (bind building {a('SlotBuildings', 'r')})
    (bind worker {a('Assignment', 'r')})
    (if (>= worker 0)
      {set_a('ReservedWorker', 'worker', 'true')}
      (bind n (+ (* r {g('WorkerCount')}) worker))
      (if (or (not {a('AllowedEdges', 'n')}) (and (not {a('Accepted', 'building')}) (< {a('FixedSlots', 'r')} 0))) {call('FailPlan')} (break))
      (if (and (>= {a('FixedSlots', 'r')} 0) (!= worker {a('FixedSlots', 'r')})) {call('FailPlan')} (break))
      (if (== {a('Priorities', 'building')} {g('Tier')})
        {s('TierCount', f'(+ {g("TierCount")} 1)')}
        {s('TierScore', f'(+ {g("TierScore")} {a("BaseScores", "n")})')})
      (else
        (if (or (not {a('AllowedEmpty', 'r')}) (and {a('Minimum', 'r')} {a('Accepted', 'building')}))
          {call('FailPlan')} (break)))))
  (if {g('PlanDone')} (return))
  (for w (range {g('WorkerCount')})
    (if (and {a('RequiredWorker', 'w')} (not {a('ReservedWorker', 'w')})) {call('FailPlan')} (break)))
  (if {g('PlanDone')} (return))
  (if (>= {g('Tier')} 0)
    {set_a('ExpectedCounts', g('Tier'), g('TierCount'))}
    {set_a('ExpectedScores', g('Tier'), g('TierScore'))})
  (if (or (< {g('Tier')} 0) (and (== {g('ReserveCount')} 0) (or (not {g('StrictMode')}) (== {g('Tier')} 0))))
    {s('BuilderTotal', '0.0')}
    (for r (range {g('RealSlotCount')} {g('SlotCount')})
      (bind worker {a('Assignment', 'r')})
      (if (< worker 0) {call('FailPlan')} (return))
      {s('BuilderTotal', f'(+ {g("BuilderTotal")} {a("BaseScores", worker_index)})')})
    {s('PlanAssignment', g('Assignment'))}
    (Utilities|Array|Resize {g('PlanAssignment')} {g('RealSlotCount')})
    {s('PlanDone', 'true')} {s('PlanSucceeded', 'true')}
    (if {g('StrictMode')}
      (for tier (range 5)
        {s('TierCount', '0')} {s('TierScore', '0.0')}
        (for r (range {g('RealSlotCount')})
          (bind building {a('SlotBuildings', 'r')})
          (bind worker {a('PlanAssignment', 'r')})
          (if (and (>= worker 0) (== {a('Priorities', 'building')} tier))
            {s('TierCount', f'(+ {g("TierCount")} 1)')}
            {s('TierScore', f'(+ {g("TierScore")} {a("BaseScores", worker_index)})')}))
        (bind difference (- {g('TierScore')} {a('ExpectedScores', 'tier')}))
        (if (or (!= {g('TierCount')} {a('ExpectedCounts', 'tier')})
                (or (> difference 0.0001) (< difference -0.0001))) {call('FailPlan')} (break))))
    (return))
  {s('BuildIndex', '0')} {s('State', '6')})
"""

row_potential = a('U', f"(+ {g('ScanRow')} 1)")
worker_potential = a('V', f"(+ {g('ScanWorker')} 1)")
dummy_potential = a('V', f"(+ {g('WorkerCount')} 1)")
code["RefinePass"] = f"""
(fn RefinePass ()
  (bind count {length('BaseScores')})
  {s('BuildEnd', f'(select (< (+ {g("BuildIndex")} 256) count) (+ {g("BuildIndex")} 256) count)')}
  (for n (range {g('BuildIndex')} {g('BuildEnd')})
    {s('ScanRow', f'(/ n {g("WorkerCount")})')} {s('ScanWorker', f'(- n (* {g("ScanRow")} {g("WorkerCount")}))')}
    {s('ReducedCost', f'(- (- (- {a("PassScores", "n")}) {row_potential}) {worker_potential})')}
    {set_a('AllowedEdges', 'n', f'(and {a("AllowedEdges", "n")} (and (>= {g("ReducedCost")} -0.00001) (<= {g("ReducedCost")} 0.00001)))')})
  {s('BuildIndex', g('BuildEnd'))}
  (if (< {g('BuildIndex')} count) (return))
  (for r (range {g('SlotCount')})
    {s('ReducedCost', f'(+ {a("U", "(+ r 1)")} {dummy_potential})')}
    {set_a('AllowedEmpty', 'r', f'(and {a("AllowedEmpty", "r")} (and (>= {g("ReducedCost")} -0.00001) (<= {g("ReducedCost")} 0.00001)))')})
  (for w (range {g('WorkerCount')})
    (if (< {a('V', '(+ w 1)')} -0.00001) {set_a('RequiredWorker', 'w', 'true')}))
  {s('Tier', f'(select {g("StrictMode")} (- {g("Tier")} 1) -1)')}
  {call('BeginPass')})
"""

code["AdvancePlan"] = f"""
(fn AdvancePlan ()
  (if {g('PlanDone')} (return))
  (switch int {g('State')}
    (:0 {call('ValidateBlock')}) (:1 {call('SelectBuilding')})
    (:2 {call('BeginCoverage')}) (:3 {call('CoverageStep')})
    (:4 {call('BuildPass')}) (:5 {call('SolvePass')}) (:6 {call('RefinePass')})
    (:Default {call('FailPlan')})))
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
