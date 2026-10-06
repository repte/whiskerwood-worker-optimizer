"""Generate owned, incremental terminal observations, without another solve."""

from pathlib import Path
import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
load = lambda name: unreal.load_class(None, ROOT + "/" + name + "." + name + "_C")
bp = unreal.load_asset(ROOT + "/BP_RunReport")
if bp is None:
    bp = BP.create(ROOT, "BP_RunReport", load("BP_JobEligibility"))
building_cls = unreal.load_class(None, "/Script/ProjectArco.GridActor")
worker_cls = unreal.load_class(None, "/Script/ProjectArco.Prototype_Agent")
refs = {"Snapshot": "BP_WorkforceSnapshot", "Layout": "BP_ProblemLayout", "Runner": "BP_ApplicationRunner"}
existing = set(BP.list_variables(bp))
for name, asset in refs.items():
    if name not in existing:
        BP.add_object_variable(bp, name, load(asset))
for name in ("StartedAt", "EndedAt"):
    if name not in existing:
        BP.add_struct_variable(bp, name, unreal.load_object(None, "/Script/CoreUObject.DateTime"))
for name in ("ObservedSlots", "ExpectedSlots"):
    if name not in existing:
        BP.add_struct_variable(bp, name, unreal.load_object(None, "/Script/ProjectArco.WorkerSlot"), container_type=ContainerType.ARRAY)
for kind, names in {
    "string": "RunId SaveIdentity",
    "name": "Trigger Outcome Failure PendingReason PendingType",
    "bool": "Begun FinishStarted ReportDone CountsKnown StaffingKnown WorkersKnown ReserveKnown ReserveSatisfied StrictMode PendingIssue CrewComplete AnyOccupant HaveRequired BuildingChanged AnyCandidate FreeCandidateFound ConfirmationWindowKnown",
    "int": "Reserve ConfirmedChanges ConfirmedFires ConfirmedHires ActiveSupportedBuildings PausedBuildings UnsupportedBuildings ConfirmedMinimumCrews FreeEligibleResidents ObservedCrews ObservedFree Stage BuildingIndex SlotIndex WorkerIndex CandidateSlot CandidateWorker PreservedIndex PendingId GroupIndex FlattenGroup FlattenIndex StepWorkLimit LastStepWork",
    "name[]": "GroupReasons GroupTypes PolicyCategories PolicyTypes",
    "int[]": "GroupCounts GroupStarts GroupIdCounts AffectedBuildingIds IssueGroups IssueIds PolicyCategoryValues PolicyTypeValues PageScratch",
}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
definitions = {
    "HasObject": [("Object", unreal.Object.static_class())],
    "BeginReport": [("RunId", "string"), ("Trigger", "name"), ("SaveIdentity", "string"), ("StartedAt", unreal.load_object(None, "/Script/CoreUObject.DateTime")), ("Reserve", "int")],
    "CaptureConfiguration": [("Settings", load("BP_PrioritySettings"))],
    "BeginFinish": [("Outcome", "name"), ("Failure", "name"), ("Snapshot", load("BP_WorkforceSnapshot")), ("Layout", load("BP_ProblemLayout")), ("Runner", load("BP_ApplicationRunner"))],
    "ReadReportedWorkplace": [("Worker", worker_cls)],
    "QueueIssue": [("Reason", "name"), ("Type", "name"), ("BuildingId", "int")],
    "CollectIssue": [], "AdvanceUnit": [], "AdvanceReport": [],
    "GetAffectedPage": [("Group", "int"), ("Offset", "int"), ("Limit", "int")],
    "CloseUnavailable": [("Outcome", "name"), ("Failure", "name"), ("Runner", load("BP_ApplicationRunner"))],
}
graphs = {}
old = {str(g.get_name()) for g in BP.list_graphs(bp)}
for name, params in definitions.items():
    graph = graphs[name] = BP.get_graph(bp, name) if name in old else BP.add_function_graph(bp, name)
    if name in old:
        continue
    for param, kind in params:
        if isinstance(kind, str):
            BP.add_function_param(graph, param, kind, True)
        elif kind == unreal.load_object(None, "/Script/CoreUObject.DateTime"):
            BP.add_struct_function_param(graph, param, kind, True)
        else:
            BP.add_object_function_param(graph, param, kind, True)
    if name == "ReadReportedWorkplace":
        BP.add_function_param(graph, "Known", "bool", False)
        BP.add_object_function_param(graph, "Workplace", building_cls, False)
    elif name == "GetAffectedPage":
        BP.add_function_param(graph, "Ids", "int", False, ContainerType.ARRAY)
    else:
        BP.add_function_param(graph, "Result", "bool", False)
BP.compile_blueprint(bp)
context = graphs["AdvanceUnit"]
enum_ne = next(n for n in BP.find_node_types(context, "", []) if n.rsplit("|", 1)[-1].replace(" ", "").lower() == "notequal(enum)")


def g(name):
    return f"(Variables|Default|Get{name})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def at(array, index):
    return f'(Utilities|Array|Get(acopy) :Array {array} :"Dimension 1" {index})'


def length(array):
    return f"(Utilities|Array|Length {array})"


def prop(ref, field):
    return f"(Class|{refs[ref].replace('_', '')}|Get{field} :self {g(ref)})"


def unpack(struct, value, prefix):
    pins = BP.get_node_type_pins(context, "Utilities|Struct|Break" + struct).output_pins
    return f"(bind ({' '.join(prefix + '_' + str(p.name) for p in pins)}) (Utilities|Struct|Break{struct} {value}))"


def valid(value):
    return f"(CallFunction|HasObject :Object {value})"


def add(name, value):
    return f"(Utilities|Array|Add {g(name)} {value})"


def increment(name):
    return put(name, f"(+ {g(name)} 1)")


building = at(prop("Snapshot", "Buildings"), g("BuildingIndex"))
building_id = at(prop("Snapshot", "BuildingIds"), g("BuildingIndex"))
building_type = at(prop("Snapshot", "PrefabKeys"), g("BuildingIndex"))
row = f"(+ {at(prop('Layout', 'BuildingStarts'), g('BuildingIndex'))} {g('SlotIndex')})"
candidate_row = f"(+ {at(prop('Layout', 'BuildingStarts'), g('BuildingIndex'))} {g('CandidateSlot')})"
queue_building = lambda reason: f'(CallFunction|QueueIssue :Reason "{reason}" :Type {building_type} :BuildingId {building_id})'
code = {}
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:\"Is Valid\" (return true)) (:\"Is Not Valid\" (return false))))"""
code["BeginReport"] = f"""(fn BeginReport (RunId Trigger SaveIdentity StartedAt Reserve)
    (if (or {g('Begun')} (or (< Reserve 0) (== (Utilities|String|Len RunId) 0))) (return false))
    (if (not (or (== Trigger "manual") (or (== Trigger "day_start") (or (== Trigger "minutes_5") (or (== Trigger "minutes_10") (== Trigger "minutes_15")))))) (return false))
    {put('RunId', 'RunId')} {put('Trigger', 'Trigger')} {put('SaveIdentity', 'SaveIdentity')}
    {put('StartedAt', 'StartedAt')} {put('Reserve', 'Reserve')} {put('Begun', 'true')}
    {put('ConfirmedMinimumCrews', '-1')} {put('FreeEligibleResidents', '-1')}
    {put('ActiveSupportedBuildings', '-1')} {put('PausedBuildings', '-1')} {put('UnsupportedBuildings', '-1')} (return true))"""
code["CaptureConfiguration"] = f"""(fn CaptureConfiguration (Settings)
    (if (or (not {g('Begun')}) {g('FinishStarted')}) (return false))
    (if (not {valid('Settings')}) (return false))
    (if (not (Class|BPPrioritySettings|GetPolicyFrozen :self Settings)) (return false))
    {put('StrictMode', '(Class|BPPrioritySettings|GetFrozenStrict :self Settings)')}
    {' '.join(put(target, '(Class|BPPrioritySettings|Get' + source + ' :self Settings)') for target, source in [('PolicyCategories', 'FrozenCategories'), ('PolicyTypes', 'FrozenTypes'), ('PolicyCategoryValues', 'FrozenCategoryValues'), ('PolicyTypeValues', 'FrozenTypeValues')])}
    (return true))"""
code["BeginFinish"] = f"""(fn BeginFinish (Outcome Failure Snapshot Layout Runner)
    (if (or (not {g('Begun')}) {g('FinishStarted')}) (return false))
    (if (not (or (== Outcome "completed") (or (== Outcome "cancelled") (== Outcome "failed")))) (return false))
    (if {valid('Runner')}
      (if (or (Class|BPApplicationRunner|GetWaiting :self Runner) (Class|BPApplicationRunner|GetActive :self Runner)) (return false))
      {put('ConfirmedChanges', '(Class|BPApplicationRunner|GetAppliedCount :self Runner)')}
      {put('ConfirmedFires', '(Class|BPApplicationRunner|GetConfirmedFires :self Runner)')}
      {put('ConfirmedHires', '(Class|BPApplicationRunner|GetConfirmedHires :self Runner)')})
    {put('Outcome', 'Outcome')} {put('Failure', 'Failure')} {put('EndedAt', '(Math|DateTime|UTCNow)')}
    {put('FinishStarted', 'true')} {put('ConfirmationWindowKnown', 'true')} {put('Stage', '5')}
    (if (not {valid('Snapshot')}) (return true))
    (if (not (and (Class|BPWorkforceSnapshot|GetSnapshotValid :self Snapshot) (Class|BPWorkforceSnapshot|GetCaptureDone :self Snapshot))) (return true))
    {put('Snapshot', 'Snapshot')}
    {put('ActiveSupportedBuildings', '(Utilities|Array|Length (Class|BPWorkforceSnapshot|GetBuildings :self Snapshot))')}
    {put('PausedBuildings', '(Utilities|Array|Length (Class|BPWorkforceSnapshot|GetPausedBuildingIds :self Snapshot))')}
    {put('UnsupportedBuildings', '(Utilities|Array|Length (Class|BPWorkforceSnapshot|GetCompatibilityBuildingIds :self Snapshot))')}
    (if (not {valid('Layout')}) (return true))
    (if (not (and (Class|BPProblemLayout|GetLayoutDone :self Layout) (Class|BPProblemLayout|GetLayoutSucceeded :self Layout))) (return true))
    (if (!= (Class|BPProblemLayout|GetSnapshot :self Layout) Snapshot) (return true))
    {put('Layout', 'Layout')} {put('StaffingKnown', 'true')} {put('WorkersKnown', 'true')} {put('Stage', '2')} (return true))"""
code["ReadReportedWorkplace"] = f"""(fn ReadReportedWorkplace (Worker)
    (if (not {valid('Worker')}) (return false))
    (bind workplace (Class|PrototypeAgent|GetWorkplace :self Worker)) (return true workplace))"""
code["QueueIssue"] = f"""(fn QueueIssue (Reason Type BuildingId)
    (if (or (not {g('FinishStarted')}) (or {g('ReportDone')} {g('PendingIssue')})) (return false))
    {put('PendingReason', 'Reason')} {put('PendingType', 'Type')} {put('PendingId', 'BuildingId')}
    {put('GroupIndex', '0')} {put('PendingIssue', 'true')} (return true))"""
code["CollectIssue"] = f"""(fn CollectIssue ()
    (if (not {g('PendingIssue')}) (return false))
    (bind i {g('GroupIndex')})
    (if (>= i {length(g('GroupReasons'))})
      {add('GroupReasons', g('PendingReason'))} {add('GroupTypes', g('PendingType'))} {add('GroupCounts', '0')}
      {add('GroupStarts', '0')} {add('GroupIdCounts', '0')}
      (else
        (if (not (and (== {at(g('GroupReasons'), 'i')} {g('PendingReason')}) (== {at(g('GroupTypes'), 'i')} {g('PendingType')})))
          {increment('GroupIndex')} (return true))))
    (Utilities|Array|SetArrayElem :TargetArray {g('GroupCounts')} :Index i :Item (+ {at(g('GroupCounts'), 'i')} 1))
    (if (>= {g('PendingId')} 0) {add('IssueGroups', 'i')} {add('IssueIds', g('PendingId'))})
    {put('PendingIssue', 'false')} (return true))"""
code["AdvanceUnit"] = f"""(fn AdvanceUnit ()
    (if {g('PendingIssue')} (bind grouped (CallFunction|CollectIssue)) (return grouped))
    (switch int {g('Stage')}
      (:0
        (if (>= {g('BuildingIndex')} {length(prop('Snapshot', 'Buildings'))}) {put('Stage', '4')} {put('PreservedIndex', '0')} (return true))
        (bind building {building})
        (if (not {valid('building')})
          {put('StaffingKnown', 'false')} {queue_building('world_changed')} {increment('BuildingIndex')} (return true))
        {unpack('PrefabInfo', '(Class|GridActor|GetPrefabInfo :self building)', 'prefab')}
        (bind (known workforce) (CallFunction|ReadWorkplace :Building building))
        {unpack('WorkerAssignment', 'workforce', 'live')}
        {unpack('WorkerAssignment', at(prop('Snapshot', 'Workforces'), g('BuildingIndex')), 'old')}
        (if (or (not known) (or live_bDisabled (or (not (Class|GridActor|GetIsPlayerOwned :self building))
          (or (<= (Class|GridActor|GetHealth :self building) 0) (or (!= (Class|GridActor|GetID :self building) {building_id})
          (or (!= prefab_prefabKey {building_type}) (!= (Utilities|Array|Length live_m_workerSlots) (Utilities|Array|Length old_m_workerSlots))))))))
          {put('StaffingKnown', 'false')} {queue_building('world_changed')} {increment('BuildingIndex')} (return true))
        {put('ObservedSlots', 'live_m_workerSlots')} {put('ExpectedSlots', 'old_m_workerSlots')}
        {put('SlotIndex', '0')} {put('CrewComplete', 'true')} {put('AnyOccupant', 'false')}
        {put('HaveRequired', 'false')} {put('BuildingChanged', 'false')} {put('Stage', '1')} (return true))
      (:1
        (if (>= {g('SlotIndex')} {length(g('ObservedSlots'))})
          (if {g('BuildingChanged')}
            {put('StaffingKnown', 'false')} {queue_building('world_changed')} {increment('BuildingIndex')} {put('Stage', '0')} (return true))
          (if (and {g('CrewComplete')} (or {g('HaveRequired')} {g('AnyOccupant')}))
            {increment('ObservedCrews')} {increment('BuildingIndex')} {put('Stage', '0')} (return true))
          {put('CandidateSlot', '0')} {put('CandidateWorker', '0')} {put('AnyCandidate', 'false')} {put('FreeCandidateFound', 'false')} {put('Stage', '3')}
          (if (and {g('HaveRequired')} {g('AnyOccupant')}) {queue_building('incomplete_crew')}) (return true))
        {unpack('WorkerSlot', at(g('ObservedSlots'), g('SlotIndex')), 'liveSlot')}
        {unpack('WorkerSlot', at(g('ExpectedSlots'), g('SlotIndex')), 'oldSlot')}
        (if (or (!= liveSlot_Agent oldSlot_Agent) (or (!= liveSlot_bIsRequiredToRun oldSlot_bIsRequiredToRun)
          ({enum_ne} liveSlot_educationRequirement oldSlot_educationRequirement))) {put('BuildingChanged', 'true')})
        (bind occupied {valid('liveSlot_Agent')})
        (if occupied {put('AnyOccupant', 'true')})
        (if {at(prop('Layout', 'Minimum'), row)}
          {put('HaveRequired', 'true')} (if (not occupied) {put('CrewComplete', 'false')}))
        {increment('SlotIndex')} (return true))
      (:2
        (if (>= {g('WorkerIndex')} {length(prop('Snapshot', 'Workers'))}) {put('Stage', '0')} (return true))
        (bind worker {at(prop('Snapshot', 'Workers'), g('WorkerIndex'))})
        (bind (known workplace) (CallFunction|ReadReportedWorkplace :Worker worker))
        (if (not {valid('worker')}) {put('WorkersKnown', 'false')} {increment('WorkerIndex')} (return true))
        {unpack('AgentCharacteristics', '(Class|PrototypeAgent|GetMCharacteristics :self worker)', 'ch')}
        {unpack('AgentCharacteristics', at(prop('Snapshot', 'Characteristics'), g('WorkerIndex')), 'captured')}
        (if (or (not known) (or (!= ch_ID {at(prop('Snapshot', 'WorkerIds'), g('WorkerIndex'))})
          (or ({enum_ne} ch_education captured_education) (or (!= ch_guild captured_guild)
          (not (Class|BPWorkforceSnapshot|WorkerUsable :self {g('Snapshot')} :Worker worker))))))
          {put('WorkersKnown', 'false')}
          (else
            (if (!= workplace {at(prop('Snapshot', 'WorkerWorkplaces'), g('WorkerIndex'))})
              {put('WorkersKnown', 'false')} (CallFunction|QueueIssue :Reason "world_changed" :Type "None" :BuildingId -1)
              (else (if (not {valid('workplace')}) {increment('ObservedFree')})))))
        {increment('WorkerIndex')} (return true))
      (:3
        (if (not {g('WorkersKnown')})
          {queue_building('eligibility_unknown')} {increment('BuildingIndex')} {put('Stage', '0')} (return true))
        (if (or {g('FreeCandidateFound')} (>= {g('CandidateSlot')} {length(g('ObservedSlots'))}))
          (CallFunction|QueueIssue :Reason (select {g('FreeCandidateFound')} "unfilled_crew" (select {g('AnyCandidate')} "eligible_worker_competition" "no_eligible_candidate")) :Type {building_type} :BuildingId {building_id})
          {increment('BuildingIndex')} {put('Stage', '0')} (return true))
        (if (and {g('HaveRequired')} (not {at(prop('Layout', 'Minimum'), candidate_row)}))
          {increment('CandidateSlot')} {put('CandidateWorker', '0')} (return true))
        {unpack('WorkerSlot', at(g('ObservedSlots'), g('CandidateSlot')), 'slot')}
        (if {valid('slot_Agent')} {increment('CandidateSlot')} {put('CandidateWorker', '0')} (return true))
        (bind n {length(prop('Snapshot', 'Workers'))})
        (if (>= {g('CandidateWorker')} (+ n {length(prop('Snapshot', 'ProtectedWorkers'))}))
          {increment('CandidateSlot')} {put('CandidateWorker', '0')} (return true))
        (if (< {g('CandidateWorker')} n)
          (bind candidate {at(prop('Snapshot', 'Workers'), g('CandidateWorker'))})
          (if (Class|BPWorkforceSnapshot|WorkerUsable :self {g('Snapshot')} :Worker candidate)
            (if (CallFunction|LiveCanFillSlot :Worker candidate :Building {building} :SlotIndex {g('CandidateSlot')})
              {put('AnyCandidate', 'true')}
              (bind (known workplace) (CallFunction|ReadReportedWorkplace :Worker candidate))
              (if (or (not known) (!= workplace {at(prop('Snapshot', 'WorkerWorkplaces'), g('CandidateWorker'))}))
                {put('WorkersKnown', 'false')}
                (else
                  (if (not {valid('workplace')})
                    (bind target (select (< {g('Reserve')} n) {g('Reserve')} n))
                    (if (> {g('ObservedFree')} target) {put('FreeCandidateFound', 'true')}))))))
          (else
            (bind protected {at(prop('Snapshot', 'ProtectedWorkers'), f'(- {g("CandidateWorker")} n)')})
            (if (Class|BPWorkforceSnapshot|WorkerUsable :self {g('Snapshot')} :Worker protected)
              (if (CallFunction|LiveCanFillSlot :Worker protected :Building {building} :SlotIndex {g('CandidateSlot')}) {put('AnyCandidate', 'true')}))))
        {increment('CandidateWorker')} (return true))
      (:4
        (bind paused {length(prop('Snapshot', 'PausedBuildingIds'))})
        (if (< {g('PreservedIndex')} paused)
          (CallFunction|QueueIssue :Reason "preserved_paused" :Type {at(prop('Snapshot', 'PausedPrefabKeys'), g('PreservedIndex'))} :BuildingId {at(prop('Snapshot', 'PausedBuildingIds'), g('PreservedIndex'))})
          (else
            (bind i (- {g('PreservedIndex')} paused))
            (if (>= i {length(prop('Snapshot', 'CompatibilityBuildingIds'))}) {put('Stage', '5')} (return true))
            (CallFunction|QueueIssue :Reason "preserved_unsupported" :Type {at(prop('Snapshot', 'CompatibilityPrefabKeys'), 'i')} :BuildingId {at(prop('Snapshot', 'CompatibilityBuildingIds'), 'i')})))
        {increment('PreservedIndex')} (return true))
      (:5
        {put('CountsKnown', f'(and {g("StaffingKnown")} {g("WorkersKnown")})')}
        {put('ConfirmedMinimumCrews', f'(select {g("StaffingKnown")} {g("ObservedCrews")} -1)')}
        {put('FreeEligibleResidents', f'(select {g("WorkersKnown")} {g("ObservedFree")} -1)')}
        {put('ReserveKnown', g('WorkersKnown'))}
        (if {g('WorkersKnown')}
          {put('ReserveSatisfied', f'(>= {g("ObservedFree")} (select (< {g("Reserve")} {length(prop("Snapshot", "Workers"))}) {g("Reserve")} {length(prop("Snapshot", "Workers"))}))')})
        {put('Stage', '6')}
        (if (!= {g('Outcome')} "completed")
          (CallFunction|QueueIssue :Reason {g('Failure')} :Type "None" :BuildingId -1)
          (else (if (and {g('ReserveKnown')} (not {g('ReserveSatisfied')}))
            (CallFunction|QueueIssue :Reason "reserve_shortfall" :Type "None" :BuildingId -1)))) (return true))
      (:6
        (if (>= {g('FlattenGroup')} {length(g('GroupReasons'))}) {put('Stage', '7')} (return true))
        (if (== {g('FlattenIndex')} 0)
          (Utilities|Array|SetArrayElem :TargetArray {g('GroupStarts')} :Index {g('FlattenGroup')} :Item {length(g('AffectedBuildingIds'))}))
        (if (>= {g('FlattenIndex')} {length(g('IssueGroups'))})
          {increment('FlattenGroup')} {put('FlattenIndex', '0')} (return true))
        (if (== {at(g('IssueGroups'), g('FlattenIndex'))} {g('FlattenGroup')})
          {add('AffectedBuildingIds', at(g('IssueIds'), g('FlattenIndex')))}
          (Utilities|Array|SetArrayElem :TargetArray {g('GroupIdCounts')} :Index {g('FlattenGroup')} :Item (+ {at(g('GroupIdCounts'), g('FlattenGroup'))} 1)))
        {increment('FlattenIndex')} (return true))
      (:7
        {put('ReportDone', 'true')}
        (Variables|Default|SetSnapshot) (Variables|Default|SetLayout) (Variables|Default|SetRunner)
        {' '.join('(Utilities|Array|Clear ' + g(n) + ')' for n in ('ObservedSlots', 'ExpectedSlots', 'IssueGroups', 'IssueIds'))}
        (return true))
      (:Default (return false))))"""
code["AdvanceReport"] = f"""(fn AdvanceReport ()
    {put('LastStepWork', '0')}
    (if (or (not {g('FinishStarted')}) {g('ReportDone')}) (return false))
    (if (or (<= {g('StepWorkLimit')} 0) (> {g('StepWorkLimit')} 64)) (return false))
    (for work (range {g('StepWorkLimit')})
      (if {g('ReportDone')} (break))
      {increment('LastStepWork')} (CallFunction|AdvanceUnit)) (return true))"""
code["GetAffectedPage"] = f"""(fn GetAffectedPage (Group Offset Limit)
    (Utilities|Array|Clear {g('PageScratch')})
    (if (or (not {g('ReportDone')}) (or (< Offset 0) (or (<= Limit 0) (not (Utilities|Array|IsValidIndex {g('GroupReasons')} Group))))) (return {g('PageScratch')}))
    (if (>= Offset {at(g('GroupIdCounts'), 'Group')}) (return {g('PageScratch')}))
    (for i (range (select (> Limit 50) 50 Limit))
      (bind relative (+ Offset i))
      (if (>= relative {at(g('GroupIdCounts'), 'Group')}) (break))
      {add('PageScratch', at(g('AffectedBuildingIds'), f'(+ {at(g("GroupStarts"), "Group")} relative)'))}) (return {g('PageScratch')}))"""
# World teardown cannot keep observing actors. Preserve only already confirmed
# actions and captured metadata; this path performs no world or settlement scan.
code["CloseUnavailable"] = f"""(fn CloseUnavailable (Outcome Failure Runner)
    (if (or (not {g('Begun')}) {g('ReportDone')}) (return false))
    (if (not (or (== Outcome "cancelled") (== Outcome "failed"))) (return false))
    (if {valid('Runner')}
      {put('ConfirmedChanges', '(Class|BPApplicationRunner|GetAppliedCount :self Runner)')}
      {put('ConfirmedFires', '(Class|BPApplicationRunner|GetConfirmedFires :self Runner)')}
      {put('ConfirmedHires', '(Class|BPApplicationRunner|GetConfirmedHires :self Runner)')})
    (if (not {g('FinishStarted')}) {put('EndedAt', '(Math|DateTime|UTCNow)')})
    {put('Outcome', 'Outcome')} {put('Failure', 'Failure')} {put('FinishStarted', 'true')}
    {put('CountsKnown', 'false')} {put('StaffingKnown', 'false')} {put('WorkersKnown', 'false')}
    {put('ReserveKnown', 'false')} {put('ReserveSatisfied', 'false')} {put('ConfirmationWindowKnown', 'false')}
    {put('ConfirmedMinimumCrews', '-1')} {put('FreeEligibleResidents', '-1')} {put('PendingIssue', 'false')}
    {' '.join('(Utilities|Array|Clear ' + g(n) + ')' for n in ('GroupReasons', 'GroupTypes', 'GroupCounts', 'GroupStarts', 'GroupIdCounts', 'AffectedBuildingIds', 'IssueGroups', 'IssueIds', 'ObservedSlots', 'ExpectedSlots', 'PageScratch'))}
    {add('GroupReasons', '"observation_unavailable"')} {add('GroupTypes', '"None"')}
    {add('GroupCounts', '1')} {add('GroupStarts', '0')} {add('GroupIdCounts', '0')}
    (Variables|Default|SetSnapshot) (Variables|Default|SetLayout) (Variables|Default|SetRunner)
    {put('ReportDone', 'true')} (return true))"""
for name, source in code.items():
    try:
        blueprint_dsl.parse(source)
    except Exception:
        unreal.log_error("WO_REPORT_PARSE " + name + "\n" + source)
        raise
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_REPORT_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    unreal.get_default_object(bp.generated_class()).set_editor_property("StepWorkLimit", 1)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-RunReport.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_RUN_REPORT_GENERATED")
exec(Path(__file__).with_name("test_run_report.py").read_text(encoding="utf-8"))
