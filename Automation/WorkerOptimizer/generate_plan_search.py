"""Generate interruptible exact teacher-plan search over the production matrix/planner."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
load = lambda name: unreal.load_class(None, ROOT + "/" + name + "." + name + "_C")
bp = unreal.load_asset(ROOT + "/BP_PlanSearch")
if bp is None:
    bp = BP.create(ROOT, "BP_PlanSearch", unreal.Object.static_class())
refs = {"Layout": "BP_ProblemLayout", "Matrix": "BP_ScoreMatrix", "Planner": "BP_StaffingPlanner",
        "Snapshot": "BP_WorkforceSnapshot", "Scorer": "BP_JobScorer", "Settings": "BP_PrioritySettings"}
existing = set(BP.list_variables(bp))
for name, cls in list((name, load(cls)) for name, cls in refs.items()) + [("Context", unreal.Object.static_class())]:
    if name not in existing:
        BP.add_object_variable(bp, name, cls)
for kind, names in {
    "bool": "SearchActive SearchDone SearchSucceeded HasBest ChoosingWorker PolicyReady Strict CacheReady SearchSetupActive EquivalentDone EquivalentResult CoverageReady ComparisonReady CandidateWins BestFullCoverage",
    "int": "State BuildingIndex ChoiceWorker CurrentSchool CandidatesEvaluated CandidatesPruned CandidateTotal BestTotal RequestedReserve StepWorkLimit LastStepWork InitCursor QualityCursor ChoiceStage ChoiceRow EquivalentIndex CandidateStage CandidateIndex DuplicateIndex CandidateTeacher CompareTier CompareIndex SelectionIndex",
    "float": "CandidateWeighted BestWeighted BestBuilderQuality",
    "name": "FailureCode",
    "int[]": "SchoolBuildings ChoiceStarts ChoiceCounts ChoiceCursors Choices Teachers UsedTeachers Priorities BestAssignment BestTeachers CandidateCounts BestCounts",
    "bool[]": "Minimum CandidateCoverage BestCoverage TeacherGroups",
    "float[]": "CandidateScores BestScores CachedScores BuilderQuality",
}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
BP.set_variable_instance_editable(bp, "StepWorkLimit", True)
definitions = {
    "HasObject": [("Object", unreal.Object.static_class())],
    "FailSearch": [("Reason", "name")],
    "BeginSearch": [("Input" + name, load(refs[name])) for name in ("Layout", "Matrix", "Planner", "Scorer", "Settings")] + [("InputContext", unreal.Object.static_class())],
    "BuildChoices": [], "BeginCandidate": [], "AdvanceSelection": [], "RejectedCandidate": [], "CoverageBelowBest": [],
    "HasEquivalentChoice": [("Column", "int")],
    "ConfigureReserve": [("Requested", "int"), ("Quality", "float[]")],
    "AdvanceMatrixStep": [], "CandidateBetter": [], "ConsiderCandidate": [], "AdvanceSearch": [], "CancelSearch": [],
}
graphs = {}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
for name, params in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
    if name not in existing_graphs:
        for param, kind in params:
            if isinstance(kind, str):
                BP.add_function_param(graphs[name], param, kind.removesuffix("[]"), True, ContainerType.ARRAY if kind.endswith("[]") else None)
            else:
                BP.add_object_function_param(graphs[name], param, kind, True)
        BP.add_function_param(graphs[name], "Result", "bool", False)
BP.compile_blueprint(bp)


def g(name):
    return f"(Variables|Default|Get{name})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def prop(ref, name):
    if ref == "Planner" and name in ("LastStepWork", "StepWorkLimit"):
        return f"(Class|BPAssignmentSolver|Get{name} :self {g(ref)})"
    return f"(Class|{refs[ref].replace('_', '')}|Get{name} :self {g(ref)})"


def invoke(ref, name, args=""):
    return f"(Class|{refs[ref].replace('_', '')}|{name} :self {g(ref)} {args})"


def at(array, index):
    return f'(Utilities|Array|Get(acopy) :Array {array} :"Dimension 1" {index})'


def count(array):
    return f"(Utilities|Array|Length {array})"


def add(name, value):
    return f"(Utilities|Array|Add {g(name)} {value})"


def set_a(name, index, value):
    return f"(Utilities|Array|SetArrayElem :TargetArray {g(name)} :Index {index} :Item {value})"


def present(value):
    return f"(CallFunction|HasObject :Object {value})"


def fail(reason):
    return f'(CallFunction|FailSearch :Reason "{reason}") (return false)'


def next_candidate(index=None):
    if index is None:
        index = f'(- {count(g("SchoolBuildings"))} 1)'
    return f"{put('SelectionIndex', index)} {put('State', '4')} (return true)"


arrays = "SchoolBuildings ChoiceStarts ChoiceCounts ChoiceCursors Choices Teachers UsedTeachers Priorities BestAssignment BestTeachers CandidateCounts BestCounts Minimum CandidateCoverage BestCoverage CandidateScores BestScores TeacherGroups CachedScores".split()
clear = " ".join(f"(Utilities|Array|Clear {g(name)})" for name in arrays)
input_guards = "\n".join(
    f"(if (not {present('Input' + name)}) {fail('invalid_input')}) {put(name, 'Input' + name)}"
    for name in ("Layout", "Matrix", "Planner", "Scorer", "Settings", "Context"))
code = {}
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))"""
code["FailSearch"] = f"""(fn FailSearch (Reason)
    (if {g('SearchActive')}
      (if {present(g('Matrix'))}
        (if {prop('Matrix', 'MatrixActive')} {invoke('Matrix', 'FailMatrix', ':Reason Reason')}))
      (if {present(g('Planner'))}
        (if (not {prop('Planner', 'PlanDone')}) {invoke('Planner', 'FailPlan')})))
    {put('SearchActive', 'false')} {put('SearchDone', 'true')} {put('SearchSucceeded', 'false')}
    {put('FailureCode', 'Reason')} {put('HasBest', 'false')}
    (Utilities|Array|Clear {g('BestAssignment')}) (Utilities|Array|Clear {g('BestTeachers')}) (return false))"""
code["BeginSearch"] = f"""(fn BeginSearch (InputLayout InputMatrix InputPlanner InputScorer InputSettings InputContext)
    (if {g('SearchActive')} (return false))
    {clear} {put('SearchDone', 'false')} {put('SearchSucceeded', 'false')} {put('HasBest', 'false')} {put('BestFullCoverage', 'false')}
    {put('ChoosingWorker', 'false')} {put('PolicyReady', 'false')} {put('CacheReady', 'false')} {put('FailureCode', '"None"')}
    {put('State', '0')} {put('BuildingIndex', '0')} {put('CandidatesEvaluated', '0')} {put('CandidatesPruned', '0')}
    {put('RequestedReserve', '0')} {put('BestBuilderQuality', '0.0')} (Utilities|Array|Clear {g('BuilderQuality')})
    {input_guards}
    (if {prop('Matrix', 'MatrixActive')} {fail('matrix_busy')})
    (if (not (and {prop('Layout', 'LayoutDone')} {prop('Layout', 'LayoutSucceeded')})) {fail('invalid_layout')})
    {put('Snapshot', prop('Layout', 'Snapshot'))}
    (if (not {present(g('Snapshot'))}) {fail('invalid_snapshot')})
    {put('InitCursor', '0')} {put('QualityCursor', '0')} {put('SearchSetupActive', 'true')}
    {put('ChoiceStage', '0')} {put('LastStepWork', '0')} {put('CandidateStage', '0')} {put('CandidateIndex', '0')}
    {put('SearchActive', 'true')} (return true))"""
code["ConfigureReserve"] = f"""(fn ConfigureReserve (Requested Quality)
    (if (or (not {g('SearchActive')}) (or (!= {g('State')} 0) (or (!= {g('BuildingIndex')} 0) (> {g('InitCursor')} 0)))) (return false))
    (if (or (< Requested 0) (> Requested 100)) (return false))
    (if (!= (Utilities|Array|Length Quality) {count(prop('Layout', 'ColumnActors'))}) (return false))
    {put('RequestedReserve', 'Requested')} {put('BuilderQuality', 'Quality')}
    (return true))"""
code["BuildChoices"] = f"""(fn BuildChoices ()
    (if {g('SearchSetupActive')}
      (if (< {g('InitCursor')} {count(prop('Snapshot', 'Buildings'))})
        {add('Teachers', '-1')} {add('TeacherGroups', 'false')}
        {put('InitCursor', f'(+ {g("InitCursor")} 1)')} (return true))
      (if (< {g('QualityCursor')} {count(g('BuilderQuality'))})
        (bind value {at(g('BuilderQuality'), g('QualityCursor'))})
        (if (not (and (>= value 0.0) (<= value 1000000.0))) {fail('invalid_reserve_quality')})
        {put('QualityCursor', f'(+ {g("QualityCursor")} 1)')} (return true))
      {put('SearchSetupActive', 'false')} (return true))
    (if (>= {g('BuildingIndex')} {count(prop('Snapshot', 'Buildings'))})
      {put('SelectionIndex', f'(- {count(g("SchoolBuildings"))} 1)')}
      {put('State', '1')} {put('CandidateStage', '0')} {put('CandidateIndex', '0')} (return true))
    (if (not {at(prop('Layout', 'SchoolBuildings'), g('BuildingIndex'))})
      {put('BuildingIndex', f'(+ {g("BuildingIndex")} 1)')} (return true))
    (if (== {g('ChoiceStage')} 0)
      {put('CurrentSchool', count(g('SchoolBuildings')))} {add('SchoolBuildings', g('BuildingIndex'))}
      {add('ChoiceStarts', count(g('Choices')))} {add('ChoiceCounts', '1')} {add('ChoiceCursors', '0')}
      (bind first {at(prop('Layout', 'BuildingStarts'), g('BuildingIndex'))})
      (if (not (Utilities|Array|IsValidIndex {prop('Layout', 'FixedSlots')} first)) {fail('unsupported_school')})
      {set_a('TeacherGroups', g('BuildingIndex'), 'true')}
      {put('ChoiceRow', '0')} {put('ChoiceStage', '1')} (return true))
    (if (== {g('ChoiceStage')} 1)
      (if (< {g('ChoiceRow')} {count(prop('Layout', 'RowBuildings'))})
        (bind r {g('ChoiceRow')})
        (if (and (== {at(prop('Layout', 'RowBuildings'), 'r')} {g('BuildingIndex')}) (>= {at(prop('Layout', 'FixedSlots'), 'r')} 0))
          {set_a('TeacherGroups', g('BuildingIndex'), 'false')})
        {put('ChoiceRow', '(+ r 1)')} (return true))
      (bind fixed {at(prop('Layout', 'FixedSlots'), at(prop('Layout', 'BuildingStarts'), g('BuildingIndex')))})
      (if (>= fixed 0) {add('Choices', 'fixed')} {put('ChoiceStage', '0')} {put('BuildingIndex', f'(+ {g("BuildingIndex")} 1)')} (return true))
      {put('ChoiceWorker', '0')} {put('ChoiceStage', '2')} (return true))
    (if (== {g('ChoiceStage')} 3)
      (bind same (CallFunction|HasEquivalentChoice :Column {g('ChoiceWorker')}))
      (if (not {g('EquivalentDone')}) (return true))
      (if (not same) {add('Choices', g('ChoiceWorker'))}
        {set_a('ChoiceCounts', g('CurrentSchool'), f'(+ {at(g("ChoiceCounts"), g("CurrentSchool"))} 1)')})
      {put('ChoiceWorker', f'(+ {g("ChoiceWorker")} 1)')} {put('ChoiceStage', '2')} (return true))
    (if (>= {g('ChoiceWorker')} {count(prop('Snapshot', 'Workers'))})
      {add('Choices', '-1')} {put('ChoiceStage', '0')} {put('BuildingIndex', f'(+ {g("BuildingIndex")} 1)')} (return true))
    (bind eligible (Class|BPJobEligibility|CanFillSlot :self {g('Snapshot')}
      :Worker {at(prop('Snapshot', 'Workers'), g('ChoiceWorker'))}
      :Building {at(prop('Snapshot', 'Buildings'), g('BuildingIndex'))} :SlotIndex 0))
    (if eligible
      {put('EquivalentIndex', at(g('ChoiceStarts'), g('CurrentSchool')))}
      {put('EquivalentDone', 'false')} {put('EquivalentResult', 'false')} {put('ChoiceStage', '3')} (return true))
    {put('ChoiceWorker', f'(+ {g("ChoiceWorker")} 1)')} (return true))"""

code["HasEquivalentChoice"] = f"""(fn HasEquivalentChoice (Column)
    (if {g('EquivalentDone')} (return {g('EquivalentResult')}))
    (if (or (not {at(g('TeacherGroups'), g('BuildingIndex'))}) (>= {g('EquivalentIndex')} {count(g('Choices'))}))
      {put('EquivalentDone', 'true')} (return false))
    (bind candidate {at(g('Choices'), g('EquivalentIndex'))})
    (if (>= candidate 0)
      (bind same (Class|BPJobEligibility|SameTeacherProfile :self {g('Snapshot')}
        :Left {at(prop('Snapshot', 'Workers'), 'candidate')} :Right {at(prop('Snapshot', 'Workers'), 'Column')}
        :Building {at(prop('Snapshot', 'Buildings'), g('BuildingIndex'))}))
      (if same {put('EquivalentDone', 'true')} {put('EquivalentResult', 'true')} (return true)))
    {put('EquivalentIndex', f'(+ {g("EquivalentIndex")} 1)')} (return false))"""

# A repeated identity invalidates its whole suffix; clear one cursor per step.
# Teacherless choices are last and cannot improve an already complete coverage.
code["AdvanceSelection"] = f"""(fn AdvanceSelection ()
    (if (and (== {g('CandidateStage')} 3) (< {g('DuplicateIndex')} {count(g('SchoolBuildings'))}))
      {set_a('ChoiceCursors', g('DuplicateIndex'), '0')}
      {put('DuplicateIndex', f'(+ {g("DuplicateIndex")} 1)')} (return true))
    (if (>= {g('SelectionIndex')} 0)
      (bind index {g('SelectionIndex')})
      {set_a('ChoiceCursors', 'index', f'(+ {at(g("ChoiceCursors"), "index")} 1)')}
      (if (< {at(g('ChoiceCursors'), 'index')} {at(g('ChoiceCounts'), 'index')})
        (bind choice (+ {at(g('ChoiceStarts'), 'index')} {at(g('ChoiceCursors'), 'index')}))
        (if (not (and {g('BestFullCoverage')} (< {at(g('Choices'), 'choice')} 0)))
          {put('State', '1')} {put('CandidateStage', '0')} {put('CandidateIndex', '0')} (return true)))
      {set_a('ChoiceCursors', 'index', '0')} {put('SelectionIndex', '(- index 1)')} (return true))
    (if (not {g('HasBest')}) {fail('no_feasible_plan')})
    {put('SearchActive', 'false')} {put('SearchDone', 'true')} {put('SearchSucceeded', 'true')} (return true))"""

code["RejectedCandidate"] = f"""(fn RejectedCandidate ()
    (bind reason {prop('Matrix', 'FailureCode')})
    (if (or (== reason "invalid_teachers") (or (== reason "incompatible_fixed_student") (== reason "ineligible_required_teacher")))
      {put('CandidatesPruned', f'(+ {g("CandidatesPruned")} 1)')} {next_candidate()})
    (CallFunction|FailSearch :Reason reason) (return false))"""
code["CoverageBelowBest"] = f"""(fn CoverageBelowBest ()
    (if (or (not {g('HasBest')}) (not {g('PolicyReady')})) {put('CoverageReady', 'true')} (return false))
    (if (< {g('CompareTier')} 0) {put('CoverageReady', 'true')} (return false))
    (bind b {g('CompareIndex')})
    (if (>= b {count(g('Priorities'))})
      {put('CompareTier', f'(- {g("CompareTier")} 1)')} {put('CompareIndex', '0')} (return false))
    (if (== {at(g('Priorities'), 'b')} {g('CompareTier')})
      (bind possible (or (not {at(prop('Layout', 'SchoolBuildings'), 'b')}) (>= {at(g('Teachers'), 'b')} 0)))
      (if (!= possible {at(g('BestCoverage'), 'b')}) {put('CoverageReady', 'true')} (return (not possible))))
    {put('CompareIndex', '(+ b 1)')} (return false))"""

code["BeginCandidate"] = f"""(fn BeginCandidate ()
    (if (== {g('CandidateStage')} 0)
      (if (== {g('CandidateIndex')} 0) (Utilities|Array|Clear {g('UsedTeachers')}))
      (if (< {g('CandidateIndex')} {count(g('SchoolBuildings'))})
        (bind n {g('CandidateIndex')})
        (bind index (+ {at(g('ChoiceStarts'), 'n')} {at(g('ChoiceCursors'), 'n')}))
        {put('CandidateTeacher', at(g('Choices'), 'index'))}
        {set_a('Teachers', at(g('SchoolBuildings'), 'n'), g('CandidateTeacher'))}
        (if (and (>= {g('CandidateTeacher')} 0) (not {at(g('TeacherGroups'), at(g('SchoolBuildings'), 'n'))}))
          {put('DuplicateIndex', '0')} {put('CandidateStage', '1')} (return true))
        {put('CandidateIndex', '(+ n 1)')} (return true))
      {put('CompareTier', '4')} {put('CompareIndex', '0')} {put('CoverageReady', 'false')} {put('CandidateStage', '2')} (return true))
    (if (== {g('CandidateStage')} 1)
      (if (< {g('DuplicateIndex')} {count(g('UsedTeachers'))})
        (if (== {at(g('UsedTeachers'), g('DuplicateIndex'))} {g('CandidateTeacher')})
          {put('CandidatesPruned', f'(+ {g("CandidatesPruned")} 1)')}
          {put('DuplicateIndex', f'(+ {g("CandidateIndex")} 1)')} {put('CandidateStage', '3')}
          {next_candidate(g('CandidateIndex'))})
        {put('DuplicateIndex', f'(+ {g("DuplicateIndex")} 1)')} (return true))
      {add('UsedTeachers', g('CandidateTeacher'))} {put('CandidateIndex', f'(+ {g("CandidateIndex")} 1)')} {put('CandidateStage', '0')} (return true))
    (bind below (CallFunction|CoverageBelowBest))
    (if (not {g('CoverageReady')}) (return true))
    (if below {put('CandidatesPruned', f'(+ {g("CandidatesPruned")} 1)')} {next_candidate()})
    (bind started {invoke('Matrix', 'BeginMatrix', f':InputLayout {g("Layout")} :InputScorer {g("Scorer")} :InputSettings {g("Settings")} :InputContext {g("Context")} :InputTeachers {g("Teachers")}')})
    (if (not started) (bind rejected (CallFunction|RejectedCandidate)) (return rejected))
    (bind groupsOK {invoke('Matrix', 'UseTeacherGroups', f':InputGroups {g("TeacherGroups")}')})
    (if (not groupsOK) {fail('teacher_groups_rejected')})
    (if {g('CacheReady')}
      (bind cached {invoke('Matrix', 'UseOrdinaryScores', f':SourceLayout {g("Layout")} :InputScores {g("CachedScores")}')})
      (if (not cached) {fail('score_cache_rejected')}))
    (if {g('PolicyReady')}
      (bind policyOK {invoke('Matrix', 'UsePolicy', f':InputPriorities {g("Priorities")} :InputStrict {g("Strict")}')})
      (if (not policyOK) {fail('policy_import_failed')}))
    {put('State', '2')} (return true))"""

code["AdvanceMatrixStep"] = f"""(fn AdvanceMatrixStep ()
    (if (not {prop('Matrix', 'MatrixDone')})
      (Class|BPScoreMatrix|SetStepWorkLimit :self {g('Matrix')} :StepWorkLimit {g('StepWorkLimit')})
      {invoke('Matrix', 'AdvanceMatrix')} {put('LastStepWork', prop('Matrix', 'LastStepWork'))} (return true))
    (if (not {prop('Matrix', 'MatrixSucceeded')})
      (bind rejected (CallFunction|RejectedCandidate)) (return rejected))
    (if (not {g('CacheReady')}) {put('CachedScores', prop('Matrix', 'Scores'))} {put('CacheReady', 'true')})
    (if (not {g('PolicyReady')})
      {put('Strict', prop('Matrix', 'Strict'))} {put('Priorities', prop('Matrix', 'Priorities'))}
      {put('Minimum', prop('Matrix', 'Minimum'))} {put('PolicyReady', 'true')} {put('State', '13')} (return true))
    (if (!= {g('Strict')} {prop('Matrix', 'Strict')}) {fail('settings_changed')})
    (if (!= {count(g('Priorities'))} {count(prop('Matrix', 'Priorities'))}) {fail('settings_changed')})
    (if (!= {count(g('Minimum'))} {count(prop('Matrix', 'Minimum'))}) {fail('world_changed')})
    {put('CompareIndex', '0')} {put('State', '11')} (return true))"""

code["CandidateBetter"] = f"""(fn CandidateBetter ()
    (if (not {g('HasBest')}) {put('ComparisonReady', 'true')} (return true))
    (if (== {g('State')} 7)
      (if (< {g('CompareTier')} 0) {put('CompareTier', '4')} {put('State', '8')} (return false))
      (bind b {g('CompareIndex')})
      (if (>= b {count(g('Priorities'))})
        {put('CompareTier', f'(- {g("CompareTier")} 1)')} {put('CompareIndex', '0')} (return false))
      (if (and (== {at(g('Priorities'), 'b')} {g('CompareTier')}) (!= {at(g('CandidateCoverage'), 'b')} {at(g('BestCoverage'), 'b')}))
        {put('ComparisonReady', 'true')} (return {at(g('CandidateCoverage'), 'b')}))
      {put('CompareIndex', '(+ b 1)')} (return false))
    (if {g('Strict')}
      (if (>= {g('CompareTier')} 0)
        (bind tier {g('CompareTier')})
        (if (!= {at(g('CandidateCounts'), 'tier')} {at(g('BestCounts'), 'tier')})
          {put('ComparisonReady', 'true')} (return (> {at(g('CandidateCounts'), 'tier')} {at(g('BestCounts'), 'tier')})))
        (if (> {at(g('CandidateScores'), 'tier')} (+ {at(g('BestScores'), 'tier')} 0.0001)) {put('ComparisonReady', 'true')} (return true))
        (if (< {at(g('CandidateScores'), 'tier')} (- {at(g('BestScores'), 'tier')} 0.0001)) {put('ComparisonReady', 'true')} (return false))
        {put('CompareTier', '(- tier 1)')} (return false))
      {put('ComparisonReady', 'true')} (return (> {prop('Planner', 'BuilderTotal')} (+ {g('BestBuilderQuality')} 0.0001))))
    {put('ComparisonReady', 'true')}
    (if (!= {g('CandidateTotal')} {g('BestTotal')}) (return (> {g('CandidateTotal')} {g('BestTotal')})))
    (if (> {g('CandidateWeighted')} (+ {g('BestWeighted')} 0.0001)) (return true))
    (if (< {g('CandidateWeighted')} (- {g('BestWeighted')} 0.0001)) (return false))
    (return (> {prop('Planner', 'BuilderTotal')} (+ {g('BestBuilderQuality')} 0.0001))))"""

code["ConsiderCandidate"] = f"""(fn ConsiderCandidate ()
    (bind r {g('CandidateIndex')})
    (if (>= r {count(prop('Layout', 'RowBuildings'))})
      {put('CompareTier', '4')} {put('CompareIndex', '0')} {put('ComparisonReady', 'false')} {put('State', '7')} (return true))
    (bind worker {at(prop('Planner', 'PlanAssignment'), 'r')})
    (bind building {at(prop('Layout', 'RowBuildings'), 'r')})
    (bind tier {at(g('Priorities'), 'building')})
    (if (or (< worker -1) (>= worker {count(prop('Layout', 'ColumnActors'))})) {fail('invalid_plan')})
    (if (< worker 0)
      (if {at(g('Minimum'), 'r')} {set_a('CandidateCoverage', 'building', 'false')})
      (else
        (if {at(prop('Layout', 'FlexibleMinimumBuildings'), 'building')} {set_a('CandidateCoverage', 'building', 'true')})
        (bind index (+ (* r {count(prop('Layout', 'ColumnActors'))}) worker))
        (bind score {at(prop('Matrix', 'Scores'), 'index')})
        (if (not (and (>= score 0.0) (<= score 1000000.0))) {fail('invalid_plan')})
        {set_a('CandidateCounts', 'tier', f'(+ {at(g("CandidateCounts"), "tier")} 1)')}
        {set_a('CandidateScores', 'tier', f'(+ {at(g("CandidateScores"), "tier")} score)')}
        {put('CandidateTotal', f'(+ {g("CandidateTotal")} 1)')}
        {put('CandidateWeighted', f'(+ {g("CandidateWeighted")} (* score (+ tier 1)))')}))
    {put('CandidateIndex', '(+ r 1)')} (return true))"""

code["AdvanceSearch"] = f"""(fn AdvanceSearch ()
    {put('LastStepWork', '0')} (if (not {g('SearchActive')}) (return false))
    (if (<= {g('StepWorkLimit')} 0) {fail('invalid_step_limit')})
    {put('LastStepWork', '1')}
    (switch int {g('State')}
      (:0 (bind built (CallFunction|BuildChoices)) (return built))
      (:1 (bind begun (CallFunction|BeginCandidate)) (return begun))
      (:2 (bind scored (CallFunction|AdvanceMatrixStep)) (return scored))
      (:3
        (if (not {prop('Planner', 'PlanDone')})
          (Class|BPAssignmentSolver|SetStepWorkLimit :self {g('Planner')} :StepWorkLimit {g('StepWorkLimit')})
          {invoke('Planner', 'AdvancePlan')} {put('LastStepWork', prop('Planner', 'LastStepWork'))} (return true))
        (if (not {prop('Planner', 'PlanSucceeded')}) {fail('planner_failed')})
        (if (!= {count(prop('Planner', 'PlanAssignment'))} {count(prop('Layout', 'RowBuildings'))}) {fail('invalid_plan')})
        (Utilities|Array|Clear {g('CandidateCoverage')})
        (Utilities|Array|Clear {g('CandidateCounts')}) (Utilities|Array|Resize {g('CandidateCounts')} 5)
        (Utilities|Array|Clear {g('CandidateScores')}) (Utilities|Array|Resize {g('CandidateScores')} 5)
        {put('CandidateTotal', '0')} {put('CandidateWeighted', '0.0')} {put('CandidateIndex', '0')} {put('State', '5')} (return true))
      (:4 (bind selected (CallFunction|AdvanceSelection)) (return selected))
      (:5
        (if (< {g('CandidateIndex')} {count(g('Priorities'))})
          {add('CandidateCoverage', f'(not {at(prop("Layout", "FlexibleMinimumBuildings"), g("CandidateIndex"))})')} {put('CandidateIndex', f'(+ {g("CandidateIndex")} 1)')} (return true))
        {put('CandidateIndex', '0')} {put('State', '6')} (return true))
      (:6 (bind considered (CallFunction|ConsiderCandidate)) (return considered))
      (:7
        (bind better (CallFunction|CandidateBetter))
        (if {g('ComparisonReady')} {put('CandidateWins', 'better')} {put('State', '9')}) (return true))
      (:8
        (bind better (CallFunction|CandidateBetter))
        (if {g('ComparisonReady')} {put('CandidateWins', 'better')} {put('State', '9')}) (return true))
      (:9
        (if {g('CandidateWins')}
          {put('BestBuilderQuality', prop('Planner', 'BuilderTotal'))}
          {put('BestAssignment', prop('Planner', 'PlanAssignment'))} {put('BestTeachers', g('Teachers'))}
          {put('BestCoverage', g('CandidateCoverage'))} {put('BestCounts', g('CandidateCounts'))}
          {put('BestScores', g('CandidateScores'))} {put('BestTotal', g('CandidateTotal'))}
          {put('BestWeighted', g('CandidateWeighted'))}
          {put('BestFullCoverage', 'true')} {put('CandidateIndex', '0')} {put('State', '10')} (return true))
        {put('CandidatesEvaluated', f'(+ {g("CandidatesEvaluated")} 1)')} {next_candidate()})
      (:10
        (if (< {g('CandidateIndex')} {count(g('BestCoverage'))})
          (if (< {g('CandidateIndex')} {count(g('SchoolBuildings'))})
            (bind building {at(g('SchoolBuildings'), g('CandidateIndex'))})
            {set_a('BestTeachers', 'building', at(prop('Planner', 'PlanAssignment'), at(prop('Layout', 'BuildingStarts'), 'building')))})
          (if (not {at(g('BestCoverage'), g('CandidateIndex'))}) {put('BestFullCoverage', 'false')})
          {put('CandidateIndex', f'(+ {g("CandidateIndex")} 1)')} (return true))
        {put('HasBest', 'true')} {put('CandidatesEvaluated', f'(+ {g("CandidatesEvaluated")} 1)')} {next_candidate()})
      (:11
        (bind b {g('CompareIndex')})
        (if (< b {count(g('Priorities'))})
          (if (!= {at(g('Priorities'), 'b')} {at(prop('Matrix', 'Priorities'), 'b')}) {fail('settings_changed')})
          {put('CompareIndex', '(+ b 1)')} (return true))
        {put('CompareIndex', '0')} {put('State', '12')} (return true))
      (:12
        (bind r {g('CompareIndex')})
        (if (< r {count(g('Minimum'))})
          (if (!= {at(g('Minimum'), 'r')} {at(prop('Matrix', 'Minimum'), 'r')}) {fail('world_changed')})
          {put('CompareIndex', '(+ r 1)')} (return true))
        {put('State', '13')} (return true))
      (:13
        {invoke('Planner', 'StartPlan', f':InputScores {prop("Matrix", "Scores")} :InputBuildings {prop("Layout", "RowBuildings")} :InputMinimum {g("Minimum")} :InputPriorities {g("Priorities")} :InputWorkers {count(prop("Layout", "ColumnActors"))} :InputStrict {g("Strict")}')}
        (if (not {prop('Planner', 'PlanDone')})
          (bind flexibleOK {invoke('Planner', 'RequireFlexibleMinimum', f':InputFlexible {prop("Layout", "FlexibleMinimumBuildings")}')})
          (if (not flexibleOK) {fail('planner_constraints_failed')})
          (bind fixedOK {invoke('Planner', 'RequireFixedSlots', f':InputFixed {prop("Matrix", "FixedSlots")}')})
          (if (not fixedOK) {fail('planner_constraints_failed')})
          (if (> {g('RequestedReserve')} 0)
            (bind reserved {invoke('Planner', 'KeepUnassigned', f':Requested {g("RequestedReserve")} :Movable {count(prop("Snapshot", "Workers"))} :Quality {g("BuilderQuality")}')})
            (if (not reserved) {put('CandidatesPruned', f'(+ {g("CandidatesPruned")} 1)')} {next_candidate()})))
        {put('State', '3')} (return true))
      (:Default {fail('invalid_state')})))"""

code["CancelSearch"] = f"""(fn CancelSearch ()
    (if (not {g('SearchActive')}) (return false))
    {invoke('Matrix', 'FailMatrix', ':Reason "cancelled"')} {invoke('Planner', 'FailPlan')}
    (CallFunction|FailSearch :Reason "cancelled") (return true))"""

for name, source in code.items():
    try:
        blueprint_dsl.parse(source)
    except Exception:
        unreal.log_error("WO_SEARCH_PARSE " + name + "\n" + source)
        raise
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_PLAN_SEARCH_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    unreal.get_default_object(bp.generated_class()).set_editor_property("StepWorkLimit", 64)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-PlanSearch.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_PLAN_SEARCH_GENERATED")
exec(Path(__file__).with_name("test_plan_search.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_grouped_search.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_search_pruning.py").read_text(encoding="utf-8"))
