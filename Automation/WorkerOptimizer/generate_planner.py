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
    "bool": "PlanDone PlanSucceeded StrictMode FixedConfigured ReserveConfigured FlexibleConfigured",
    "int": "State SlotCount WorkerCount BuildingCount CurrentBuilding CurrentSlot RootSlot QueueHead SearchRow FoundWorker AugmentRow PreviousWorker BestPriority Tier BuildIndex BuildEnd ScanRow ScanWorker ScanPriority PlanValidationIndex PlanValidationEnd TierCount RealSlotCount ReserveCount PolicyCursor ReserveMovable ReserveRow DispatchState PolicyWork SolveColumns DummyRemaining UnionRow",
    "float": "MaxScore FillBonus CoverageBonus ColumnBonus EdgeScore ReducedCost TierScore BuilderTotal",
    "float[]": "BaseScores PassScores ExpectedScores ReserveQuality ExpandedScores",
    "int[]": "SlotBuildings Priorities PlanAssignment CoverageSlotMatch CoverageWorkerMatch SavedSlotMatch SavedWorkerMatch ParentRow Queue MinimumCount SlotCountByBuilding ExpectedCounts FixedSlots FixedOwners PendingFixed DummyBuildings OpenCount OptionalOpenCount BuildingFirstRow BuildingLastRow NextBuildingRow",
    "bool[]": "Minimum Accepted Processed Visited ReservedWorker AllowedEdges AllowedEmpty RequiredWorker FlexibleMinimum BuildingHasFixed BuildingFilled",
}
existing = set(BP.list_variables(bp))
for kind, names in types.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)

graphs = {}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
functions = ("FailPlan", "StartPlan", "RequireFixedSlots", "RequireFlexibleMinimum", "KeepUnassigned", "ValidateBlock", "SelectBuilding", "BeginCoverage", "CoverageStep", "BeginPass", "BuildPass", "SolvePass", "RefinePass", "PolicyStep", "AdvancePlan")
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
  {s('FlexibleConfigured', 'false')}
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
  {reset('FlexibleMinimum', g('BuildingCount'))} {reset('OpenCount', g('BuildingCount'))} {reset('OptionalOpenCount', g('BuildingCount'))}
  {reset('BuildingHasFixed', g('BuildingCount'))} {reset('BuildingFilled', g('BuildingCount'))}
  {reset('BuildingFirstRow', g('BuildingCount'))} {reset('BuildingLastRow', g('BuildingCount'))} {reset('NextBuildingRow', g('SlotCount'))}
  (Utilities|Array|Clear {g('DummyBuildings')}) (Utilities|Array|Clear {g('ExpandedScores')})
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

code["ValidateBlock"] = f"""
(fn ValidateBlock ()
  (bind n {g('PlanValidationIndex')})
  (if (< n {length('BaseScores')})
    (bind value {a('BaseScores', 'n')})
    (if (not (and (>= value -1e20) (<= value 1e6))) {call('FailPlan')} (return))
    {s('ScanRow', f'(/ n {g("WorkerCount")})')} {s('ScanWorker', f'(- n (* {g("ScanRow")} {g("WorkerCount")}))')}
    (bind fixedWorker {a('FixedSlots', g('ScanRow'))}) (bind fixedOwner {a('FixedOwners', g('ScanWorker'))})
    (if (or (and (>= fixedWorker 0) (!= fixedWorker {g('ScanWorker')}))
      (and (>= fixedOwner 0) (!= fixedOwner {g('ScanRow')}))) {set_a('BaseScores', 'n', '-1e20')})
    {set_a('AllowedEdges', 'n', '(>= value 0.0)')}
    (if (> value {g('MaxScore')}) {s('MaxScore', 'value')})
    {s('PlanValidationIndex', f'(+ n 1)')} (return))
  (bind capacity (+ {g('SlotCount')} 1))
  {s('FillBonus', f'(+ (* (+ (* {g("MaxScore")} 5.0) 1.0) capacity) 1.0)')}
  {s('CoverageBonus', f'(+ (* (+ (+ {g("FillBonus")} (* {g("MaxScore")} 5.0)) 1.0) capacity) 1.0)')}
  {s('ColumnBonus', f'(+ (* (+ (+ (+ {g("CoverageBonus")} {g("FillBonus")} ) (* {g("MaxScore")} 5.0)) 1.0) capacity) 1.0)')}
  {s('PolicyCursor', '0')} {s('CurrentBuilding', '-1')} {s('BestPriority', '-1')} {s('State', '19')})
"""

code["SelectBuilding"] = f"""
(fn SelectBuilding ()
  (bind b {g('PolicyCursor')})
  (if (< b {g('BuildingCount')})
    (if (and (not {a('Processed', 'b')}) (> {a('Priorities', 'b')} {g('BestPriority')}))
      {s('CurrentBuilding', 'b')} {s('BestPriority', a('Priorities', 'b'))})
    {s('PolicyCursor', '(+ b 1)')} (return))
  (if (< {g('CurrentBuilding')} 0) {s('Tier', '4')} {s('PolicyCursor', '0')} {s('State', '20')} (return))
  {set_a('Processed', g('CurrentBuilding'), 'true')}
  {s('SavedSlotMatch', g('CoverageSlotMatch'))} {s('SavedWorkerMatch', g('CoverageWorkerMatch'))}
  {s('CurrentSlot', a('BuildingFirstRow', g('CurrentBuilding')))} {s('State', '2')})
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
  {reset('PassScores', f'(* {g("SlotCount")} {g("SolveColumns")})')}
  {s('BuildIndex', '0')} {s('State', '4')})
"""

code["BuildPass"] = f"""
(fn BuildPass ()
  (bind n {g('BuildIndex')})
  (if (< n {length('ExpandedScores')})
    {s('ScanRow', f'(/ n {g("SolveColumns")})')} {s('ScanWorker', f'(- n (* {g("ScanRow")} {g("SolveColumns")}))')}
    (bind building {a('SlotBuildings', g('ScanRow'))})
    {s('ScanPriority', a('Priorities', 'building'))} {s('EdgeScore', '-1e20')}
    (if {a('AllowedEdges', 'n')}
      {s('EdgeScore', '0.0')}
      (if (< {g('ScanWorker')} {g('WorkerCount')})
        (if (and (>= {g('ScanPriority')} 0) (>= {g('Tier')} 0))
          (if (not {g('StrictMode')}) {s('EdgeScore', f'(+ {g("FillBonus")} (* {a("ExpandedScores", "n")} (+ {g("ScanPriority")} 1)))')}
            (elif (== {g('ScanPriority')} {g('Tier')}) {s('EdgeScore', f'(+ {g("FillBonus")} {a("ExpandedScores", "n")})')})))
        (if (and (< {g('ScanPriority')} 0) (< {g('Tier')} 0)) {s('EdgeScore', a('ExpandedScores', 'n'))})
        (if {a('Minimum', g('ScanRow'))} {s('EdgeScore', f'(+ {g("EdgeScore")} {g("CoverageBonus")})')}))
      (if {a('RequiredWorker', g('ScanWorker'))} {s('EdgeScore', f'(+ {g("EdgeScore")} {g("ColumnBonus")})')}))
    {set_a('PassScores', 'n', g('EdgeScore'))} {s('BuildIndex', '(+ n 1)')} (return))
  {call('Initialize', f':IncomingScores {g("PassScores")} :RowCount {g("SlotCount")} :ColumnCount {g("SolveColumns")}')}
  {call('RestrictDummies', f':Mask {g("AllowedEmpty")}')} {s('State', '5')})
"""

code["SolvePass"] = f"""
(fn SolvePass ()
  (if (not {g('Succeeded')}) {call('FailPlan')} (return))
  {s('TierCount', '0')} {s('TierScore', '0.0')} {s('PolicyCursor', '0')} {s('State', '7')})
"""

row_potential = a('U', f"(+ {g('ScanRow')} 1)")
worker_potential = a('V', f"(+ {g('ScanWorker')} 1)")
code["RefinePass"] = f"""
(fn RefinePass ()
  (bind n {g('BuildIndex')})
  (if (< n {length('ExpandedScores')})
    {s('ScanRow', f'(/ n {g("SolveColumns")})')} {s('ScanWorker', f'(- n (* {g("ScanRow")} {g("SolveColumns")}))')}
    {s('ReducedCost', f'(- (- (- {a("PassScores", "n")}) {row_potential}) {worker_potential})')}
    {set_a('AllowedEdges', 'n', f'(and {a("AllowedEdges", "n")} (and (>= {g("ReducedCost")} -0.00001) (<= {g("ReducedCost")} 0.00001)))')}
    {s('BuildIndex', '(+ n 1)')} (return))
  {s('PolicyCursor', '0')} {s('State', '30')})
"""

policy_worker_score = a('BaseScores', f'(+ (* i {g("WorkerCount")}) worker)')
coverage_index = f"(+ (* {g('ScanRow')} {g('WorkerCount')}) w)"
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
        (Utilities|Array|Add {g('AllowedEdges')} eligible)
        (if (and eligible (and (< {g('FoundWorker')} 0) (< {a('CoverageWorkerMatch', 'w')} 0))) {s('FoundWorker', 'w')})
        {s('ScanWorker', '(+ w 1)')}
        (else
          (if (< {g('FoundWorker')} 0) {call('FailPlan')}
            (else
              (bind row (+ {g('RealSlotCount')} {g('ReserveRow')}))
              {set_a('CoverageSlotMatch', 'row', g('FoundWorker'))} {set_a('CoverageWorkerMatch', g('FoundWorker'), 'row')}
              {s('ReserveRow', f'(+ {g("ReserveRow")} 1)')} {s('State', '17')})))))
    (:21
      (bind w {g('ScanWorker')})
      (if (< w {g('WorkerCount')}) {set_a('Visited', 'w', 'false')} {s('ScanWorker', '(+ w 1)')}
        (else
          (Utilities|Array|Clear {g('Queue')}) (Utilities|Array|Add {g('Queue')} {g('RootSlot')})
          {s('QueueHead', '0')} {s('State', '3')})))
    (:24
      (bind w {g('ScanWorker')})
      (if (< w {g('WorkerCount')})
        (if {a('Visited', 'w')} {s('ScanWorker', '(+ w 1)')} {reset_union} (return))
        (if (>= {g('SearchRow')} {g('SlotCount')})
          (if (< {g('UnionRow')} 0) {s('ScanWorker', '(+ w 1)')} {reset_union} (return))
          {s('ScanRow', g('UnionRow'))}
          (if (>= {a('FixedSlots', g('ScanRow'))} 0)
            {s('UnionRow', a('NextBuildingRow', g('ScanRow')))} (return))
          (else {s('ScanRow', g('SearchRow'))}))
        (if (and (not {a('Visited', 'w')}) (>= {a('BaseScores', coverage_index)} 0.0))
          {set_a('Visited', 'w', 'true')} {set_a('ParentRow', 'w', g('SearchRow'))}
          (if (< {a('CoverageWorkerMatch', 'w')} 0) {s('FoundWorker', 'w')} {s('State', '22')}
            (else (Utilities|Array|Add {g('Queue')} {a('CoverageWorkerMatch', 'w')})))
          {s('ScanWorker', '(+ w 1)')} {reset_union}
          (else
            (if (>= {g('SearchRow')} {g('SlotCount')}) {s('UnionRow', a('NextBuildingRow', g('ScanRow')))}
              (else {s('ScanWorker', '(+ w 1)')}))))
        (else {s('State', '3')})))
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
          (if (not {a('AllowedEdges', 'n')}) {call('FailPlan')})
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
          (if (or (< {g('Tier')} 0) (and (== {g('ReserveCount')} 0) (or (not {g('StrictMode')}) (== {g('Tier')} 0))))
            {s('BuilderTotal', '0.0')} {s('PolicyCursor', g('RealSlotCount'))} {s('State', '25')}
            (else {s('BuildIndex', '0')} {s('State', '6')})))))
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
        {s('PolicyCursor', '(+ i 1)')} {s('State', '23')}
        (else
          {s('SolveColumns', f'(+ {g("WorkerCount")} {length("DummyBuildings")})')}
          (if (> {g('SolveColumns')} 10000) {call('FailPlan')} (return))
          {reset('ExpandedScores', f'(* {g("SlotCount")} {g("SolveColumns")})')}
          {reset('AllowedEdges', f'(* {g("SlotCount")} {g("SolveColumns")})')}
          (Utilities|Array|Resize {g('RequiredWorker')} {g('SolveColumns')})
          (Utilities|Array|Resize {g('ReservedWorker')} {g('SolveColumns')})
          {s('BuildIndex', '0')} {s('State', '26')})))
    (:23
      (if (> {g('DummyRemaining')} 0)
        (Utilities|Array|Add {g('DummyBuildings')} {g('CurrentBuilding')}) {s('DummyRemaining', f'(- {g("DummyRemaining")} 1)')}
        (else {s('State', '20')})))
    (:26
      (bind n {g('BuildIndex')})
      (if (< n {length('ExpandedScores')})
        {s('ScanRow', f'(/ n {g("SolveColumns")})')} {s('ScanWorker', f'(- n (* {g("ScanRow")} {g("SolveColumns")}))')}
        (bind b {a('SlotBuildings', g('ScanRow'))}) {s('EdgeScore', '-1e20')}
        (if (< {g('ScanWorker')} {g('WorkerCount')})
          (if (or {a('Accepted', 'b')} (>= {a('FixedSlots', g('ScanRow'))} 0))
            {s('EdgeScore', a('BaseScores', f'(+ (* {g("ScanRow")} {g("WorkerCount")}) {g("ScanWorker")})'))})
          (else
            (if (and (== {a('DummyBuildings', f'(- {g("ScanWorker")} {g("WorkerCount")})')} b)
              (and (< {a('FixedSlots', g('ScanRow'))} 0) (not (and {a('Minimum', g('ScanRow'))} {a('Accepted', 'b')}))))
              {s('EdgeScore', '0.0')})))
        {set_a('ExpandedScores', 'n', g('EdgeScore'))} {set_a('AllowedEdges', 'n', f'(>= {g("EdgeScore")} 0.0)')}
        {s('BuildIndex', '(+ n 1)')}
        (else {s('PolicyCursor', '0')} {s('State', '28')})))
    (:28
      (if (< i {g('SlotCount')}) {set_a('AllowedEmpty', 'i', 'false')} {s('PolicyCursor', '(+ i 1)')}
        (else {s('CurrentBuilding', '-1')} {call('BeginPass')})))
    (:Default {call('FailPlan')})))
"""
code["AdvancePlan"] = f"""
(fn AdvancePlan ()
  {s('LastStepWork', '0')} (if {g('PlanDone')} (return))
  (if (<= {g('StepWorkLimit')} 0) {call('FailPlan')} (return))
  (if (and (== {g('State')} 5) (not {g('Done')})) {call('Advance')} (return))
  {s('PolicyWork', '0')}
  (for work (range {g('StepWorkLimit')})
    {s('PolicyWork', '(+ work 1)')} {call('PolicyStep')}
    (if (or {g('PlanDone')} (== {g('State')} 5)) (break)))
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
