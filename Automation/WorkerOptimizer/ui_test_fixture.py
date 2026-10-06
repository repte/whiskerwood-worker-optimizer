"""Transient native setters for UI fixtures; never saved or packaged."""
import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

ROOT = "/Game/Mods/WorkerOptimizer/"
load = lambda name: unreal.load_class(None, ROOT + name + "." + name + "_C")
fixture = BP.create("/Game/WorkerOptimizerEditorTests", "BP_CompactUIInputs", unreal.Object.static_class())
methods = {
    "Busy": [("Model",load("BP_SettingsModel")),("Value","bool")],
    "History": [("Book",load("BP_Logbook")),("Store",load("BP_LogbookStore"))],
    "Mutation": [("Book",load("BP_Logbook")),("Store",load("BP_LogbookStore")),("Enabled","bool")],
    "Evict": [("Book",load("BP_Logbook")),("Store",load("BP_LogbookStore"))],
    "Detail": [("View",load("WBP_LogbookView")),("Page","int"),("Total","int")],
    "Controller": [("Controller",load("BP_WorkerOptimizer"))],
}
graphs = {}
for name, args in methods.items():
    graph = graphs[name] = BP.add_function_graph(fixture,name)
    for param,kind in args:
        if isinstance(kind,str): BP.add_function_param(graph,param,kind,True)
        else: BP.add_object_function_param(graph,param,kind,True)
BP.compile_blueprint(fixture)
code = {
    "Busy": '(fn Busy (Model Value) (Class|BPSettingsModel|SetBusy :self Model :Busy Value))',
    "History": '''(fn History (Book Store)
      (Utilities|Array|Add (Class|BPLogbook|GetStores :self Book) Store)
      (Class|BPLogbook|SetActiveWorkspace :self Book :ActiveWorkspace 0)
      (Class|BPLogbook|SetReady :self Book :Ready true)
      (Class|BPLogbook|SetHistoryRevision :self Book :HistoryRevision 1)
      (Class|BPLogbook|SetPersistenceStatus :self Book :PersistenceStatus "session_only")
      (for i (range 50)
        (Utilities|Array|Add (Class|BPLogbookStore|GetRunId :self Store) (Utilities|String|Append :A "run-" :B (Utilities|String|ToString(Integer) i)))
        (Utilities|Array|Add (Class|BPLogbookStore|GetOutcome :self Store) (select (== i 49) "cancelled" "completed"))
        (Utilities|Array|Add (Class|BPLogbookStore|GetFailure :self Store) (select (== i 49) "cancelled" "None"))
        (Utilities|Array|Add (Class|BPLogbookStore|GetTrigger :self Store) "manual")
        (Utilities|Array|Add (Class|BPLogbookStore|GetConfirmedChanges :self Store) 0)))''',
    "Mutation": '''(fn Mutation (Book Store Enabled)
      (Class|BPLogbook|SetStage :self Book :Stage (select Enabled 1 0))
      (Class|BPLogbook|SetWorkWorkspace :self Book :WorkWorkspace 0)
      (if Enabled (Utilities|Array|Add (Class|BPLogbookStore|GetRunId :self Store) "partial")
        (else (Utilities|Array|RemoveIndex (Class|BPLogbookStore|GetRunId :self Store) 50)
          (Class|BPLogbook|SetHistoryRevision :self Book :HistoryRevision 2))))''',
    "Detail": '''(fn Detail (View Page Total)
      (Class|WBPLogbookView|SetDetailTotal :self View :DetailTotal Total)
      (Class|WBPLogbookView|SetDetailPage :self View :DetailPage Page))''',
    "Controller": '''(fn Controller (Controller)
      (Class|BPWorkerOptimizer|SetContext :self Controller :Context Controller)
      (bind settings (Game|ConstructObjectfromClass :Class "/Game/Mods/WorkerOptimizer/BP_PrioritySettings.BP_PrioritySettings_C" :self Controller))
      (bind catalog (Game|ConstructObjectfromClass :Class "/Game/Mods/WorkerOptimizer/BP_DefinitionCatalog.BP_DefinitionCatalog_C" :self Controller))
      (bind history (Game|ConstructObjectfromClass :Class "/Game/Mods/WorkerOptimizer/BP_Logbook.BP_Logbook_C" :self Controller))
      (Class|BPWorkerOptimizer|SetSettings :self Controller :Settings settings)
      (Class|BPWorkerOptimizer|SetPolicyCatalog :self Controller :PolicyCatalog catalog)
      (Class|BPWorkerOptimizer|SetLogbook :self Controller :Logbook history))''',
}
code['Evict'] = '(fn Evict (Book Store) ' + ' '.join(
    f'(Utilities|Array|RemoveIndex (Class|BPLogbookStore|Get{field} :self Store) 0) '
    f'(Utilities|Array|Add (Class|BPLogbookStore|Get{field} :self Store) {value})'
    for field, value in [('RunId','"run-50"'),('Outcome','"completed"'),('Failure','"None"'),('Trigger','"manual"'),('ConfirmedChanges','0')]
) + ' (Class|BPLogbook|SetHistoryRevision :self Book :HistoryRevision 3))'
with toolset_registry.tool_raising_exceptions():
    for name,source in code.items(): BP.write_graph_dsl(graphs[name],source)
    BP.compile_blueprint(fixture,warnings_as_errors=True)
inputs = unreal.new_object(fixture.generated_class())
