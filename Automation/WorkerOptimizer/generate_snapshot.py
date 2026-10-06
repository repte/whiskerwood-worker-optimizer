"""Generate the read-only, version-guarded game-state snapshot."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
parent = unreal.load_class(None, ROOT + "/BP_JobEligibility.BP_JobEligibility_C")
assert parent
bp = unreal.load_asset(ROOT + "/BP_WorkforceSnapshot")
if bp is None:
    bp = BP.create(ROOT, "BP_WorkforceSnapshot", parent)
elif BP.get_parent(bp) != parent:
    BP.set_parent(bp, parent)
building_class = unreal.load_class(None, "/Script/ProjectArco.GridActor")
worker_class = unreal.load_class(None, "/Script/ProjectArco.Prototype_Agent")
existing = set(BP.list_variables(bp))
for name, cls in (("Buildings", building_class), ("CompatibilityBuildings", building_class), ("WorkerWorkplaces", building_class), ("Workers", worker_class), ("ProtectedWorkers", worker_class), ("PausedBuildingActors", building_class)):
    if name not in existing:
        BP.add_object_variable(bp, name, cls, container_type=ContainerType.ARRAY)
for name in ("BuildingQueue", "WorkerQueue"):
    if name not in existing:
        BP.add_object_variable(bp, name, unreal.Actor.static_class(), container_type=ContainerType.ARRAY)
for name in ("PrefabKeys", "PausedPrefabKeys", "CompatibilityPrefabKeys"):
    if name not in existing:
        BP.add_variable(bp, name, "name", container_type=ContainerType.ARRAY)
if "CompatibilityMessages" not in existing:
    BP.add_variable(bp, "CompatibilityMessages", "string", container_type=ContainerType.ARRAY)
for name, struct in (("Workforces", "WorkerAssignment"), ("Characteristics", "AgentCharacteristics"), ("States", "AgentState")):
    if name not in existing:
        BP.add_struct_variable(bp, name, unreal.load_object(None, "/Script/ProjectArco." + struct), container_type=ContainerType.ARRAY)
for name in ("BuildingIds", "WorkerIds", "PausedBuildingIds", "CompatibilityBuildingIds"):
    if name not in existing:
        BP.add_variable(bp, name, "int", container_type=ContainerType.ARRAY)
for name in ("WorkerPhase", "SnapshotValid", "CaptureDone"):
    if name not in existing:
        BP.add_variable(bp, name, "bool")
for name in ("CaptureIndex", "CaptureStage"):
    if name not in existing:
        BP.add_variable(bp, name, "int")
for name, kind in (("ValidationGuard", "name"), ("ValidationIndex", "int"), ("ValidationCaptured", "string"), ("ValidationLive", "string"), ("ValidationProbeDepth", "int")):
    if name not in existing: BP.add_variable(bp, name, kind)
for kind, names in {"bool": "ProtectionActive ProtectionHaveSlots", "int": "ProtectionComponentIndex ProtectionSlotIndex LastProtectionWork"}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind)
if "ProtectionBuilding" not in existing:
    BP.add_object_variable(bp, "ProtectionBuilding", building_class)
if "ProtectionComponents" not in existing:
    BP.add_object_variable(bp, "ProtectionComponents", unreal.ActorComponent.static_class(), container_type=ContainerType.ARRAY)
if "ProtectionSlots" not in existing:
    BP.add_struct_variable(bp, "ProtectionSlots", unreal.load_object(None, "/Script/ProjectArco.WorkerSlot"), container_type=ContainerType.ARRAY)

definitions = {
    "HasObject": ([("Object", unreal.Object.static_class())], True),
    "ResetSnapshot": ([], False),
    "RecordCompatibilityIssue": ([("Building", building_class)], True),
    "ObserveUnsupportedDefinition": ([("Building", building_class), ("MaxAgents", "int"), ("HouseTier", "int"), ("Found", "bool")], True),
    "ProtectBuilding": ([("Building", building_class)], False),
    "AdvanceProtection": ([], False),
    "AddBuilding": ([("Building", building_class)], True),
    "FinishBuildings": ([], False),
    "WorkerUsable": ([("Worker", worker_class)], True),
    "AddWorker": ([("Worker", worker_class), ("ReportedWorkplace", building_class)], True),
    "StoreWorker": ([("Worker", worker_class), ("ReportedWorkplace", building_class)], True),
    "BuildingUnchanged": ([("Index", "int")], True),
    "BuildingMatchesExpected": ([("Index", "int"), ("ChangedSlot", "int"), ("ExpectedOccupant", worker_class)], True),
    "WorkerIdentityUnchanged": ([("Index", "int")], True),
    "WorkerUnchanged": ([("Index", "int"), ("ReportedWorkplace", building_class)], True),
    "ConfirmAction": ([("BuildingIndex", "int"), ("SlotIndex", "int"), ("WorkerIndex", "int"), ("Fire", "bool"), ("ReportedWorkplace", building_class)], True),
    "ConfirmActionProbe": ([("BuildingIndex", "int"), ("SlotIndex", "int"), ("WorkerIndex", "int"), ("Fire", "bool"), ("ReportedWorkplace", building_class)], True),
    "BeginCapture": ([("WorldContext", unreal.Object.static_class())], False),
    "AdvanceCapture": ([], False),
    "CaptureBuildingActor": ([("Candidate", unreal.Actor.static_class())], True),
    "CaptureWorkerActor": ([("Candidate", unreal.Actor.static_class())], True),
    "ResetValidationFailure": ([], False),
    "RecordValidationFailure": ([("Guard", "name"), ("Index", "int"), ("Captured", "string"), ("Live", "string")], True),
}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
graphs = {}
for name, (params, result) in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
    if name not in existing_graphs:
        for param, kind in params:
            if isinstance(kind, str):
                BP.add_function_param(graphs[name], param, kind, True)
            else:
                BP.add_object_function_param(graphs[name], param, kind, True)
        if result:
            BP.add_function_param(graphs[name], "Result", "bool", False)

BP.compile_blueprint(bp)
context = graphs["AddBuilding"]
node_types = BP.find_node_types(context, "", [])
enum_not_equal = next(n for n in node_types if n.rsplit("|", 1)[-1].replace(" ", "").lower() == "notequal(enum)")
all_actors_node = next(n for n in node_types if n.rsplit("|", 1)[-1].lower() == "getallactorsofclass")
worker_cast_node = next(n for n in node_types if n.rsplit("|", 1)[-1].replace("_", "").lower() == "casttoprototypeagent")


def g(name):
    return f"(Variables|Default|Get{name})"


def set_v(name, value):
    return f"(Variables|Default|Set{name} {value})"


def item(name, index="Index"):
    return f'(Utilities|Array|Get(acopy) :Array {g(name)} :"Dimension 1" {index})'


def contains(name, value):
    return f"(Utilities|Array|ContainsItem {g(name)} {value})"


def add(name, value, unique=False):
    return f"(Utilities|Array|{'AddUnique' if unique else 'Add'} {g(name)} {value})"


def unpack(struct_name, value, prefix):
    node = "Utilities|Struct|Break" + struct_name
    pins = BP.get_node_type_pins(context, node).output_pins
    names = [prefix + "_" + str(p.name) for p in pins]
    return f"(bind ({' '.join(names)}) ({node} {value}))"


def invalid_state(prefix):
    return f"(or (or {prefix}_isDummy {prefix}_isInNautical) (or {prefix}_isBeingManhandled {prefix}_pendingRemoval))"

def diagnostic(guard, captured='"unknown"', live='"unknown"'):
    return f'(CallFunction|RecordValidationFailure :Guard "{guard}" :Index Index :Captured {captured} :Live {live}) (return false)'

def text(value, kind="Integer"):
    return f"(Utilities|String|ToString({kind}) {value})"

def append(*values):
    result = values[0]
    for value in values[1:]: result = f'(Utilities|String|Append :A {result} :B {value})'
    return result

def pair_summary(prefix):
    return append('"id="', text(prefix+'_ID'), '"/guild="', text(prefix+'_guild', 'Name'), '"/edu="', text(prefix+'_education', 'Byte'), '"/base="', text(prefix+'_base_productivity', 'Float'))

def role_summary(prefix):
    return append('"slot="', text('i'), '"/edu="', text(prefix+'_educationRequirement', 'Byte'), '"/required="', f'(select {prefix}_bIsRequiredToRun "true" "false")', '"/bonus="', f'(select {prefix}_bGivesBonus "true" "false")')


code = {}
code["ResetValidationFailure"] = f'''(fn ResetValidationFailure ()
    {set_v('ValidationGuard', '"None"')} {set_v('ValidationIndex', '-1')}
    {set_v('ValidationCaptured', '""')} {set_v('ValidationLive', '""')})'''
code["RecordValidationFailure"] = f'''(fn RecordValidationFailure (Guard Index Captured Live)
    (if (> {g('ValidationProbeDepth')} 0) (return false))
    (if (== {g('ValidationGuard')} "None")
      {set_v('ValidationGuard', 'Guard')} {set_v('ValidationIndex', 'Index')}
      {set_v('ValidationCaptured', 'Captured')} {set_v('ValidationLive', 'Live')})
    (return false))'''
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))"""
arrays = "Buildings Workforces Workers WorkerWorkplaces ProtectedWorkers Characteristics States BuildingIds WorkerIds PrefabKeys BuildingQueue WorkerQueue CompatibilityBuildings CompatibilityMessages ProtectionComponents ProtectionSlots PausedBuildingActors PausedBuildingIds PausedPrefabKeys CompatibilityBuildingIds CompatibilityPrefabKeys".split()
code["ResetSnapshot"] = f"""(fn ResetSnapshot ()
    (CallFunction|ResetValidationFailure)
    {set_v('ValidationProbeDepth', '0')}
    {' '.join(f'(Utilities|Array|Clear {g(n)})' for n in arrays)}
    {set_v('WorkerPhase', 'false')} {set_v('SnapshotValid', 'true')}
    {set_v('CaptureDone', 'true')} {set_v('CaptureIndex', '0')} {set_v('CaptureStage', '0')}
    {set_v('ProtectionActive', 'false')} {set_v('ProtectionHaveSlots', 'false')} {set_v('LastProtectionWork', '0')}
    {set_v('ProtectionComponentIndex', '0')} {set_v('ProtectionSlotIndex', '0')}
    (Variables|Default|SetProtectionBuilding))"""
code["FinishBuildings"] = f"(fn FinishBuildings () (if {g('ProtectionActive')} (return)) {set_v('WorkerPhase', 'true')})"
code["RecordCompatibilityIssue"] = f"""(fn RecordCompatibilityIssue (Building)
    (if (not (CallFunction|HasObject :Object Building)) (return false))
    (if (or (not (Class|GridActor|GetIsPlayerOwned :self Building)) (<= (Class|GridActor|GetHealth :self Building) 0)) (return false))
    (if {contains('CompatibilityBuildings', 'Building')} (return true))
    (bind (known workforce) (CallFunction|ReadWorkplace :Building Building))
    (if known (return false))
    {unpack('PrefabInfo', '(Class|GridActor|GetPrefabInfo :self Building)', 'prefab')}
    (bind message (Utilities|String|Append
      :A (Utilities|String|Append :A "WorkerOptimizer: skipped unsupported workplace " :B (Utilities|String|ToString(Name) prefab_prefabKey))
      :B (Utilities|String|Append
        :A (Utilities|String|Append :A " (building " :B (Utilities|String|ToString(Integer) (Class|GridActor|GetID :self Building)))
        :B "); existing workers preserved.")))
    {add('CompatibilityBuildings', 'Building')} {add('CompatibilityMessages', 'message')}
    {add('CompatibilityBuildingIds', '(Class|GridActor|GetID :self Building)')} {add('CompatibilityPrefabKeys', 'prefab_prefabKey')}
    (bind api (Class|ModAPI|GetModAPI :WorldContext Building))
    (if (CallFunction|HasObject :Object api)
      (Class|ModAPI|LogMessage :self api :WorldContext Building :Msg message :doPrependDate true))
    (return true))"""
code["ObserveUnsupportedDefinition"] = """(fn ObserveUnsupportedDefinition (Building MaxAgents HouseTier Found)
    (if (or (not Found) (or (<= MaxAgents 0) (> HouseTier 0))) (return false))
    (bind reported (CallFunction|RecordCompatibilityIssue :Building Building)) (return reported))"""
code["ProtectBuilding"] = f"""(fn ProtectBuilding (Building)
    (if (not (CallFunction|HasObject :Object Building)) (return))
    (if (not {g('CaptureDone')})
      {set_v('ProtectionBuilding', 'Building')}
      (bind components (Actor|GetComponentsbyClass :self Building :ComponentClass "/Script/Engine.ActorComponent"))
      {set_v('ProtectionComponents', 'components')}
      {set_v('ProtectionComponentIndex', '0')} {set_v('ProtectionSlotIndex', '0')}
      {set_v('ProtectionHaveSlots', 'false')} {set_v('ProtectionActive', 'true')} (return))
    (Utilities|IsValid Building
      (:"Is Valid"
        (bind components (Actor|GetComponentsbyClass :self Building :ComponentClass "/Script/Engine.ActorComponent"))
        (for component components
          (bind (known workforce) (CallFunction|ReadComponent :component component))
          (if known
            {unpack('WorkerAssignment', 'workforce', 'wf')}
            (if (> (Utilities|Array|Length wf_m_workerSlots) 0)
              (CallFunction|RecordCompatibilityIssue :Building Building))
            (for slot wf_m_workerSlots
              {unpack('WorkerSlot', 'slot', 'slot')}
              (Utilities|IsValid slot_Agent
                (:"Is Valid" {add('ProtectedWorkers', 'slot_Agent', True)})
                (:"Is Not Valid"))))))
      (:"Is Not Valid")))"""
code["AdvanceProtection"] = f"""(fn AdvanceProtection ()
    {set_v('LastProtectionWork', '0')}
    (if (not {g('ProtectionActive')}) (return))
    (if (>= {g('ProtectionComponentIndex')} (Utilities|Array|Length {g('ProtectionComponents')}))
      {set_v('ProtectionActive', 'false')} {set_v('ProtectionHaveSlots', 'false')}
      (Utilities|Array|Clear {g('ProtectionComponents')}) (Utilities|Array|Clear {g('ProtectionSlots')})
      (Variables|Default|SetProtectionBuilding) (return))
    (if (not {g('ProtectionHaveSlots')})
      (bind (known workforce) (CallFunction|ReadComponent :component {item('ProtectionComponents', g('ProtectionComponentIndex'))}))
      (if known
        {unpack('WorkerAssignment', 'workforce', 'wf')}
        {set_v('ProtectionSlots', 'wf_m_workerSlots')}
        (if (> (Utilities|Array|Length wf_m_workerSlots) 0) (CallFunction|RecordCompatibilityIssue :Building {g('ProtectionBuilding')}))
        {set_v('ProtectionHaveSlots', 'true')} {set_v('ProtectionSlotIndex', '0')}
        (else {set_v('ProtectionComponentIndex', f'(+ {g("ProtectionComponentIndex")} 1)')})) (return))
    (if (>= {g('ProtectionSlotIndex')} (Utilities|Array|Length {g('ProtectionSlots')}))
      (Utilities|Array|Clear {g('ProtectionSlots')}) {set_v('ProtectionHaveSlots', 'false')}
      {set_v('ProtectionComponentIndex', f'(+ {g("ProtectionComponentIndex")} 1)')} (return))
    {unpack('WorkerSlot', item('ProtectionSlots', g('ProtectionSlotIndex')), 'slot')}
    (if (CallFunction|HasObject :Object slot_Agent) {add('ProtectedWorkers', 'slot_Agent', True)})
    {set_v('LastProtectionWork', '1')} {set_v('ProtectionSlotIndex', f'(+ {g("ProtectionSlotIndex")} 1)')})"""
code["AddBuilding"] = f"""(fn AddBuilding (Building)
    (if {g('WorkerPhase')} (return false))
    (Utilities|IsValid Building
      (:"Is Valid"
        (if {contains('Buildings', 'Building')} (return false))
        (bind (known workforce) (CallFunction|ReadWorkplace :Building Building))
        {unpack('WorkerAssignment', 'workforce', 'wf')}
        (if (not known)
          (bind (definition found) (Class|GridActor|GetGridActorDefinition :self Building))
          {unpack('GridActorDefinitionMasterSyncFormat', 'definition', 'd')}
          (CallFunction|ObserveUnsupportedDefinition :Building Building :MaxAgents d_maxAgents_contextual :HouseTier d_asHouseTier :Found found))
        (if (and known (and wf_bDisabled (and (Class|GridActor|GetIsPlayerOwned :self Building)
            (and (> (Class|GridActor|GetHealth :self Building) 0) (> (Utilities|Array|Length wf_m_workerSlots) 0)))))
          (if (not {contains('PausedBuildingActors', 'Building')})
            {unpack('PrefabInfo', '(Class|GridActor|GetPrefabInfo :self Building)', 'paused')}
            {add('PausedBuildingActors', 'Building')} {add('PausedBuildingIds', '(Class|GridActor|GetID :self Building)')}
            {add('PausedPrefabKeys', 'paused_prefabKey')}))
        (if (or (not known) (or wf_bDisabled (or (not (Class|GridActor|GetIsPlayerOwned :self Building))
            (or (<= (Class|GridActor|GetHealth :self Building) 0) (== (Utilities|Array|Length wf_m_workerSlots) 0)))))
          (CallFunction|ProtectBuilding :Building Building) (return false))
        (bind id (Class|GridActor|GetID :self Building))
        (if {contains('BuildingIds', 'id')}
          {set_v('SnapshotValid', 'false')} (CallFunction|ProtectBuilding :Building Building) (return false))
        {unpack('PrefabInfo', '(Class|GridActor|GetPrefabInfo :self Building)', 'prefab')}
        {add('Buildings', 'Building')} {add('Workforces', 'workforce')} {add('BuildingIds', 'id')}
        {add('PrefabKeys', 'prefab_prefabKey')}
        (return true))
      (:"Is Not Valid" (return false))))"""
code["WorkerUsable"] = f"""(fn WorkerUsable (Worker)
    (Utilities|IsValid Worker
      (:"Is Valid"
        {unpack('AgentState', '(Class|PrototypeAgent|GetMState :self Worker)', 'st')}
        (return (not {invalid_state('st')})))
      (:"Is Not Valid" (return false))))"""
code["StoreWorker"] = f"""(fn StoreWorker (Worker ReportedWorkplace)
    (bind characteristics (Class|PrototypeAgent|GetMCharacteristics :self Worker))
    {unpack('AgentCharacteristics', 'characteristics', 'ch')}
    (if {contains('WorkerIds', 'ch_ID')}
      {set_v('SnapshotValid', 'false')} {add('ProtectedWorkers', 'Worker', True)} (return false))
    {add('Workers', 'Worker')} {add('WorkerWorkplaces', 'ReportedWorkplace')}
    {add('Characteristics', 'characteristics')} {add('States', '(Class|PrototypeAgent|GetMState :self Worker)')}
    {add('WorkerIds', 'ch_ID')} (return true))"""
code["AddWorker"] = f"""(fn AddWorker (Worker ReportedWorkplace)
    (if (not {g('WorkerPhase')}) (return false))
    (Utilities|IsValid Worker
      (:"Is Valid"
        (if {contains('Workers', 'Worker')} (return false))
        (if {contains('ProtectedWorkers', 'Worker')} (return false))
        (if (not (CallFunction|WorkerUsable :Worker Worker))
          {add('ProtectedWorkers', 'Worker', True)} (return false))
        (Utilities|IsValid ReportedWorkplace
          (:"Is Valid"
            (if (not {contains('Buildings', 'ReportedWorkplace')})
              (CallFunction|RecordCompatibilityIssue :Building ReportedWorkplace)
              {add('ProtectedWorkers', 'Worker', True)} (return false))
            (bind storedEmployed (CallFunction|StoreWorker :Worker Worker :ReportedWorkplace ReportedWorkplace))
            (return storedEmployed))
          (:"Is Not Valid"
            (bind storedFree (CallFunction|StoreWorker :Worker Worker :ReportedWorkplace ReportedWorkplace))
            (return storedFree))))
      (:"Is Not Valid" (return false))))"""
code["BuildingMatchesExpected"] = f"""(fn BuildingMatchesExpected (Index ChangedSlot ExpectedOccupant)
    (if (< ChangedSlot -1) {diagnostic('building.changed_slot_index', '"-1_or_slot"', text('ChangedSlot'))})
    (if (not (Utilities|Array|IsValidIndex {g('Buildings')} Index)) {diagnostic('building.index', text(f'(Utilities|Array|Length {g("Buildings")})'), text('Index'))})
    (bind building {item('Buildings')})
    (Utilities|IsValid building
      (:"Is Valid"
        (if (or (not (Class|GridActor|GetIsPlayerOwned :self building)) (<= (Class|GridActor|GetHealth :self building) 0)) {diagnostic('building.ownership_or_health', '"owned=true/health>0"', append('"owned="', '(select (Class|GridActor|GetIsPlayerOwned :self building) "true" "false")', '"/health="', text('(Class|GridActor|GetHealth :self building)', 'Float')))})
        (if (!= (Class|GridActor|GetID :self building) {item('BuildingIds')}) {diagnostic('building.id', text(item('BuildingIds')), text('(Class|GridActor|GetID :self building)'))})
        {unpack('PrefabInfo', '(Class|GridActor|GetPrefabInfo :self building)', 'prefab')}
        (if (!= prefab_prefabKey {item('PrefabKeys')}) {diagnostic('building.prefab', text(item('PrefabKeys'), 'Name'), text('prefab_prefabKey', 'Name'))})
        (bind (known workforce) (CallFunction|ReadWorkplace :Building building))
        (if (not known) {diagnostic('building.workplace_read', '"known"', '"unavailable"')})
        {unpack('WorkerAssignment', 'workforce', 'live')}
        {unpack('WorkerAssignment', item('Workforces'), 'old')}
        (if (or live_bDisabled (!= live_bOvertime old_bOvertime)) {diagnostic('building.disabled_or_overtime', '(select old_bOvertime "overtime" "regular")', '(select live_bDisabled "disabled" (select live_bOvertime "overtime" "regular"))')})
        (if (!= (Utilities|Array|Length live_m_workerSlots) (Utilities|Array|Length old_m_workerSlots)) {diagnostic('building.slot_count', text('(Utilities|Array|Length old_m_workerSlots)'), text('(Utilities|Array|Length live_m_workerSlots)'))})
        (if (>= ChangedSlot (Utilities|Array|Length live_m_workerSlots)) {diagnostic('building.changed_slot_index', text('(Utilities|Array|Length live_m_workerSlots)'), text('ChangedSlot'))})
        (for i (range (Utilities|Array|Length live_m_workerSlots))
          {unpack('WorkerSlot', '(Utilities|Array|Get(acopy) :Array live_m_workerSlots :"Dimension 1" i)', 'a')}
          {unpack('WorkerSlot', '(Utilities|Array|Get(acopy) :Array old_m_workerSlots :"Dimension 1" i)', 'b')}
          (if (== i ChangedSlot)
            (if (!= a_Agent ExpectedOccupant) {diagnostic('building.changed_slot_occupant', append('"slot="', text('i'), '"/agent="', text('ExpectedOccupant', 'Object')), append('"slot="', text('i'), '"/agent="', text('a_Agent', 'Object')))})
            (else (if (!= a_Agent b_Agent) {diagnostic('building.slot_occupant', append('"slot="', text('i'), '"/agent="', text('b_Agent', 'Object')), append('"slot="', text('i'), '"/agent="', text('a_Agent', 'Object')))})))
          (if (or ({enum_not_equal} a_educationRequirement b_educationRequirement)
            (or (!= a_bIsRequiredToRun b_bIsRequiredToRun) (!= a_bGivesBonus b_bGivesBonus))) {diagnostic('building.slot_role', role_summary('b'), role_summary('a'))}))
        (return true))
      (:"Is Not Valid" {diagnostic('building.invalid', '"valid"', '"invalid"')})))"""
code["BuildingUnchanged"] = """(fn BuildingUnchanged (Index)
    (bind unchanged (CallFunction|BuildingMatchesExpected :Index Index :ChangedSlot -1))
    (return unchanged))"""
code["WorkerIdentityUnchanged"] = f"""(fn WorkerIdentityUnchanged (Index)
    (if (not (Utilities|Array|IsValidIndex {g('Workers')} Index)) {diagnostic('worker.index', text(f'(Utilities|Array|Length {g("Workers")})'), text('Index'))})
    (bind worker {item('Workers')})
    (if (not (CallFunction|WorkerUsable :Worker worker)) {diagnostic('worker.usable', '"usable"', '"invalid_or_unusable"')})
    (if {contains('ProtectedWorkers', 'worker')} {diagnostic('worker.protected', '"movable"', '"protected"')})
    {unpack('AgentCharacteristics', '(Class|PrototypeAgent|GetMCharacteristics :self worker)', 'live')}
    {unpack('AgentCharacteristics', item('Characteristics'), 'old')}
    (if (or (!= live_ID old_ID) (or (!= live_guild old_guild) (or ({enum_not_equal} live_education old_education)
        (!= live_base_productivity old_base_productivity)))) {diagnostic('worker.characteristics', pair_summary('old'), pair_summary('live'))})
    (if (!= (Utilities|Set|Length live_traits) (Utilities|Set|Length old_traits)) {diagnostic('worker.trait_count', text('(Utilities|Set|Length old_traits)'), text('(Utilities|Set|Length live_traits)'))})
    (bind traits (Utilities|Set|ToArray live_traits))
    (for trait traits
      (if (not (Utilities|Set|ContainsItem old_traits trait)) {diagnostic('worker.trait_membership', '"not_present"', text('trait', 'Name'))}))
    (return true))"""
code["WorkerUnchanged"] = f"""(fn WorkerUnchanged (Index ReportedWorkplace)
    (bind identityOK (CallFunction|WorkerIdentityUnchanged :Index Index))
    (if (not identityOK) (return false))
    (bind worker {item('Workers')})
    (if (!= ReportedWorkplace {item('WorkerWorkplaces')}) {diagnostic('worker.workplace', text(item('WorkerWorkplaces'), 'Object'), text('ReportedWorkplace', 'Object'))})
    ; Soft quality is frozen by the scorer; identity/availability and placement remain live.
    (return true))"""
code["ConfirmAction"] = f"""(fn ConfirmAction (BuildingIndex SlotIndex WorkerIndex Fire ReportedWorkplace)
    (if (not (and {g('SnapshotValid')} {g('CaptureDone')})) (return false))
    (if (not (Utilities|Array|IsValidIndex {g('Buildings')} BuildingIndex)) (return false))
    (bind identityOK (CallFunction|WorkerIdentityUnchanged :Index WorkerIndex))
    (if (not identityOK) (return false))
    (bind building {item('Buildings', 'BuildingIndex')})
    (bind worker {item('Workers', 'WorkerIndex')})
    {unpack('WorkerAssignment', item('Workforces', 'BuildingIndex'), 'old')}
    (if (not (Utilities|Array|IsValidIndex old_m_workerSlots SlotIndex)) (return false))
    {unpack('WorkerSlot', '(Utilities|Array|Get(acopy) :Array old_m_workerSlots :"Dimension 1" SlotIndex)', 'oldSlot')}
    (if Fire
      (if (!= oldSlot_Agent worker) (return false))
      (if (!= {item('WorkerWorkplaces', 'WorkerIndex')} building) (return false))
      (if (CallFunction|HasObject :Object ReportedWorkplace) (return false))
      (bind fireMatches (CallFunction|BuildingMatchesExpected :Index BuildingIndex :ChangedSlot SlotIndex))
      (if (not fireMatches) (return false))
      (else
        (if (CallFunction|HasObject :Object oldSlot_Agent) (return false))
        (if (CallFunction|HasObject :Object {item('WorkerWorkplaces', 'WorkerIndex')}) (return false))
        (if (!= ReportedWorkplace building) (return false))
        (bind hireMatches (CallFunction|BuildingMatchesExpected :Index BuildingIndex :ChangedSlot SlotIndex :ExpectedOccupant worker))
        (if (not hireMatches) (return false))
        (bind eligible (CallFunction|LiveCanFillSlot :Worker worker :Building building :SlotIndex SlotIndex))
        (if (not eligible) (return false))))
    (bind (known workforce) (CallFunction|ReadWorkplace :Building building))
    (if (not known) (return false))
    (Utilities|Array|SetArrayElem :TargetArray {g('Workforces')} :Index BuildingIndex :Item workforce)
    (Utilities|Array|SetArrayElem :TargetArray {g('WorkerWorkplaces')} :Index WorkerIndex :Item ReportedWorkplace)
    (Utilities|Array|SetArrayElem :TargetArray {g('States')} :Index WorkerIndex :Item (Class|PrototypeAgent|GetMState :self worker))
    (return true))"""
# Confirmation may return false while native state propagates; it is not a terminal validator.
code["ConfirmActionProbe"] = code["ConfirmAction"].replace("(fn ConfirmAction ", "(fn ConfirmActionProbe ", 1)
code["ConfirmAction"] = f'''(fn ConfirmAction (BuildingIndex SlotIndex WorkerIndex Fire ReportedWorkplace)
    {set_v('ValidationProbeDepth', f'(+ {g("ValidationProbeDepth")} 1)')}
    (bind confirmed (CallFunction|ConfirmActionProbe :BuildingIndex BuildingIndex :SlotIndex SlotIndex
      :WorkerIndex WorkerIndex :Fire Fire :ReportedWorkplace ReportedWorkplace))
    {set_v('ValidationProbeDepth', f'(- {g("ValidationProbeDepth")} 1)')}
    (return confirmed))'''
code["BeginCapture"] = f"""(fn BeginCapture (WorldContext)
    (CallFunction|ResetSnapshot)
    (Utilities|IsValid WorldContext
      (:"Is Valid"
        (bind buildings ({all_actors_node} :WorldContextObject WorldContext :ActorClass "/Script/ProjectArco.GridActor"))
        {set_v('BuildingQueue', 'buildings')}
        (bind workers ({all_actors_node} :WorldContextObject WorldContext :ActorClass "/Script/ProjectArco.Prototype_Agent"))
        {set_v('WorkerQueue', 'workers')}
        {set_v('CaptureDone', 'false')})
      (:"Is Not Valid" {set_v('SnapshotValid', 'false')})))"""
code["CaptureBuildingActor"] = """(fn CaptureBuildingActor (Candidate)
    (bind building (Utilities|Casting|CastToGridActor :Object Candidate)
      (:then (bind added (CallFunction|AddBuilding :Building building)) (return added))
      (:CastFailed (return false))))"""
code["CaptureWorkerActor"] = f"""(fn CaptureWorkerActor (Candidate)
    (Utilities|IsValid Candidate
      (:"Is Valid"
        (bind worker ({worker_cast_node} :Object Candidate)
          (:then
            (bind workplace (Class|PrototypeAgent|GetWorkplace :self worker))
            (bind added (CallFunction|AddWorker :Worker worker :ReportedWorkplace workplace))
            (return added))
          (:CastFailed (return false))))
      (:"Is Not Valid" (return false))))"""
code["AdvanceCapture"] = f"""(fn AdvanceCapture ()
    {set_v('LastProtectionWork', '0')}
    (if {g('CaptureDone')} (return))
    (if (not {g('SnapshotValid')})
      {set_v('CaptureDone', 'true')} {set_v('ProtectionActive', 'false')} {set_v('ProtectionHaveSlots', 'false')}
      (Utilities|Array|Clear {g('ProtectionComponents')}) (Utilities|Array|Clear {g('ProtectionSlots')})
      (Utilities|Array|Clear {g('BuildingQueue')}) (Utilities|Array|Clear {g('WorkerQueue')})
      (Variables|Default|SetProtectionBuilding) (return))
    (if {g('ProtectionActive')} (CallFunction|AdvanceProtection) (return))
    (if (== {g('CaptureStage')} 0)
      (if (>= {g('CaptureIndex')} (Utilities|Array|Length {g('BuildingQueue')}))
        (CallFunction|FinishBuildings)
        {set_v('CaptureStage', '1')} {set_v('CaptureIndex', '0')} (return))
      (CallFunction|CaptureBuildingActor :Candidate {item('BuildingQueue', g('CaptureIndex'))})
      {set_v('CaptureIndex', f'(+ {g("CaptureIndex")} 1)')} (return))
    (if (>= {g('CaptureIndex')} (Utilities|Array|Length {g('WorkerQueue')}))
      {set_v('CaptureDone', 'true')}
      (Utilities|Array|Clear {g('BuildingQueue')}) (Utilities|Array|Clear {g('WorkerQueue')}) (return))
    (CallFunction|CaptureWorkerActor :Candidate {item('WorkerQueue', g('CaptureIndex'))})
    {set_v('CaptureIndex', f'(+ {g("CaptureIndex")} 1)')})"""

for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_SNAPSHOT_GENERATE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    for name, source in code.items():
        Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-Snapshot-" + name + ".dsl").write_text(source, encoding="utf-8")
unreal.log("WO_SNAPSHOT_GENERATED")
exec(Path(__file__).with_name("test_snapshot.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_action_confirmation.py").read_text(encoding="utf-8"))
