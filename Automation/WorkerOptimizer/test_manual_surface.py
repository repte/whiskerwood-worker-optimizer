"""Verify the retained feature assets cannot alter the manual-only surface."""

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


ROOT = "/Game/Mods/WorkerOptimizer/"
load = lambda name: unreal.load_class(None, ROOT + name + "." + name + "_C")


def manual_widget():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    factory = unreal.get_default_object(unreal.load_class(None, "/Script/UMG.WidgetBlueprintLibrary"))
    widget = factory.call_method("Create", args=(world, load("WBP_WorkerOptimizer"), None))
    controller = actors.spawn_actor_from_class(load("BP_WorkerOptimizer"), unreal.Vector(0, 0, -100000))
    config = unreal.new_object(load("BP_HotkeyConfig"))
    config.call_method("ResetDefaults")
    try:
        assert widget.call_method("InitializeUI", args=(controller, config))
        for field in ("SettingsButton", "LogbookButton", "SettingsPanel", "KeySelector", "PanelScale"):
            assert widget.get_editor_property(field).get_visibility() == unreal.SlateVisibility.COLLAPSED, field
        panel = widget.get_editor_property("PanelHost")
        assert not panel.get_editor_property("Initialized"), "The dormant settings panel must not initialize"
        assert not widget.get_editor_property("SettingsModel")
        for function in ("ToggleSettings", "OpenLogbook", "InitializePanel", "ToggleButton", "IsCapturing"):
            assert not widget.call_method(function), function
        assert not widget.call_method("KeyChanged", args=(config.call_method("ExportChord"),))
        assert not config.get_editor_property("Dirty"), "Dormant controls must not mutate saved hotkeys"
        assert widget.get_editor_property("ButtonVisible")
        assert widget.get_editor_property("Controls").get_visibility() == unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE
        assert widget.get_editor_property("BusyText").get_visibility() == unreal.SlateVisibility.COLLAPSED
        assert not controller.get_editor_property("RunActive"), "Only the assignment button starts work"
    finally:
        widget.call_method("ShutdownUI")
        widget.remove_from_parent()
        actors.destroy_actor(controller)


def neutral_policy():
    path = "/Game/WorkerOptimizerEditorTests/BP_ManualPolicyInput"
    bp = BP.create("/Game/WorkerOptimizerEditorTests", "BP_ManualPolicyInput", load("BP_PrioritySettings"))
    for field in ("StoredPriority", "StoredMode", "StoredAuto", "StoredReserve"):
        BP.add_variable(bp, field, "string")
        BP.set_variable_instance_editable(bp, field, True)
    graph = BP.add_function_graph(bp, "ReadOption")
    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(graph, """(fn ReadOption (Context OptionId Fallback)
            (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.reserve") (return (Variables|Default|GetStoredReserve)))
            (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.mode") (return (Variables|Default|GetStoredMode)))
            (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.auto_assignment") (return (Variables|Default|GetStoredAuto)))
            (return (Variables|Default|GetStoredPriority)))""")
        BP.compile_blueprint(bp, warnings_as_errors=True)
    settings = unreal.new_object(bp.generated_class())
    try:
        for field, value in (("StoredPriority", "4"), ("StoredMode", "Weighted"), ("StoredAuto", "day_start"), ("StoredReserve", "7")):
            settings.set_editor_property(field, value)
        assert settings.call_method("BeginPolicyKeys")
        assert settings.call_method("AddPolicyKey", args=("fishery", "Food"))
        assert settings.call_method("FinishPolicyKeys")
        assert settings.call_method("ReadPriority", args=(settings, "Food", "fishery")) == 2
        assert settings.call_method("ReadStrictMode", args=(settings,))
        assert str(settings.call_method("ReadAutoMode", args=(settings,))) == "off"
        assert settings.call_method("CapturePolicy", args=(settings,))
        assert list(settings.get_editor_property("FrozenCategoryValues")) == [2]
        assert list(settings.get_editor_property("FrozenTypeValues")) == [2]
        assert settings.call_method("ReadReserve", args=(settings,)) == 7
        settings.set_editor_property("StoredReserve", "9")
        assert settings.call_method("ReadReserve", args=(settings,)) == 7, "Reserve stays frozen during a run"
        assert settings.call_method("ReleasePolicy")
        assert settings.call_method("ReadReserve", args=(settings,)) == 9
        assert settings.get_editor_property("StoredPriority") == "4"
        assert settings.get_editor_property("StoredMode") == "Weighted"
        assert settings.get_editor_property("StoredAuto") == "day_start"
    finally:
        settings = graph = bp = None
        unreal.SystemLibrary.collect_garbage()
        unreal.EditorAssetLibrary.delete_asset(path)


def dormant_routes():
    # Inspect executable production graphs: dormant definitions may remain, but
    # the active entry points must not reach option registration or scheduling.
    checks = {
        "BP_MapLoad": {
            "PollAutomatic": ("BeginTriggeredRun", "Poll"),
            "OnDayStart": ("ObserveDay",),
            "PumpUI": ("PollKey", "ToggleButton"),
            "AttachAPI": ("BindDay",),
        },
        "BP_PrioritySettings": {
            "RegisterGeneral": ("RegisterModOptions", "MigrateOption"),
            "RegisterCategory": ("RegisterModOptions", "MigrateOption"),
            "RegisterType": ("RegisterModOptions", "MigrateOption"),
        },
    }
    for asset, functions in checks.items():
        bp = unreal.load_asset(ROOT + asset)
        for function, forbidden in functions.items():
            types = [str(info.type_id).rsplit("|", 1)[-1] for info in BP.get_node_infos(BP.find_nodes(BP.get_graph(bp, function)))]
            for name in forbidden:
                assert name not in types, (asset, function, name)


failures = []
for check in (manual_widget, neutral_policy, dormant_routes):
    try:
        check()
    except AssertionError as failure:
        failures.append((check.__name__, str(failure)))
        unreal.log_error("WO_MANUAL_SURFACE_FAIL " + check.__name__ + ": " + str(failure))
assert not failures, failures
unreal.log("WO_MANUAL_SURFACE_TESTS_PASS: single icon, dormant controls/schedules/options, neutral policy and preserved builder reserve")
