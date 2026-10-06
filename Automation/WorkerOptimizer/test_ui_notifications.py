"""Source guards for presentation events, independent of the editor runtime."""
from pathlib import Path
import sys


def run():
    folder = Path(__file__).parent
    sources = {name: (folder / ("generate_" + name + ".py")).read_text(encoding="utf-8")
               for name in ("controller", "logbook", "settings_model", "lifecycle")}
    dispatchers = {"controller": "OnControllerPresentationChanged", "logbook": "OnHistoryPresentationChanged",
                   "settings_model": "OnSettingsPresentationChanged"}
    for name, dispatcher in dispatchers.items():
        assert 'BP.add_event_dispatcher(bp, "' + dispatcher + '")' in sources[name], name
        assert "find_node_types" in sources[name], name
        assert "notification_nodes = list(dict.fromkeys" in sources[name], name
        assert "create_presentation_node" not in sources[name], name
    controller = sources["controller"]
    final_mutations = {"BeginTriggeredRun": "Clear {g('FinalWorkers')}",
                       "FailRun": "CallFunction|AdvanceTerminalReport",
                       "CompleteRun": "CallFunction|AdvanceTerminalReport",
                       "PublishTerminalReport": "put('CompletedRecordCount'"}
    for function, final_mutation in final_mutations.items():
        start = controller.index('code["' + function + '"]')
        end = controller.find('\ncode[', start + 1)
        body = controller[start:end if end >= 0 else None]
        assert "{notify}" in body, function
        assert body.index(final_mutation) < body.index("{notify}"), function
    assert "{put('LateEndPending', 'false')} {notify}" in controller
    assert "or {g('RunActive')} {g('ReportPending')}" in controller
    assert "or {prop('Runner', 'Active')} {prop('Runner', 'Waiting')}" in controller
    start = controller.index('code["PreparePolicyKeys"]')
    end = controller.index('\ndef concat', start)
    policy = controller[start:end]
    assert "(bind ready {invoke('Settings', 'FinishPolicyKeys')}) (if ready {notify}) (return ready)" in policy
    assert "(if {prop('Settings', 'PolicyKeysReady')} (return true))" in policy
    assert policy.count("{notify}") == 1
    logbook = sources["logbook"]
    assert "PresentationReady" in logbook
    assert "PresentationRevision" in logbook
    assert "PresentationStatus" in logbook
    assert "presentation_changed" in logbook
    assert "(if presentation_changed {notify})" in logbook
    assert logbook.index("{presentation_update} {put('PresentationInitialized','true')}") < logbook.index("(if presentation_changed {notify})")
    assert "(if wasReady {put('PresentationReady','false')} {notify})" in logbook
    settings = sources["settings_model"]
    assert "(if written {put('OptionRevision'" in settings
    assert "{notify}) (return written)" in settings
    test_source = Path(__file__).read_text(encoding="utf-8")
    native_source = test_source[test_source.index("\ndef run_native():"):]
    assert "set_editor_property" not in native_source
    assert "BP_NotificationInputs" in native_source
    assert "save_loaded_asset" not in native_source
    print("WO_UI_NOTIFICATIONS_SOURCE_PASS")


def run_native():
    import unreal
    import toolset_registry
    from editor_toolset.toolsets.blueprint import BlueprintTools as BP
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    # Blueprint setters exercise protected instance fields without changing flags.
    fixture = BP.create("/Game/WorkerOptimizerEditorTests", "BP_NotificationInputs", unreal.Object.static_class())
    field_types = {
        "BP_WorkerOptimizer": {"Initialized": "bool", "Settings": load("BP_PrioritySettings"),
                               "PolicyCatalog": load("BP_DefinitionCatalog"), "RunActive": "bool", "ReportPending": "bool"},
        "BP_DefinitionCatalog": {"CatalogDone": "bool", "CatalogSucceeded": "bool"},
        "BP_PrioritySettings": {"PolicyKeysReady": "bool"},
        "BP_Logbook": {"SessionOnly": "bool", "ActiveWorkspace": "int"},
    }
    setters = {}
    for asset, fields in field_types.items():
        for field, kind in fields.items():
            method = asset + "_" + field
            graph = BP.add_function_graph(fixture, method)
            BP.add_object_function_param(graph, "Target", load(asset), True)
            if isinstance(kind, str):
                BP.add_function_param(graph, "Value", kind, True)
            else:
                BP.add_object_function_param(graph, "Value", kind, True)
            setters[method] = graph
    BP.compile_blueprint(fixture)
    with toolset_registry.tool_raising_exceptions():
        for asset, fields in field_types.items():
            for field in fields:
                method = asset + "_" + field
                class_id = asset.replace("_", "")
                BP.write_graph_dsl(setters[method], f'(fn {method} (Target Value) (Class|{class_id}|Set{field} :self Target :{field} Value))')
        BP.compile_blueprint(fixture, warnings_as_errors=True)
    inputs = unreal.new_object(fixture.generated_class())

    def put(obj, name, value):
        asset = str(obj.get_class().get_name()).removesuffix("_C")
        inputs.call_method(asset + "_" + name, args=(obj, value))
    notifications = {
        "BP_WorkerOptimizer": ("PreparePolicyKeys", "BeginTriggeredRun", "FailRun", "CompleteRun", "PublishTerminalReport", "AdvanceRun"),
        "BP_Logbook": ("RefreshView", "RetryStorage", "PrepareAppend"),
        "BP_SettingsModel": ("WriteSetting", "AdvanceFilter"),
    }
    dispatchers = {"BP_WorkerOptimizer": "OnControllerPresentationChanged", "BP_Logbook": "OnHistoryPresentationChanged",
                   "BP_SettingsModel": "OnSettingsPresentationChanged"}
    for asset, functions in notifications.items():
        blueprint = unreal.load_asset(root + asset)
        assert blueprint, asset
        assert dispatchers[asset] in [str(graph.get_name()) for graph in BP.list_event_dispatchers(blueprint)]
        for function in functions:
            nodes = BP.get_node_infos(BP.find_nodes(BP.get_graph(blueprint, function)))
            calls = [node for node in nodes if node.type_id.rsplit("|", 1)[-1].replace(" ", "") == "Call" + dispatchers[asset]]
            assert len(calls) == 1, (asset, function, [node.type_id for node in nodes])
    lifecycle = unreal.load_asset(root + "BP_MapLoad")
    pump_calls = {node.type_id.rsplit("|", 1)[-1] for node in BP.get_node_infos(BP.find_nodes(BP.get_graph(lifecycle, "PumpUI")))}
    assert not pump_calls & {"RefreshUI", "IsCapturing", "PollKey", "ToggleButton"}, "Manual UI stays event-driven without hotkey polling or icon hiding"

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    controller = actors.spawn_actor_from_class(load("BP_WorkerOptimizer"), unreal.Vector(0, 0, -100000))
    try:
        settings = unreal.new_object(load("BP_PrioritySettings"))
        catalog = unreal.new_object(load("BP_DefinitionCatalog"))
        put(controller, "Initialized", True)
        put(controller, "Settings", settings)
        put(controller, "PolicyCatalog", catalog)
        put(catalog, "CatalogDone", True)
        put(catalog, "CatalogSucceeded", True)
        put(settings, "PolicyKeysReady", False)
        assert controller.call_method("PreparePolicyKeys")
        assert settings.get_editor_property("PolicyKeysReady")
        assert controller.call_method("PreparePolicyKeys")
        assert not controller.get_editor_property("RunActive")
        assert not controller.get_editor_property("ReportPending")
        assert controller.get_editor_property("ReplanCount") == 0
        # Both locks reject before needing any bridge/context or capturing policy.
        for active, pending in ((True, False), (False, True), (True, True)):
            put(controller, "RunActive", active)
            put(controller, "ReportPending", pending)
            assert not controller.call_method("BeginTriggeredRun", args=("manual",))
            assert controller.get_editor_property("RunActive") == active
            assert controller.get_editor_property("ReportPending") == pending
            assert not settings.get_editor_property("PolicyFrozen")
    finally:
        actors.destroy_actor(controller)
    logbook = unreal.new_object(load("BP_Logbook"))
    put(logbook, "SessionOnly", True)
    put(logbook, "ActiveWorkspace", -1)
    assert not logbook.call_method("RefreshView")
    snapshots = ("PresentationInitialized", "PresentationReady", "PresentationRevision", "PresentationStatus")
    before = tuple(logbook.get_editor_property(name) for name in snapshots)
    assert not logbook.call_method("RefreshView")
    assert before == tuple(logbook.get_editor_property(name) for name in snapshots)
    assert before[0], before
    assert str(logbook.get_editor_property("PersistenceStatus")) == "session_only"
    unreal.log("WO_UI_NOTIFICATIONS_NATIVE_PASS")


if __name__ == "__main__":
    run()
    if "unreal" in sys.modules:
        run_native()
