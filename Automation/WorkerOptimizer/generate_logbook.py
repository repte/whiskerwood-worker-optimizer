"""Generate data-only sidecars and a bounded, single-in-flight history service."""
from pathlib import Path
import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl
from editor_toolset.toolsets.data_asset import DataAssetTools

ROOT = "/Game/Mods/WorkerOptimizer"
INDEX_SLOT = "WorkerOptimizer_HistoryIndex_v1"
PREFIX = "WorkerOptimizer_History_v1_"
load = lambda n: unreal.load_class(None, f"{ROOT}/{n}.{n}_C")
# Every terminal field is primitive; variable-length fields have record-local offsets.
SCALARS = {
    "string": "RunId SaveIdentity",
    "name": "Trigger Outcome Failure",
    "int": "Reserve ConfirmedChanges ConfirmedFires ConfirmedHires ActiveSupportedBuildings PausedBuildings UnsupportedBuildings ConfirmedMinimumCrews FreeEligibleResidents StartedYear StartedMonth StartedDay StartedHour StartedMinute StartedSecond StartedMillisecond EndedYear EndedMonth EndedDay EndedHour EndedMinute EndedSecond EndedMillisecond",
    "bool": "CountsKnown StaffingKnown WorkersKnown ReserveKnown ReserveSatisfied StrictMode ConfirmationWindowKnown",
}
ARRAYS = {"name": "GroupReasons GroupTypes PolicyCategories PolicyTypes",
          "int": "GroupCounts GroupStarts GroupIdCounts AffectedBuildingIds PolicyCategoryValues PolicyTypeValues"}
scalar_fields = [(n, k) for k, ns in SCALARS.items() for n in ns.split()]
array_fields = [(n, k) for k, ns in ARRAYS.items() for n in ns.split()]
store_fields = [("SchemaVersion", "int"), ("Identity", "string"), ("StorageId", "string"), ("Revision", "int")]
store_fields += [(n, k + "[]") for n, k in scalar_fields]
for n, k in array_fields:
    store_fields += [(n, k + "[]"), (n + "Offsets", "int[]"), (n + "Lengths", "int[]")]
index_fields = [("SchemaVersion", "int"), ("Revision", "int"), ("Identities", "string[]"), ("StorageIds", "string[]")]

def variables(bp, fields):
    old = set(BP.list_variables(bp))
    for n, k in fields:
        if n not in old:
            BP.add_variable(bp, n, k.removesuffix("[]"), container_type=ContainerType.ARRAY if k.endswith("[]") else None)

for asset, fields in (("BP_LogbookStore", store_fields), ("BP_LogbookIndex", index_fields)):
    obj = unreal.load_asset(ROOT + "/" + asset) or BP.create(ROOT, asset, unreal.SaveGame.static_class())
    if asset == "BP_LogbookStore":
        for obsolete in ("StartedAt", "EndedAt"):
            if obsolete in BP.list_variables(obj): BP.remove_variable(obj, obsolete)
    variables(obj, fields)
    if "IOCoordinator" in BP.list_variables(obj): BP.remove_variable(obj, "IOCoordinator")
    BP.add_object_variable(obj, "IOCoordinator", unreal.Object.static_class())
    BP.compile_blueprint(obj, warnings_as_errors=True)
    unreal.get_default_object(obj.generated_class()).set_editor_property("SchemaVersion", 1)
    assert unreal.EditorAssetLibrary.save_loaded_asset(obj)

bp = unreal.load_asset(ROOT + "/BP_Logbook") or BP.create(ROOT, "BP_Logbook", unreal.Object.static_class())
gate_bp = unreal.load_asset(ROOT + "/BP_LogbookIO") or BP.create(ROOT, "BP_LogbookIO", unreal.PrimaryDataAsset.static_class())
request_bp = unreal.load_asset(ROOT + "/BP_LogbookIORequest") or BP.create(ROOT, "BP_LogbookIORequest", unreal.Object.static_class())
variables(gate_bp, [("Busy", "bool")])
if "CurrentRequest" not in BP.list_variables(gate_bp): BP.add_object_variable(gate_bp, "CurrentRequest", unreal.Object.static_class())
variables(request_bp, [("Kind", "name"), ("Slot", "string"), ("Identity", "string"), ("Generation", "int"), ("Revision", "int"), ("Workspace", "int")])
for name, klass in (("Owner", unreal.Object.static_class()), ("Context", unreal.Object.static_class()), ("Payload", unreal.SaveGame.static_class()), ("Coordinator", unreal.Object.static_class())):
    if name not in BP.list_variables(request_bp): BP.add_object_variable(request_bp, name, klass)
BP.compile_blueprint(gate_bp)
BP.compile_blueprint(request_bp)
for name in ("Acquire", "Release"):
    existing = {str(x.get_name()) for x in BP.list_graphs(gate_bp)}
    graph = BP.get_graph(gate_bp, name) if name in existing else BP.add_function_graph(gate_bp, name)
    if name not in existing:
        BP.add_object_function_param(graph, "Request", unreal.Object.static_class(), True)
        BP.add_function_param(graph, "Result", "bool", False)
    BP.write_graph_dsl(graph, f'''(fn {name} (Request)
      (if {"(Variables|Default|GetBusy)" if name == "Acquire" else "(!= (Variables|Default|GetCurrentRequest) Request)"} (return false))
      (Variables|Default|SetCurrentRequest {"Request" if name == "Acquire" else ""})
      (Variables|Default|SetBusy {"true" if name == "Acquire" else "false"}) (return true))''')
BP.compile_blueprint(gate_bp, warnings_as_errors=True)
coordinator = unreal.load_asset(ROOT + "/DA_LogbookIO") or DataAssetTools.create(ROOT, "DA_LogbookIO", gate_bp.generated_class())
unreal.EditorAssetLibrary.save_loaded_asset(gate_bp)
complete_graphs = {str(x.get_name()) for x in BP.list_graphs(request_bp)}
complete_graph = BP.get_graph(request_bp, "Complete") if "Complete" in complete_graphs else BP.add_function_graph(request_bp, "Complete")
if "Complete" not in complete_graphs:
    BP.add_object_function_param(complete_graph, "SaveGame", unreal.SaveGame.static_class(), True)
    BP.add_function_param(complete_graph, "Success", "bool", True)
    BP.add_function_param(complete_graph, "Result", "bool", False)
BP.compile_blueprint(request_bp)
variables(bp, [("ActiveIdentity", "string"), ("RequestIdentity", "string"), ("RequestSlot", "string"),
    ("StorageFailure", "name"), ("RequestKind", "name"),
    *[(n, "int") for n in "Generation HistoryRevision RequestGeneration RequestRevision RequestWorkspace ActiveWorkspace WorkWorkspace Stage FieldCursor ElementCursor EvictRemaining StorageCursor DirtyCount SnapshotCursor PendingCursor PendingMatchCount PendingOldest".split()],
    *[(n, "bool") for n in "Ready Dirty Closed IndexReady IndexDirty InFlight Snapshotting".split()],
    ("LoadedFlags", "bool[]"), ("DirtyFlags", "bool[]"), ("WorkspaceIdentities", "string[]"),
    ("IndexValidating", "bool"), ("IndexValidationIndex", "int"), ("IndexValidationOther", "int"),
    ("LookupIdentity", "string"), *[(n,"int") for n in "LookupPhase LookupIndex LookupMapping LookupWorkspace SessionWorkspace".split()],
    ("SessionOnly", "bool"), ("PersistenceRequested", "bool"), ("PersistenceStatus", "name"),
    ("PresentationInitialized", "bool"), ("PresentationReady", "bool"), ("PresentationClosed", "bool"),
    ("PresentationIdentity", "string"), ("PresentationWorkspace", "int"), ("PresentationRevision", "int"),
    ("PresentationStatus", "name"), ("PresentationFailure", "name")])
refs = {"Index": "BP_LogbookIndex", "WorkingStore": "BP_LogbookStore", "SnapshotStore": "BP_LogbookStore", "Report": "BP_RunReport"}
old = set(BP.list_variables(bp))
for n, a in refs.items():
    if n not in old: BP.add_object_variable(bp, n, load(a))
for n, a in (("Stores", "BP_LogbookStore"), ("PendingReports", "BP_RunReport")):
    if n not in old: BP.add_object_variable(bp, n, load(a), container_type=ContainerType.ARRAY)
for n, cls in (("Context", unreal.Object.static_class()), ("RequestObject", unreal.SaveGame.static_class()), ("RequestContext", load("BP_LogbookIORequest")), ("Coordinator", load("BP_LogbookIO"))):
    if n not in old: BP.add_object_variable(bp, n, cls)
definitions = {
    "HasObject": [("Object", unreal.Object.static_class())], "ResolveIdentity": [("Context", unreal.Object.static_class())],
    "ValidStorageId": [("Slot", "string")], "BeginLoad": [("Identity", "string")],
    "EnsureWorkspace": [("Identity", "string")], "AppendReport": [("Report", load("BP_RunReport"))],
    "AdvanceStorage": [], "GetRunCount": [], "RefreshView": [], "AdvanceAppend": [],
    "ValidateStore": [("Store", load("BP_LogbookStore")), ("Identity", "string"), ("Slot", "string")],
    "ValidateIndex": [("Value", load("BP_LogbookIndex"))],
    "BeginRequest": [("Kind", "name"), ("Workspace", "int"), ("Payload", unreal.SaveGame.static_class())],
    "StartNativeRequest": [], "CompleteRequest": [("SaveGame", unreal.SaveGame.static_class()), ("Success", "bool")],
    "AdvanceSnapshot": [], "RetryStorage": [], "CloseStorage": [],
    "EnsureSession": [], "PrepareAppend": [("Workspace", "int")],
    "SelectPending": [],
}
graphs = {}
old_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
for n, params in definitions.items():
    graph = graphs[n] = BP.get_graph(bp, n) if n in old_graphs else BP.add_function_graph(bp, n)
    if n in old_graphs: continue
    for p, k in params:
        (BP.add_function_param if isinstance(k, str) else BP.add_object_function_param)(graph, p, k, True)
    if n == "ResolveIdentity":
        BP.add_function_param(graph, "Valid", "bool", False)
        BP.add_function_param(graph, "Identity", "string", False)
    else:
        BP.add_function_param(graph, "Result", "int" if n in ("GetRunCount", "EnsureWorkspace", "EnsureSession") else "bool", False)
BP.compile_blueprint(bp)

if "OnHistoryPresentationChanged" not in {str(graph.get_name()) for graph in BP.list_event_dispatchers(bp)}:
    BP.add_event_dispatcher(bp, "OnHistoryPresentationChanged")
BP.compile_blueprint(bp)
notification_nodes = list(dict.fromkeys(node for node in BP.find_node_types(graphs["RefreshView"], "OnHistoryPresentationChanged", [])
                      if node.rsplit("|", 1)[-1].replace(" ", "") == "CallOnHistoryPresentationChanged"))
assert len(notification_nodes) == 1, notification_nodes
notify = f"({notification_nodes[0]} :self self)"

g = lambda n: f"(Variables|Default|Get{n})"
put = lambda n,v: f"(Variables|Default|Set{n} {v})"
at = lambda a,i: f'(Utilities|Array|Get(acopy) :Array {a} :"Dimension 1" {i})'
length = lambda a: f"(Utilities|Array|Length {a})"
add = lambda a,v: f"(Utilities|Array|Add {a} {v})"
setat = lambda a,i,v: f'(Utilities|Array|SetArrayElem :TargetArray {a} :Index {i} :Item {v})'
remove = lambda a: f"(Utilities|Array|RemoveIndex {a} 0)"
valid = lambda o: f"(CallFunction|HasObject :Object {o})"
prop = lambda cls,obj,n: f"(Class|{cls.replace('_','')}|Get{n} :self {obj})"
sprop = lambda n: prop("BP_LogbookStore", g("WorkingStore"), n)
sput = lambda n,v: f"(Class|BPLogbookStore|Set{n} :self {g('WorkingStore')} :{n} {v})"
inc = lambda n: put(n, f"(+ {g(n)} 1)")
presentation_fields = {"Ready": "bool", "Closed": "bool", "ActiveIdentity": "string", "ActiveWorkspace": "int",
                       "HistoryRevision": "int", "PersistenceStatus": "name", "StorageFailure": "name"}
presentation_cache = {"Ready": "PresentationReady", "Closed": "PresentationClosed", "ActiveIdentity": "PresentationIdentity",
                      "ActiveWorkspace": "PresentationWorkspace", "HistoryRevision": "PresentationRevision",
                      "PersistenceStatus": "PresentationStatus", "StorageFailure": "PresentationFailure"}
presentation_changed = f'(not {g("PresentationInitialized")})'
for field, kind in presentation_fields.items():
    old_value = g(presentation_cache[field])
    comparison = (f'(Utilities|String|NotEqualExactly(String) {old_value} {g(field)})'
                  if kind == "string" else f'(!= {old_value} {g(field)})')
    presentation_changed = f'(or {presentation_changed} {comparison})'
presentation_update = ' '.join(put(presentation_cache[field], g(field)) for field in presentation_fields)
fail = lambda reason: f"{put('StorageFailure', chr(34)+reason+chr(34))} (CallFunction|RefreshView) (return false)"
code = {}
code["HasObject"] = '(fn HasObject (Object) (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))'
code["ResolveIdentity"] = f"""(fn ResolveIdentity (Context)
    {put('Context','Context')}
    (if (not {valid('Context')}) (return false ""))
    (bind (ok systems) (Class|ArcoSystems|GetArcoSys))
    (if (or (not ok) (not {valid('systems')})) (return false ""))
    (bind identity (Class|ArcoSystems|GetMAssociatedSave :self systems))
    (return (> (Utilities|String|Len identity) 0) identity))"""
code["ValidStorageId"] = f"""(fn ValidStorageId (Slot)
    (if (!= (Utilities|String|Len Slot) {len(PREFIX)+32}) (return false))
    (if (not (Utilities|String|StartsWith :SourceString Slot :InPrefix "{PREFIX}" :SearchCase "CaseSensitive")) (return false))
    (bind suffix (Utilities|String|Right :SourceString Slot :Count 32))
    (for character (Utilities|String|GetCharacterArrayfromString suffix)
      (if (not (Utilities|String|Contains :SearchIn "0123456789abcdefABCDEF" :Substring character :bUseCase true)) (return false)))
    (return true))"""
code["RefreshView"] = f"""(fn RefreshView ()
    {put('Dirty', f'(or {g("IndexDirty")} (or (> {g("DirtyCount")} 0) (> {length(g("PendingReports"))} 0)))')}
    {put('Ready','false')}
    (if (and (or {g('SessionOnly')} {g('IndexReady')}) (>= {g('ActiveWorkspace')} 0))
      (if (and (< {g('ActiveWorkspace')} {length(g('Stores'))}) (== {g('Stage')} 0))
        (bind store {at(g('Stores'),g('ActiveWorkspace'))})
        {put('Ready', at(g('LoadedFlags'),g('ActiveWorkspace')))}
        {put('HistoryRevision',prop('BP_LogbookStore','store','Revision'))}))
    {put('PersistenceStatus',f'(select {g("SessionOnly")} "session_only" (select {g("Dirty")} "pending" (select {g("Ready")} "stored" "loading")))')}
    (if (and (!= {g('StorageFailure')} "None") (!= {g('StorageFailure')} "identity_unavailable")) {put('PersistenceStatus','"failed"')})
    (bind presentation_changed {presentation_changed})
    {presentation_update} {put('PresentationInitialized','true')}
    (if presentation_changed {notify})
    (return {g('Ready')}))"""
code["EnsureSession"] = f"""(fn EnsureSession ()
    (if (>= {g('SessionWorkspace')} 0) (return {g('SessionWorkspace')}))
    (bind store (Game|ConstructObjectfromClass :Class "{ROOT}/BP_LogbookStore.BP_LogbookStore_C" :self self))
    (bind i {add(g('Stores'),'store')}) {add(g('WorkspaceIdentities'),'""')}
    {add(g('LoadedFlags'),'true')} {add(g('DirtyFlags'),'false')}
    {put('SessionWorkspace','i')} (return i))"""
code["BeginLoad"] = f"""(fn BeginLoad (Identity)
    (if {g('Closed')} (return false))
    (if (== (Utilities|String|Len Identity) 0) {inc('Generation')} {put('ActiveIdentity','""')}
      {put('SessionOnly','true')} {put('ActiveWorkspace','(CallFunction|EnsureSession)')} {fail('identity_unavailable')})
    {put('SessionOnly','false')} {put('PersistenceRequested','true')}
    (if (== {g('StorageFailure')} "identity_unavailable") {put('StorageFailure','"None"')})
    (if (Utilities|String|NotEqualExactly(String) Identity {g('ActiveIdentity')}) {inc('Generation')} {put('ActiveIdentity','Identity')} {put('ActiveWorkspace','-1')} {put('Ready','false')})
    (if {g('IndexReady')} {put('ActiveWorkspace','(CallFunction|EnsureWorkspace :Identity Identity)')})
    (CallFunction|RefreshView) (return true))"""
code["EnsureWorkspace"] = f"""(fn EnsureWorkspace (Identity)
    (if (or (not {g('IndexReady')}) (== (Utilities|String|Len Identity) 0)) (return -1))
    (if (Utilities|String|NotEqualExactly(String) Identity {g('LookupIdentity')})
      {put('LookupIdentity','Identity')} {put('LookupPhase','0')} {put('LookupIndex','0')} (return -1))
    (if (== {g('LookupPhase')} 0)
      (if (< {g('LookupIndex')} {length(g('WorkspaceIdentities'))})
        (if (Utilities|String|EqualExactly(String) Identity {at(g('WorkspaceIdentities'),g('LookupIndex'))})
          {put('LookupWorkspace',g('LookupIndex'))} {put('LookupPhase','3')} (return {g('LookupWorkspace')}))
        {inc('LookupIndex')} (return -1))
      {put('LookupPhase','1')} {put('LookupIndex','0')} (return -1))
    (if (== {g('LookupPhase')} 1)
      (if (< {g('LookupIndex')} {length(prop('BP_LogbookIndex',g('Index'),'Identities'))})
        (if (Utilities|String|EqualExactly(String) Identity {at(prop('BP_LogbookIndex',g('Index'),'Identities'),g('LookupIndex'))})
          {put('LookupMapping',g('LookupIndex'))} {put('LookupPhase','2')} (return -1))
        {inc('LookupIndex')} (return -1))
      (bind id (Utilities|String|Append :A "{PREFIX}" :B (Guid|ToString(Guid) (Guid|NewGuid))))
      (bind compact (Utilities|String|Replace :SourceString id :From "-" :To "" :SearchCase "CaseSensitive"))
      (if (not (CallFunction|ValidStorageId :Slot compact)) {put('StorageFailure','"invalid_history_slot"')} (return -1))
      (Utilities|Array|Add {prop('BP_LogbookIndex',g('Index'),'Identities')} Identity)
      (Utilities|Array|Add {prop('BP_LogbookIndex',g('Index'),'StorageIds')} compact)
      (Class|BPLogbookIndex|SetRevision :self {g('Index')} :Revision (+ {prop('BP_LogbookIndex',g('Index'),'Revision')} 1))
      {put('IndexDirty','true')}
      {put('LookupMapping',f'(- {length(prop("BP_LogbookIndex",g("Index"),"Identities"))} 1)')}
      {put('LookupPhase','2')} (return -1))
    (if (== {g('LookupPhase')} 3) (return {g('LookupWorkspace')}))
    (bind store (Game|ConstructObjectfromClass :Class "{ROOT}/BP_LogbookStore.BP_LogbookStore_C" :self self))
    (Class|BPLogbookStore|SetIdentity :self store :Identity Identity)
    (Class|BPLogbookStore|SetStorageId :self store :StorageId {at(prop('BP_LogbookIndex',g('Index'),'StorageIds'),g('LookupMapping'))})
    (bind result {add(g('Stores'),'store')}) {add(g('WorkspaceIdentities'),'Identity')}
    {add(g('LoadedFlags'),'false')} {add(g('DirtyFlags'),'false')}
    {put('LookupWorkspace','result')} {put('LookupPhase','3')} (return result))"""
code["AppendReport"] = f"""(fn AppendReport (Report)
    (if (or {g('Closed')} (not {valid('Report')})) (return false))
    (if (not {prop('BP_RunReport','Report','ReportDone')}) (return false))
    (if (> (Utilities|String|Len {prop('BP_RunReport','Report','SaveIdentity')}) 0) {put('PersistenceRequested','true')})
    (if (Utilities|Array|ContainsItem {g('PendingReports')} Report) (return true))
    {put('PendingMatchCount','0')} {put('PendingOldest','-1')}
    (for i (range {length(g('PendingReports'))})
      (bind queued {at(g('PendingReports'),'i')})
      (if (Utilities|String|EqualExactly(String) {prop('BP_RunReport','queued','SaveIdentity')} {prop('BP_RunReport','Report','SaveIdentity')})
        (if (Utilities|String|EqualExactly(String) {prop('BP_RunReport','queued','RunId')} {prop('BP_RunReport','Report','RunId')}) (return true))
        (if (not (and (> {g('Stage')} 0) (== queued {g('Report')})))
          {inc('PendingMatchCount')}
          (if (< {g('PendingOldest')} 0) {put('PendingOldest','i')}))))
    (if (>= {g('PendingMatchCount')} 50) (Utilities|Array|RemoveIndex {g('PendingReports')} {g('PendingOldest')}))
    {add(g('PendingReports'),'Report')} {put('PendingCursor','0')} (CallFunction|RefreshView) (return true))"""
# Loaded payload validation rejects all malformed offsets before it can be installed.
checks = [f'(if (!= {length(prop("BP_LogbookStore","Store",n))} count) (return false))' for n,k in scalar_fields]
for n,k in array_fields:
    checks += [f'''(if (or (!= {length(prop('BP_LogbookStore','Store',n+'Offsets'))} count) (!= {length(prop('BP_LogbookStore','Store',n+'Lengths'))} count)) (return false))
      (for i (range 0 count)
        (bind offset {at(prop('BP_LogbookStore','Store',n+'Offsets'),'i')})
        (bind size {at(prop('BP_LogbookStore','Store',n+'Lengths'),'i')})
        (if (or (< offset 0) (< size 0)) (return false))
        (if (== i 0) (if (!= offset 0) (return false))
          (else (if (!= offset (+ {at(prop('BP_LogbookStore','Store',n+'Offsets'),'(- i 1)')} {at(prop('BP_LogbookStore','Store',n+'Lengths'),'(- i 1)')})) (return false))))
        (if (== i (- count 1)) (if (!= (+ offset size) {length(prop('BP_LogbookStore','Store',n))}) (return false))))
      (if (and (== count 0) (!= {length(prop('BP_LogbookStore','Store',n))} 0)) (return false))''']
code['ValidateStore'] = f'''(fn ValidateStore (Store Identity Slot)
    (if (not {valid('Store')}) (return false))
    (if (or (!= {prop('BP_LogbookStore','Store','SchemaVersion')} 1) (or (Utilities|String|NotEqualExactly(String) {prop('BP_LogbookStore','Store','Identity')} Identity) (Utilities|String|NotEqualExactly(String) {prop('BP_LogbookStore','Store','StorageId')} Slot))) (return false))
    (bind count {length(prop('BP_LogbookStore','Store','RunId'))}) (if (> count 50) (return false))
    {' '.join(checks)} (return true))'''
code['ValidateIndex'] = f'''(fn ValidateIndex (Value)
    (if (not {valid('Value')}) (return false))
    (if (!= {prop('BP_LogbookIndex','Value','SchemaVersion')} 1) (return false))
    (bind ids {prop('BP_LogbookIndex','Value','Identities')}) (bind slots {prop('BP_LogbookIndex','Value','StorageIds')})
    (if (!= {length('ids')} {length('slots')}) (return false))
    (return true))'''
code['GetRunCount'] = f'''(fn GetRunCount () (CallFunction|RefreshView)
    (if (not {g('Ready')}) (return 0))
    (return {length(prop('BP_LogbookStore',at(g('Stores'),g('ActiveWorkspace')),'RunId'))}))'''
code['RetryStorage'] = f'''(fn RetryStorage () (if {g('Closed')} (return false))
    (bind changed (!= {g('StorageFailure')} "None")) {put('StorageFailure','"None"')}
    (if changed {notify}) (return true))'''
code['CloseStorage'] = f'''(fn CloseStorage () {put('Closed','true')} (CallFunction|RefreshView)
    (if (and {g('InFlight')} (or (== {g('RequestKind')} "load_index") (== {g('RequestKind')} "load_payload")))
      (Class|BPLogbookIO|Release :self {g('Coordinator')} :Request {g('RequestContext')}))
    (if (or {g('Dirty')} (or {g('InFlight')} {g('Snapshotting')})) {fail('history_unflushed')}) (return true))'''

# One accepted request owns these fields until its sole native callback arrives.
code['BeginRequest'] = f'''(fn BeginRequest (Kind Workspace Payload)
    (if (or {g('Closed')} {g('InFlight')}) (return false))
    (if {prop('BP_LogbookIO',g('Coordinator'),'Busy')} (return false))
    {put('RequestKind','Kind')} {put('RequestWorkspace','Workspace')} {put('RequestGeneration',g('Generation'))}
    {put('RequestIdentity','""')} {put('RequestRevision','0')} {put('RequestSlot',f'"{INDEX_SLOT}"')}
    (if (or (== Kind "load_payload") (== Kind "save_payload"))
      (if (or (< Workspace 0) (>= Workspace {length(g('Stores'))})) (return false))
      (bind store {at(g('Stores'),'Workspace')})
      {put('RequestIdentity',prop('BP_LogbookStore','store','Identity'))}
      {put('RequestSlot',prop('BP_LogbookStore','store','StorageId'))}
      {put('RequestRevision',prop('BP_LogbookStore','store','Revision'))}
      (if (not (CallFunction|ValidStorageId :Slot {g('RequestSlot')})) {fail('invalid_history_slot')}))
    (if (== Kind "save_index") {put('RequestRevision',prop('BP_LogbookIndex',g('Index'),'Revision'))})
    (bind request (Game|ConstructObjectfromClass :Class "{ROOT}/BP_LogbookIORequest.BP_LogbookIORequest_C" :self self))
    (Class|BPLogbookIORequest|SetOwner :self request :Owner self)
    (Class|BPLogbookIORequest|SetContext :self request :Context {g('Context')})
    (Class|BPLogbookIORequest|SetCoordinator :self request :Coordinator {g('Coordinator')})
    (Class|BPLogbookIORequest|SetKind :self request :Kind Kind)
    (Class|BPLogbookIORequest|SetSlot :self request :Slot {g('RequestSlot')})
    (Class|BPLogbookIORequest|SetIdentity :self request :Identity {g('RequestIdentity')})
    (Class|BPLogbookIORequest|SetGeneration :self request :Generation {g('RequestGeneration')})
    (Class|BPLogbookIORequest|SetRevision :self request :Revision {g('RequestRevision')})
    (Class|BPLogbookIORequest|SetWorkspace :self request :Workspace Workspace)
    (Class|BPLogbookIORequest|SetPayload :self request :Payload Payload)
    (bind acquired (Class|BPLogbookIO|Acquire :self {g('Coordinator')} :Request request))
    (if (not acquired) (return false))
    {put('RequestContext','request')}
    (if {valid('Payload')}
      (if (== Kind "save_index")
        (bind index (Utilities|Casting|CastToBP_LogbookIndex :Object Payload))
        (Class|BPLogbookIndex|SetIOCoordinator :self index :IOCoordinator {g('Coordinator')})
        (else
          (bind store (Utilities|Casting|CastToBP_LogbookStore :Object Payload))
          (Class|BPLogbookStore|SetIOCoordinator :self store :IOCoordinator {g('Coordinator')}))))
    {put('RequestObject','Payload')} {put('InFlight','true')}
    (bind started (CallFunction|StartNativeRequest))
    (if (not started) {put('InFlight','false')} (Class|BPLogbookIO|Release :self {g('Coordinator')} :Request request) {fail('history_storage_unavailable')}) (return true))'''
code['StartNativeRequest'] = f'''(fn StartNativeRequest ()
    (if (not {valid(g('Context'))}) (return false))
    (Class|BPLogbookIORequest|BeginNative :self {g('RequestContext')}) (return true))'''
code['CompleteRequest'] = f'''(fn CompleteRequest (SaveGame Success)
    (if (not {g('InFlight')}) (return false))
    (Class|BPLogbookIO|Release :self {g('Coordinator')} :Request {g('RequestContext')})
    {put('InFlight','false')}
    (if {g('Closed')} (return false))
    (if (not Success) {fail('history_storage_failed')})
    (if (== {g('RequestKind')} "load_index")
      (bind value (Utilities|Casting|CastToBP_LogbookIndex :Object SaveGame)
        (:CastFailed {fail('invalid_history_index')})
        (:then
          (if (not (CallFunction|ValidateIndex :Value value)) {fail('invalid_history_index')})
          {put('Index','value')} {put('IndexValidating','true')} {put('IndexValidationIndex','0')} {put('IndexValidationOther','0')} (return true))))
    (if (== {g('RequestKind')} "save_index")
      (if (== {g('RequestRevision')} {prop('BP_LogbookIndex',g('Index'),'Revision')}) {put('IndexDirty','false')})
      (CallFunction|RefreshView) (return true))
    (bind i {g('RequestWorkspace')})
    (if (or (< i 0) (>= i {length(g('Stores'))})) {fail('history_request_stale')})
    (bind store {at(g('Stores'),'i')})
    (if (or (Utilities|String|NotEqualExactly(String) {prop('BP_LogbookStore','store','Identity')} {g('RequestIdentity')}) (Utilities|String|NotEqualExactly(String) {prop('BP_LogbookStore','store','StorageId')} {g('RequestSlot')})) {fail('history_request_stale')})
    (if (== {g('RequestKind')} "load_payload")
      (bind value (Utilities|Casting|CastToBP_LogbookStore :Object SaveGame)
        (:CastFailed {fail('invalid_history_file')})
        (:then
          (if (not (CallFunction|ValidateStore :Store value :Identity {g('RequestIdentity')} :Slot {g('RequestSlot')})) {fail('invalid_history_file')})
          (if (or {at(g('DirtyFlags'),'i')} {at(g('LoadedFlags'),'i')}) {fail('history_request_stale')})
          {setat(g('Stores'),'i','value')} {setat(g('LoadedFlags'),'i','true')} {put('PendingCursor','0')}
          (if (and (== {g('RequestGeneration')} {g('Generation')}) (Utilities|String|EqualExactly(String) {g('RequestIdentity')} {g('ActiveIdentity')})) (CallFunction|RefreshView))
          (return true))))
    (if (and (== {g('RequestKind')} "save_payload") (and {at(g('DirtyFlags'),'i')} (== {g('RequestRevision')} {prop('BP_LogbookStore','store','Revision')})))
      {setat(g('DirtyFlags'),'i','false')} {put('DirtyCount',f'(- {g("DirtyCount")} 1)')})
    (CallFunction|RefreshView) (return true))'''

# Append/eviction copies one scalar/array element or adjusts one offset per advance.
append_parts = []
evict_parts = []
for field,(n,k) in enumerate(array_fields):
    arr, offsets, sizes = sprop(n),sprop(n+'Offsets'),sprop(n+'Lengths')
    evict_parts.append(f'''(if (== {g('FieldCursor')} {field})
      (if (== {g('ElementCursor')} 0) {put('EvictRemaining',at(sizes,'0'))} {put('ElementCursor','1')} (return true))
      (if (> {g('EvictRemaining')} 0) {remove(arr)} {put('EvictRemaining',f'(- {g("EvictRemaining")} 1)')} (return true))
      (if (< {g('ElementCursor')} {length(offsets)})
        {setat(offsets,g('ElementCursor'),f'(- {at(offsets,g("ElementCursor"))} {at(sizes,"0")})')}
        {inc('ElementCursor')} (return true))
      {remove(offsets)} {remove(sizes)} {inc('FieldCursor')} {put('ElementCursor','0')} (return true))''')
    source = prop('BP_RunReport',g('Report'),n)
    append_parts.append(f'''(if (== {g('FieldCursor')} {len(scalar_fields)+field})
      (if (== {g('ElementCursor')} 0) {add(offsets,length(arr))} {add(sizes,length(source))})
      (if (< {g('ElementCursor')} {length(source)}) {add(arr,at(source,g('ElementCursor')))} {inc('ElementCursor')} (return true))
      {inc('FieldCursor')} {put('ElementCursor','0')} (return true))''')
for field,(n,k) in enumerate(scalar_fields):
    value = prop('BP_RunReport',g('Report'),n)
    preparation = ''
    for prefix in ('Started', 'Ended'):
        if n.startswith(prefix):
            source = prop('BP_RunReport', g('Report'), prefix + 'At')
            components = ('Year','Month','Day','Hour','Minute','Second','Millisecond')
            preparation = f'(bind ({" ".join(components)}) (Math|DateTime|BreakDateTime {source}))'
            value = n.removeprefix(prefix)
    append_parts.insert(field, f'''(if (== {g('FieldCursor')} {field}) {preparation} {add(sprop(n),value)} {inc('FieldCursor')} (return true))''')
    evict_parts.append(f'''(if (== {g('FieldCursor')} {len(array_fields)+field}) {remove(sprop(n))} {inc('FieldCursor')} (return true))''')
code['AdvanceAppend'] = f'''(fn AdvanceAppend ()
    (if (== {g('Stage')} 1)
      {' '.join(evict_parts)}
      {put('Stage','2')} {put('FieldCursor','0')} {put('ElementCursor','0')} (return true))
    {' '.join(append_parts)}
    {sput('Revision',f'(+ {sprop("Revision")} 1)')}
    (if (and (> (Utilities|String|Len {sprop('Identity')}) 0) (not {at(g('DirtyFlags'),g('WorkWorkspace'))})) {setat(g('DirtyFlags'),g('WorkWorkspace'),'true')} {inc('DirtyCount')})
    {remove(g('PendingReports'))} {put('Stage','0')} {put('FieldCursor','0')} {put('ElementCursor','0')}
    (Variables|Default|SetReport) (CallFunction|RefreshView) (return true))'''
snapshots = [f'''(if (== {g('SnapshotCursor')} {i})
    (Class|BPLogbookStore|Set{n} :self {g('SnapshotStore')} :{n} {sprop(n)}) {inc('SnapshotCursor')} (return true))''' for i,(n,k) in enumerate(store_fields)]
code['AdvanceSnapshot'] = f'''(fn AdvanceSnapshot () {' '.join(snapshots)}
    {put('Snapshotting','false')}
    (bind accepted (CallFunction|BeginRequest :Kind "save_payload" :Workspace {g('WorkWorkspace')} :Payload {g('SnapshotStore')}))
    (return accepted))'''
code['PrepareAppend'] = f'''(fn PrepareAppend (Workspace)
    {put('WorkWorkspace','Workspace')}
    (if (< Workspace 0) (return false))
    {put('WorkingStore',at(g('Stores'),'Workspace'))}
    (if {at(g('LoadedFlags'),'Workspace')}
      (if (Utilities|Array|ContainsItem {sprop('RunId')} {prop('BP_RunReport',g('Report'),'RunId')})
        {remove(g('PendingReports'))} (CallFunction|RefreshView) (return true))
      (bind wasReady {g('Ready')})
      {put('Stage',f'(select (>= {length(sprop("RunId"))} 50) 1 2)')} {put('Ready','false')}
      {put('FieldCursor','0')} {put('ElementCursor','0')}
      (if wasReady {put('PresentationReady','false')} {notify}) (return true))
    {put('StorageCursor','Workspace')} (return false))'''
code['SelectPending'] = f'''(fn SelectPending ()
    (if (== {length(g('PendingReports'))} 0) (return false))
    (if (>= {g('PendingCursor')} {length(g('PendingReports'))}) {put('PendingCursor','0')})
    {put('Report',at(g('PendingReports'),g('PendingCursor')))}
    (if (== (Utilities|String|Len {prop('BP_RunReport',g('Report'),'SaveIdentity')}) 0)
      {put('WorkWorkspace','(CallFunction|EnsureSession)')}
      (else
        (if (not {g('IndexReady')}) {inc('PendingCursor')} (return false))
        {put('WorkWorkspace',f'(CallFunction|EnsureWorkspace :Identity {prop("BP_RunReport",g("Report"),"SaveIdentity")})')}
        (if (< {g('WorkWorkspace')} 0) (return false))))
    (if (not {at(g('LoadedFlags'),g('WorkWorkspace'))})
      {put('StorageCursor',g('WorkWorkspace'))} {inc('PendingCursor')} (return false))
    (if (> {g('PendingCursor')} 0)
      (Utilities|Array|RemoveIndex {g('PendingReports')} {g('PendingCursor')})
      (Utilities|Array|Insert :TargetArray {g('PendingReports')} :NewItem {g('Report')} :Index 0))
    {put('PendingCursor','0')}
    (bind prepared (CallFunction|PrepareAppend :Workspace {g('WorkWorkspace')})) (return prepared))'''
code['AdvanceStorage'] = f'''(fn AdvanceStorage ()
    (if {g('Closed')} (return false))
    (if (> {g('Stage')} 0) (bind advanced (CallFunction|AdvanceAppend)) (return advanced))
    (if {g('Snapshotting')}
      (if (and (!= {g('StorageFailure')} "None") (!= {g('StorageFailure')} "identity_unavailable")) (return false))
      (bind advanced (CallFunction|AdvanceSnapshot)) (return advanced))
    (if (> {length(g('PendingReports'))} 0)
      (bind selected (CallFunction|SelectPending)) (if selected (return true)))
    (if (and (!= {g('StorageFailure')} "None") (!= {g('StorageFailure')} "identity_unavailable")) (CallFunction|RefreshView) (return false))
    (if (and {prop('BP_LogbookIO',g('Coordinator'),'Busy')} (!= {prop('BP_LogbookIO',g('Coordinator'),'CurrentRequest')} {g('RequestContext')})) (return false))
    (if (not {g('PersistenceRequested')}) (CallFunction|RefreshView) (return false))
    (if {g('IndexValidating')}
      (bind ids {prop('BP_LogbookIndex',g('Index'),'Identities')})
      (bind slots {prop('BP_LogbookIndex',g('Index'),'StorageIds')})
      (bind i {g('IndexValidationIndex')})
      (if (< i {length('ids')})
        (if (or (== (Utilities|String|Len {at('ids','i')}) 0) (not (CallFunction|ValidStorageId :Slot {at('slots','i')}))) {fail('invalid_history_index')})
        (if (< {g('IndexValidationOther')} i)
          (if (or (Utilities|String|EqualExactly(String) {at('ids','i')} {at('ids',g('IndexValidationOther'))})
            (Utilities|String|Equal,CaseInsensitive(String) {at('slots','i')} {at('slots',g('IndexValidationOther'))})) {fail('invalid_history_index')})
          {inc('IndexValidationOther')} (return true))
        {inc('IndexValidationIndex')} {put('IndexValidationOther','0')} (return true))
      {put('IndexValidating','false')} {put('IndexReady','true')} (return true))
    (if (not {g('IndexReady')})
      (if {g('InFlight')} (return false))
      (if (SaveGame|DoesSaveGameExist :SlotName "{INDEX_SLOT}" :UserIndex 0)
        (bind accepted (CallFunction|BeginRequest :Kind "load_index" :Workspace -1)) (return accepted))
      (bind value (Game|ConstructObjectfromClass :Class "{ROOT}/BP_LogbookIndex.BP_LogbookIndex_C" :self self))
      {put('Index','value')} {put('IndexReady','true')} (return true))
    (if (and (< {g('ActiveWorkspace')} 0) (> (Utilities|String|Len {g('ActiveIdentity')}) 0)) {put('ActiveWorkspace',f'(CallFunction|EnsureWorkspace :Identity {g("ActiveIdentity")})')} (return true))
    (if {g('InFlight')} (CallFunction|RefreshView) (return false))
    (if {g('IndexDirty')}
      (bind value (Game|ConstructObjectfromClass :Class "{ROOT}/BP_LogbookIndex.BP_LogbookIndex_C" :self self))
      (Class|BPLogbookIndex|SetRevision :self value :Revision {prop('BP_LogbookIndex',g('Index'),'Revision')})
      (Class|BPLogbookIndex|SetIdentities :self value :Identities {prop('BP_LogbookIndex',g('Index'),'Identities')})
      (Class|BPLogbookIndex|SetStorageIds :self value :StorageIds {prop('BP_LogbookIndex',g('Index'),'StorageIds')})
      (bind accepted (CallFunction|BeginRequest :Kind "save_index" :Workspace -1 :Payload value)) (return accepted))
    (if (== {length(g('Stores'))} 0) (return false))
    (if (>= {g('StorageCursor')} {length(g('Stores'))}) {put('StorageCursor','0')})
    {put('WorkWorkspace',g('StorageCursor'))} {inc('StorageCursor')}
    (bind i {g('WorkWorkspace')})
    {put('WorkingStore',at(g('Stores'),'i'))}
    (if (not {at(g('LoadedFlags'),'i')})
      (if (not (CallFunction|ValidStorageId :Slot {sprop('StorageId')})) {fail('invalid_history_slot')})
      (if (SaveGame|DoesSaveGameExist :SlotName {sprop('StorageId')} :UserIndex 0)
        (bind accepted (CallFunction|BeginRequest :Kind "load_payload" :Workspace i)) (return accepted))
      {setat(g('LoadedFlags'),'i','true')} {put('PendingCursor','0')} (CallFunction|RefreshView) (return true))
    (if {at(g('DirtyFlags'),'i')}
      {put('WorkWorkspace','i')} {put('SnapshotCursor','0')}
      {put('SnapshotStore',f'(Game|ConstructObjectfromClass :Class "{ROOT}/BP_LogbookStore.BP_LogbookStore_C" :self self)')}
      {put('Snapshotting','true')} (return true))
    (CallFunction|RefreshView) (return false))'''

# Immutable receivers prevent a late abandoned read from releasing a newer request.
event_graph = BP.get_graph(request_bp, "EventGraph")
events = f'''(event Custom|BeginNative ()
  (if (or (== {g('Kind')} "load_index") (== {g('Kind')} "load_payload"))
    (SaveGame|AsyncLoadGamefromSlot :WorldContextObject {g('Context')} :SlotName {g('Slot')} :UserIndex 0
      (:Completed (CallFunction|Complete :SaveGame _savegame :Success _bsuccess)))
    (else (SaveGame|AsyncSaveGametoSlot :WorldContextObject {g('Context')} :SaveGameObject {g('Payload')} :SlotName {g('Slot')} :UserIndex 0
      (:Completed (CallFunction|Complete :SaveGame _savegame :Success _bsuccess))))))'''
receiver = f'''(fn Complete (SaveGame Success)
    (bind gate (Utilities|Casting|CastToBP_LogbookIO :Object {g('Coordinator')})
      (:CastFailed (return false))
      (:then
        (if (!= {prop('BP_LogbookIO','gate','CurrentRequest')} self) (return false))
        (bind owner (Utilities|Casting|CastToBP_Logbook :Object {g('Owner')})
          (:CastFailed (Class|BPLogbookIO|Release :self gate :Request self) (return false))
          (:then
            (if (!= {prop('BP_Logbook','owner','RequestContext')} self)
              (Class|BPLogbookIO|Release :self gate :Request self) (return false))
            (bind applied (Class|BPLogbook|CompleteRequest :self owner :SaveGame SaveGame :Success Success))
            (return applied))))))'''
with toolset_registry.tool_raising_exceptions():
    BP.write_graph_dsl(complete_graph, receiver)
    BP.write_graph_dsl(event_graph, events)
    BP.compile_blueprint(request_bp, warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(request_bp)
    for name, source in code.items():
        unreal.log("WO_LOGBOOK_WRITE " + name)
        graph = graphs[name]
        blueprint_dsl.Transpiler(graph, BP.create_node, BP.connect_pins, BP._get_node_info,
            BP.set_pin_value, lambda graph: BP.find_nodes(graph), delete_node_fn=BP.delete_node,
            find_node_types_fn=lambda query: BP.find_node_types(graph, query)).transpile(source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    cdo = unreal.get_default_object(bp.generated_class())
    cdo.set_editor_property("ActiveWorkspace", -1)
    cdo.set_editor_property("SessionWorkspace", -1)
    cdo.set_editor_property("SessionOnly", True)
    cdo.set_editor_property("Coordinator", coordinator)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    coordinator.set_editor_property("Busy", False)
    coordinator.set_editor_property("CurrentRequest", None)
    assert unreal.EditorAssetLibrary.save_loaded_asset(coordinator)
unreal.log("WO_LOGBOOK_GENERATED")
exec(Path(__file__).with_name("test_logbook.py").read_text(encoding="utf-8"))
