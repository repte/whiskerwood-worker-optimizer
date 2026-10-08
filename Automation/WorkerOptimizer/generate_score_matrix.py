"""Build a runtime assignment matrix for one hypothetical school-teacher plan."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
load = lambda name: unreal.load_class(None, ROOT + "/" + name + "." + name + "_C")
worker_class = unreal.load_class(None, "/Script/ProjectArco.Prototype_Agent")
building_class = unreal.load_class(None, "/Script/ProjectArco.GridActor")
bp = unreal.load_asset(ROOT + "/BP_ScoreMatrix")
if bp is None:
    bp = BP.create(ROOT, "BP_ScoreMatrix", unreal.Object.static_class())
existing = set(BP.list_variables(bp))
for name, cls in (("Layout", load("BP_ProblemLayout")), ("Snapshot", load("BP_WorkforceSnapshot")),
                  ("Scorer", load("BP_JobScorer")), ("Settings", load("BP_PrioritySettings")),
                  ("Context", unreal.Object.static_class()), ("EdgeWorker", worker_class),
                  ("EdgeTeacher", worker_class), ("ProfileTeacher", worker_class), ("EdgeBuilding", building_class)):
    if name not in existing:
        BP.add_object_variable(bp, name, cls)
for kind, names in {
    "bool": "MatrixActive MatrixDone MatrixSucceeded AwaitingScore SchoolEdge Strict PolicyImported GroupsConfigured OrdinaryCached SetupActive StudentFound ProfileStarted ProfileReady",
    "int": "Stage BuildingIndex EdgeIndex EdgeRow EdgeColumn StudentMinimum CurrentPriority StepWorkLimit LastStepWork SetupStage SetupIndex SetupRow SetupEnd ProfileIndex PolicyIndex",
    "float": "ObservedScore",
    "name": "FailureCode",
    "int[]": "Teachers Priorities FixedSlots PolicyValues",
    "float[]": "Scores CachedScores",
    "bool[]": "Minimum TeacherGroups",
}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
BP.set_variable_instance_editable(bp, "StepWorkLimit", True)
definitions = {
    "HasObject": [("Object", unreal.Object.static_class())],
    "FailMatrix": [("Reason", "name")],
    "BeginMatrix": [("InputLayout", load("BP_ProblemLayout")), ("InputScorer", load("BP_JobScorer")),
        ("InputSettings", load("BP_PrioritySettings")), ("InputContext", unreal.Object.static_class()), ("InputTeachers", "int[]")],
    "RecordDefinition": [("Category", "name"), ("Found", "bool")],
    "UsePolicy": [("InputPriorities", "int[]"), ("InputStrict", "bool")],
    "UseTeacherGroups": [("InputGroups", "bool[]")],
    "UseOrdinaryScores": [("SourceLayout", load("BP_ProblemLayout")), ("InputScores", "float[]")],
    "ResolveProfileTeacher": [("BuildingIndex", "int")],
    "StoreEdge": [("Value", "float")],
    "PrepareEdge": [],
    "SetupStep": [],
    "RecordScore": [("Valid", "bool"), ("Value", "float")],
    "AdvanceEdge": [],
    "AdvanceMatrix": [],
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
context = graphs["PrepareEdge"]


def g(name):
    return f"(Variables|Default|Get{name})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def prop(cls, name, obj):
    return f"(Class|{cls}|Get{name} :self {obj})"


def lg(name):
    return prop("BPProblemLayout", name, g("Layout"))


def sg(name):
    return prop("BPWorkforceSnapshot", name, g("Snapshot"))


def at(array, index):
    return f'(Utilities|Array|Get(acopy) :Array {array} :"Dimension 1" {index})'


def count(array):
    return f"(Utilities|Array|Length {array})"


def present(value):
    return f"(CallFunction|HasObject :Object {value})"


def unpack(struct, value, prefix):
    node = "Utilities|Struct|Break" + struct
    return f"(bind ({' '.join(prefix + '_' + str(p.name) for p in BP.get_node_type_pins(context, node).output_pins)}) ({node} {value}))"


def fail(reason):
    return f'(CallFunction|FailMatrix :Reason "{reason}") (return false)'


def store(value):
    return f"(CallFunction|StoreEdge :Value {value}) (return true)"


clear = " ".join(f"(Utilities|Array|Clear {g(name)})" for name in ("Scores", "Priorities", "Minimum", "FixedSlots", "PolicyValues", "TeacherGroups", "CachedScores"))
code = {}
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))"""
code["FailMatrix"] = f"""(fn FailMatrix (Reason)
    {put('MatrixActive', 'false')} {put('MatrixDone', 'true')} {put('MatrixSucceeded', 'false')}
    {put('AwaitingScore', 'false')} {put('SetupActive', 'false')} {put('FailureCode', 'Reason')} {clear} (return false))"""
code["BeginMatrix"] = f"""(fn BeginMatrix (InputLayout InputScorer InputSettings InputContext InputTeachers)
    (if {g('MatrixActive')} (return false))
    {clear} {put('MatrixDone', 'false')} {put('MatrixSucceeded', 'false')} {put('AwaitingScore', 'false')}
    {put('PolicyImported', 'false')} {put('GroupsConfigured', 'false')} {put('OrdinaryCached', 'false')}
    {put('FailureCode', '"None"')} {put('Stage', '0')} {put('BuildingIndex', '0')} {put('EdgeIndex', '0')}
    (if (not {present('InputLayout')}) {fail('invalid_layout')})
    {put('Layout', 'InputLayout')}
    (if (not (and {lg('LayoutDone')} {lg('LayoutSucceeded')})) {fail('invalid_layout')})
    {put('Snapshot', lg('Snapshot'))}
    (if (not {present(g('Snapshot'))}) {fail('invalid_snapshot')})
    (if (not (and {sg('SnapshotValid')} {sg('CaptureDone')})) {fail('invalid_snapshot')})
    (if (not {present('InputScorer')}) {fail('invalid_scorer')})
    (if (not {prop('BPJobScorer', 'Ready', 'InputScorer')}) {fail('invalid_scorer')})
    (if (not {present('InputSettings')}) {fail('invalid_settings')})
    (if (not {present('InputContext')}) {fail('invalid_context')})
    (if (!= {count('InputTeachers')} {count(sg('Buildings'))}) {fail('invalid_teachers')})
    {put('Scorer', 'InputScorer')} {put('Settings', 'InputSettings')} {put('Context', 'InputContext')}
    {put('Teachers', 'InputTeachers')} {put('Minimum', lg('Minimum'))} {put('FixedSlots', lg('FixedSlots'))}
    (Utilities|Array|Resize {g('TeacherGroups')} {count(sg('Buildings'))})
    (bind strict (Class|BPPrioritySettings|ReadStrictMode :self {g('Settings')} :Context {g('Context')}))
    {put('Strict', 'strict')}
    {put('LastStepWork', '0')} {put('SetupActive', 'true')} {put('SetupStage', '0')} {put('SetupIndex', '0')}
    {put('ProfileStarted', 'false')} {put('ProfileReady', 'false')} {put('PolicyIndex', '0')}
    {put('MatrixActive', 'true')} (return true))"""

code["RecordDefinition"] = f"""(fn RecordDefinition (Category Found)
    (if (or {g('SetupActive')} (or (not {g('MatrixActive')}) (!= {g('Stage')} 0))) (return false))
    (if (not Found) {fail('definition_unavailable')})
    (bind unchanged (Class|BPWorkforceSnapshot|BuildingUnchanged :self {g('Snapshot')} :Index {g('BuildingIndex')}))
    (if (not unchanged) {fail('world_changed')})
    (if {g('PolicyImported')}
      {put('CurrentPriority', at(g('PolicyValues'), g('BuildingIndex')))}
      (else
        (bind priority (Class|BPPrioritySettings|ReadPriority :self {g('Settings')} :Context {g('Context')}
          :Category Category :Type {at(sg('PrefabKeys'), g('BuildingIndex'))}))
        {put('CurrentPriority', 'priority')}))
    (if (or (< {g('CurrentPriority')} 0) (> {g('CurrentPriority')} 4)) {fail('invalid_policy')})
    (Utilities|Array|Add {g('Priorities')} {g('CurrentPriority')})
    {put('BuildingIndex', f'(+ {g("BuildingIndex")} 1)')}
    (if (>= {g('BuildingIndex')} {count(sg('Buildings'))}) {put('Stage', '1')}) (return true))"""
code["UsePolicy"] = f"""(fn UsePolicy (InputPriorities InputStrict)
    (if (or (not {g('MatrixActive')}) (or (!= {g('EdgeIndex')} 0) {g('AwaitingScore')})) (return false))
    (if (and (== {g('Stage')} 0) (> {g('BuildingIndex')} 0)) (return false))
    (if (!= {count('InputPriorities')} {count(sg('Buildings'))}) (return false))
    {put('PolicyValues', 'InputPriorities')} {put('Strict', 'InputStrict')} {put('PolicyImported', 'true')} {put('PolicyIndex', '0')}
    (if (== {g('Stage')} 1) {put('Priorities', 'InputPriorities')}) (return true))"""
code["UseTeacherGroups"] = f"""(fn UseTeacherGroups (InputGroups)
    (if (or (not {g('MatrixActive')}) (or {g('GroupsConfigured')} (or (> {g('BuildingIndex')} 0) (or (> {g('EdgeIndex')} 0) {g('AwaitingScore')})))) (return false))
    (if (!= {count('InputGroups')} {count(sg('Buildings'))}) (return false))
    (if (not {g('SetupActive')}) (return false))
    (if (or (> {g('SetupIndex')} 0) (!= {g('SetupStage')} 0)) (return false))
    {put('TeacherGroups', 'InputGroups')} {put('GroupsConfigured', 'true')} (return true))"""

code["ResolveProfileTeacher"] = f"""(fn ResolveProfileTeacher (BuildingIndex)
    (if {g('ProfileReady')}
      (if (not {present(g('ProfileTeacher'))}) (return false))
      {put('EdgeTeacher', g('ProfileTeacher'))} (return true))
    (if (not {present(g('EdgeTeacher'))}) {put('ProfileReady', 'true')} (return false))
    (if (!= {g('EdgeTeacher')} {g('EdgeWorker')}) {put('ProfileReady', 'true')} {put('ProfileTeacher', g('EdgeTeacher'))} (return true))
    (if (not {g('ProfileStarted')})
      {put('ProfileStarted', 'true')} {put('ProfileIndex', '0')} (Variables|Default|SetProfileTeacher))
    (if (>= {g('ProfileIndex')} {count(sg('Workers'))}) {put('ProfileReady', 'true')} (return false))
    (bind candidate {at(sg('Workers'), g('ProfileIndex'))})
    (if (!= candidate {g('EdgeWorker')})
      (bind same (Class|BPJobEligibility|SameTeacherProfile :self {g('Snapshot')}
        :Left candidate :Right {g('EdgeTeacher')} :Building {g('EdgeBuilding')}))
      (if same
        {put('ProfileTeacher', 'candidate')} {put('EdgeTeacher', 'candidate')} {put('ProfileReady', 'true')} (return true)))
    {put('ProfileIndex', f'(+ {g("ProfileIndex")} 1)')} (return false))"""

code["UseOrdinaryScores"] = f"""(fn UseOrdinaryScores (SourceLayout InputScores)
    (if (or (not {g('MatrixActive')}) (or {g('OrdinaryCached')} (or (> {g('BuildingIndex')} 0) (or (> {g('EdgeIndex')} 0) {g('AwaitingScore')})))) (return false))
    (if (!= SourceLayout {g('Layout')}) (return false))
    (if (!= {count('InputScores')} (* {count(lg('RowBuildings'))} {count(lg('ColumnActors'))})) (return false))
    {put('CachedScores', 'InputScores')} {put('OrdinaryCached', 'true')} (return true))"""
code["StoreEdge"] = f"""(fn StoreEdge (Value)
    (if (or (not {g('MatrixActive')}) (!= {g('Stage')} 1)) (return false))
    (if (not (or (== Value -1.0) (and (>= Value 0.0) (<= Value 1000000.0)))) {fail('invalid_score')})
    (Utilities|Array|Add {g('Scores')} Value)
    {put('EdgeIndex', f'(+ {g("EdgeIndex")} 1)')} {put('AwaitingScore', 'false')} {put('ProfileStarted', 'false')} {put('ProfileReady', 'false')} (return true))"""
code["PrepareEdge"] = f"""(fn PrepareEdge ()
    (if (or {g('SetupActive')} (or (not {g('MatrixActive')}) (or (!= {g('Stage')} 1) {g('AwaitingScore')}))) (return false))
    (if (and {g('PolicyImported')} (< {g('PolicyIndex')} {count(g('PolicyValues'))}))
      (bind value {at(g('PolicyValues'), g('PolicyIndex'))})
      (if (or (< value 0) (> value 4)) {fail('invalid_policy')})
      {put('PolicyIndex', f'(+ {g("PolicyIndex")} 1)')} (return true))
    (if (>= {g('EdgeIndex')} (* {count(lg('RowBuildings'))} {count(lg('ColumnActors'))}))
      {put('MatrixActive', 'false')} {put('MatrixDone', 'true')} {put('MatrixSucceeded', 'true')} (return true))
    {put('EdgeRow', f'(/ {g("EdgeIndex")} {count(lg("ColumnActors"))})')}
    {put('EdgeColumn', f'(- {g("EdgeIndex")} (* {g("EdgeRow")} {count(lg("ColumnActors"))}))')}
    (bind fixed {at(g('FixedSlots'), g('EdgeRow'))})
    (if (and (>= fixed 0) (!= fixed {g('EdgeColumn')})) {store('-1.0')})
    (if (and (>= {g('EdgeColumn')} {count(sg('Workers'))}) (!= fixed {g('EdgeColumn')})) {store('-1.0')})
    (bind buildingIndex {at(lg('RowBuildings'), g('EdgeRow'))})
    (bind slotIndex {at(lg('RowSlots'), g('EdgeRow'))})
    (bind school {at(lg('SchoolBuildings'), 'buildingIndex')})
    (if (and {g('OrdinaryCached')} (not school)) {store(at(g('CachedScores'), g('EdgeIndex')))})
    {put('EdgeWorker', at(lg('ColumnActors'), g('EdgeColumn')))}
    {put('EdgeBuilding', at(sg('Buildings'), 'buildingIndex'))}
    (bind teacher {at(g('Teachers'), 'buildingIndex')})
    (if (>= teacher 0) {put('EdgeTeacher', at(lg('ColumnActors'), 'teacher'))}
      (else (Variables|Default|SetEdgeTeacher)))
    {put('SchoolEdge', 'school')}
    (if school
      (if (== slotIndex 0)
        (if {at(g('TeacherGroups'), 'buildingIndex')}
          (bind same (Class|BPJobEligibility|SameTeacherProfile :self {g('Snapshot')}
            :Left {g('EdgeWorker')} :Right {g('EdgeTeacher')} :Building {g('EdgeBuilding')}))
          (if (not same) {store('-1.0')})
          (else (if (!= teacher {g('EdgeColumn')}) {store('-1.0')})))
        (if (>= fixed 0) {store('0.0')}))
      (if (and (> slotIndex 0) {at(g('TeacherGroups'), 'buildingIndex')})
        (bind resolved (CallFunction|ResolveProfileTeacher :BuildingIndex buildingIndex))
        (if (not resolved)
          (if (not {g('ProfileReady')}) (return true))
          {store('-1.0')}))
      (else (if (>= fixed 0) {store('0.0')})))
    (if (and school (and (> slotIndex 0) (>= fixed 0)))
      {unpack('WorkerAssignment', at(sg('Workforces'), 'buildingIndex'), 'oldWf')}
      {unpack('WorkerSlot', at('oldWf_m_workerSlots', '0'), 'oldTeacher')}
      (if (== {g('EdgeTeacher')} oldTeacher_Agent)
        (if (not {present(g('EdgeTeacher'))}) {store('0.0')})
        {put('AwaitingScore', 'true')} (return true)))
    (bind eligible (Class|BPJobEligibility|CanFillSlot :self {g('Snapshot')} :Worker {g('EdgeWorker')}
      :Building {g('EdgeBuilding')} :SlotIndex slotIndex :PlannedTeacher {g('EdgeTeacher')}))
    (if (not eligible)
      (if (>= fixed 0) {fail('incompatible_fixed_student')})
      {store('-1.0')})
    (if (and school (== slotIndex 0)) {store('0.0')})
    {put('AwaitingScore', 'true')} (return true))"""
code["RecordScore"] = f"""(fn RecordScore (Valid Value)
    (if (or (not {g('MatrixActive')}) (not {g('AwaitingScore')})) (return false))
    (if (not Valid) {fail('score_unavailable')})
    (if (not (and (>= Value 0.0) (<= Value 1000000.0))) {fail('invalid_score')})
    {put('ObservedScore', 'Value')}
    (if {g('SchoolEdge')} {put('ObservedScore', f'(* Value 100.0)')})
    (bind stored (CallFunction|StoreEdge :Value {g('ObservedScore')})) (return stored))"""

code["SetupStep"] = f"""(fn SetupStep ()
    (bind b {g('SetupIndex')})
    (if (>= b {count(sg('Buildings'))})
      {put('SetupActive', 'false')}
      (if (== {count(sg('Buildings'))} 0) {put('Stage', '1')}) (return true))
    (bind first {at(lg('BuildingStarts'), 'b')})
    (bind teacher {at(g('Teachers'), 'b')})
    (if (== {g('SetupStage')} 0)
      (if (or (< teacher -1) (>= teacher {count(lg('ColumnActors'))})) {fail('invalid_teachers')})
      (if {at(lg('SchoolBuildings'), 'b')}
        (if (not (Utilities|Array|IsValidIndex {lg('FixedSlots')} first)) {fail('unsupported_school')})
        (bind fixed {at(lg('FixedSlots'), 'first')})
        (if (and (>= fixed 0) (!= teacher fixed)) {fail('invalid_teachers')})
        (if (and (>= teacher {count(sg('Workers'))}) (!= teacher fixed)) {fail('invalid_teachers')})
        (if (and {at(g('TeacherGroups'), 'b')} (>= fixed 0)) {fail('invalid_teacher_groups')})
        {unpack('WorkerAssignment', at(sg('Workforces'), 'b'), 'wf')}
        (if (< {count('wf_m_workerSlots')} 2) {fail('unsupported_school')})
        (Utilities|Array|SetArrayElem :TargetArray {g('Minimum')} :Index first :Item true)
        {put('StudentMinimum', '(+ first 1)')} {put('StudentFound', 'false')}
        {put('SetupRow', '(+ first 1)')} {put('SetupEnd', f'(+ first {count("wf_m_workerSlots")})')}
        {put('SetupStage', '1')} (return true))
      (if (!= teacher -1) {fail('invalid_teachers')})
      (if {at(g('TeacherGroups'), 'b')} {fail('invalid_teacher_groups')})
      {put('SetupIndex', '(+ b 1)')} (return true))
    (if (< {g('SetupRow')} {g('SetupEnd')})
      (if (>= {at(lg('FixedSlots'), g('SetupRow'))} 0)
        (if {at(g('TeacherGroups'), 'b')} {fail('invalid_teacher_groups')})
        (if (not {g('StudentFound')})
          {put('StudentMinimum', g('SetupRow'))} {put('StudentFound', 'true')}))
      {put('SetupRow', f'(+ {g("SetupRow")} 1)')} (return true))
    (Utilities|Array|SetArrayElem :TargetArray {g('Minimum')} :Index {g('StudentMinimum')} :Item true)
    (if (and (>= teacher 0) (>= {at(lg('FixedSlots'), g('StudentMinimum'))} 0))
      (if (and (< teacher {count(sg('Workers'))})
        (not (and (== {at(lg('FixedSlots'), 'first')} teacher) (== {at(lg('Incumbents'), 'first')} teacher))))
        (bind teacherEligible (Class|BPJobEligibility|CanFillSlot :self {g('Snapshot')}
          :Worker {at(lg('ColumnActors'), 'teacher')} :Building {at(sg('Buildings'), 'b')} :SlotIndex 0))
        (if (not teacherEligible) {fail('ineligible_required_teacher')}))
      (Utilities|Array|SetArrayElem :TargetArray {g('FixedSlots')} :Index first :Item teacher))
    (if (and {at(g('TeacherGroups'), 'b')} (>= teacher 0))
      (bind qualified (Class|BPJobEligibility|SameTeacherProfile :self {g('Snapshot')}
        :Left {at(lg('ColumnActors'), 'teacher')} :Right {at(lg('ColumnActors'), 'teacher')} :Building {at(sg('Buildings'), 'b')}))
      (if (not qualified) {fail('invalid_teacher_groups')}))
    {put('SetupStage', '0')} {put('SetupIndex', '(+ b 1)')} (return true))"""

code["AdvanceMatrix"] = f"""(fn AdvanceMatrix ()
    {put('LastStepWork', '0')} (if (not {g('MatrixActive')}) (return false))
    (if (<= {g('StepWorkLimit')} 0) {fail('invalid_step_limit')})
    {put('LastStepWork', '1')}
    (if (and {g('PolicyImported')} (< {g('PolicyIndex')} {count(g('PolicyValues'))}))
      (bind value {at(g('PolicyValues'), g('PolicyIndex'))})
      (if (or (< value 0) (> value 4)) {fail('invalid_policy')})
      {put('PolicyIndex', f'(+ {g("PolicyIndex")} 1)')} (return true))
    (if {g('SetupActive')} (bind setup (CallFunction|SetupStep)) (return setup))
    (if (== {g('Stage')} 0)
      (bind (definition found) (Class|GridActor|GetGridActorDefinition :self {at(sg('Buildings'), g('BuildingIndex'))}))
      {unpack('GridActorDefinitionMasterSyncFormat', 'definition', 'd')}
      (if found
        (bind optionsReady (Class|BPPrioritySettings|EnsureDefinitionOptions :self {g('Settings')} :Context {g('Context')}
          :Type {at(sg('PrefabKeys'), g('BuildingIndex'))} :Category d_toolbarGroup :StringKey d_stringKey))
        (if (not optionsReady) {fail('option_registration_failed')}))
      (bind accepted (CallFunction|RecordDefinition :Category d_toolbarGroup :Found found)) (return accepted))
    {put('LastStepWork', '0')}
    (for work (range {g('StepWorkLimit')})
      {put('LastStepWork', f'(+ {g("LastStepWork")} 1)')}
      (bind advanced (CallFunction|AdvanceEdge))
      (if (not {g('MatrixActive')}) (return {g('MatrixSucceeded')}))
      (if (not advanced) (return false)))
    (return true))"""

code["AdvanceEdge"] = f"""(fn AdvanceEdge ()
    (if (or {g('SetupActive')} (or (not {g('MatrixActive')}) (!= {g('Stage')} 1))) (return false))
    (if (not {g('AwaitingScore')})
      (bind prepared (CallFunction|PrepareEdge)) (return prepared))
    (if {g('SchoolEdge')}
      (bind (valid value) (Class|BPJobScorer|SchoolLearningRate :self {g('Scorer')} :Teacher {g('EdgeTeacher')}
        :Student {g('EdgeWorker')} :Building {g('EdgeBuilding')}))
      (bind recorded (CallFunction|RecordScore :Valid valid :Value value)) (return recorded))
    {unpack('WorkerAssignment', at(sg('Workforces'), at(lg('RowBuildings'), g('EdgeRow'))), 'wf')}
    (bind (ordinaryValid ordinaryValue) (Class|BPJobScorer|ScoreWorker :self {g('Scorer')} :Worker {g('EdgeWorker')}
      :Building {g('EdgeBuilding')} :Overtime wf_bOvertime))
    (bind ordinaryRecorded (CallFunction|RecordScore :Valid ordinaryValid :Value ordinaryValue)) (return ordinaryRecorded))"""

for name, source in code.items():
    try:
        blueprint_dsl.parse(source)
    except Exception:
        unreal.log_error("WO_MATRIX_PARSE " + name + "\n" + source)
        raise
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        # Rewritten bodies must not retain old parameter-linked nodes.
        result_kept = False
        for old_node in BP.find_nodes(graphs[name]):
            kind = old_node.get_class().get_name()
            if kind == "K2Node_FunctionEntry":
                continue
            if kind == "K2Node_FunctionResult" and not result_kept:
                result_kept = True
                for pin in BP.get_node_infos([old_node])[0].input_pins:
                    for connected in pin.connected_pins:
                        BP.break_pins(connected, pin.pin_id)
                continue
            BP.delete_node(old_node)
        unreal.log("WO_SCORE_MATRIX_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    unreal.get_default_object(bp.generated_class()).set_editor_property("StepWorkLimit", 64)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-ScoreMatrix.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_SCORE_MATRIX_GENERATED")
exec(Path(__file__).with_name("test_score_matrix.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_grouped_matrix.py").read_text(encoding="utf-8"))
