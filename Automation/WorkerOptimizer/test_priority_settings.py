"""Exercise native option policy, type inheritance and stable configuration keys."""

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
import toolset_registry


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_PrioritySettings.BP_PrioritySettings_C")
    assert cls, "Production priority settings do not exist"
    assert "CapturePolicy" in {str(g.get_name()) for g in BP.list_graphs(unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_PrioritySettings"))}, "Run policy is still read live instead of captured"
    settings = unreal.new_object(cls)
    call = lambda name, *args: settings.call_method(name, args=args)
    assert not call("CapturePolicy", settings), "Unknown first-run keys cannot expose partial readiness"
    assert call("BeginPolicyKeys")
    assert call("AddPolicyKey", "fishery", "Food")
    assert call("FinishPolicyKeys")
    assert call("CapturePolicy", settings)
    assert not call("CapturePolicy", settings), "Active policy cannot be silently replaced"
    assert call("ReadPriority", None, "Food", "new_type") == 2
    assert call("ReleasePolicy")
    for priority in range(5):
        assert call("ParsePriority", str(priority), False) == (True, priority)
        assert call("ParsePriority", str(priority), True) == (True, priority)
        assert call("ResolvePriority", str(priority), "inherit") == priority
        for override in range(5):
            assert call("ResolvePriority", str(priority), str(override)) == override
    assert call("ParsePriority", "inherit", True) == (True, -1)
    assert not call("ParsePriority", "inherit", False)[0]
    for bad in ("", "-1", "5", "100", "2.0", "2x", "garbage", " 3"):
        assert not call("ParsePriority", bad, True)[0]
        assert call("ResolvePriority", bad, "inherit") == 2
        assert call("ResolvePriority", "4", bad) == 4
        assert call("ResolvePriority", bad, "0") == 0
    assert call("IsStrictValue", "Strict")
    assert not call("IsStrictValue", "Weighted")
    assert call("IsStrictValue", "future_unsupported_mode")
    category_key = call("CategoryOptionId", "food.production")
    type_key = call("TypeOptionId", "food.production")
    assert category_key == "WorkerOptimizer.category.food.production"
    assert type_key == "WorkerOptimizer.type.food.production"
    assert category_key != type_key, "Categories and types cannot overwrite one another"
    assert call("TypeOptionId", "future.building") == "WorkerOptimizer.type.future.building"
    assert call("CategoryLabelKey", "food_process") == "toolbar.food_process"
    assert call("ResolveLabel", "future.building", "missing.translation") == "future.building"
    assert not call("EnsureDefinitionOptions", None, "future.building", "food_process", "missing.translation")
    assert not call("RegisterGeneral", None)
    assert not call("RegisterCategory", None, "food", "Nahrung")
    assert not call("RegisterType", None, "future.building", "New Building")
    assert call("ReadPriority", None, "food", "future.building") == 2
    assert call("ReadStrictMode", None)
    assert str(call("ReadAutoMode", None)) == "off"
    for mode in ("off", "day_start", "minutes_5", "minutes_10", "minutes_15"):
        assert str(call("ParseAutoMode", mode)) == mode
        assert str(call("ParseAutoMode", "WorkerOptimizer.ui.auto." + mode)) == mode
    assert str(call("ParseAutoMode", "unsupported")) == "off"
    invalid_context = settings
    assert not call("EnsureDefinitionOptions", invalid_context, "future.building", "food_process", "missing.translation")
    assert not call("EnsureDefinitionOptions", invalid_context, "None", "food_process", "")
    assert not list(settings.get_editor_property("RegisteredCategories")), "Native failures must not populate the registration cache"
    assert not list(settings.get_editor_property("RegisteredTypes"))
    assert not call("RegisterGeneral", invalid_context)
    assert not call("RegisterCategory", invalid_context, "food", "Food")
    assert not call("RegisterType", invalid_context, "future.building", "New Building")
    assert call("ReadPriority", invalid_context, "food", "future.building") == 2
    assert call("ReadStrictMode", invalid_context)
    unreal.log("WO_PRIORITY_SETTINGS_TESTS_PASS: five levels, all type/category combinations, inheritance for new types, malformed stored values, distinct internal keys and strict/weighted parsing; native settings persistence not exercised")


run()


def policy_key_caps():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_PrioritySettings.BP_PrioritySettings_C")
    types = unreal.new_object(cls)
    assert types.call_method("BeginPolicyKeys")
    for index in range(10000):
        assert types.call_method("AddPolicyKey", args=("cap.type." + str(index), "Food"))
    assert types.call_method("AddPolicyKey", args=("cap.type.0", "Food")), "Existing type at the cap must remain usable"
    assert not types.call_method("AddPolicyKey", args=("cap.type.extra", "Food"))
    assert len(types.get_editor_property("KnownTypes")) == 10000
    categories = unreal.new_object(cls)
    assert categories.call_method("BeginPolicyKeys")
    for index in range(10000):
        assert categories.call_method("AddPolicyKey", args=("cap.type", "cap.category." + str(index)))
    assert categories.call_method("AddPolicyKey", args=("cap.type", "cap.category.0")), "Existing category at the cap must remain usable"
    assert categories.call_method("AddPolicyKey", args=("cap.type", "None"))
    assert not categories.call_method("AddPolicyKey", args=("cap.new_type", "cap.category.extra"))
    assert len(categories.get_editor_property("KnownCategories")) == 10000
    assert len(categories.get_editor_property("KnownTypes")) == 1, "Rejected category must not partially add a type"
    unreal.log("WO_POLICY_KEY_CAPS_TESTS_PASS: duplicate type/category reuse at 10000, new-key rejection, None-category reuse and no partial addition")


policy_key_caps()


def policy_input_boundary():
    # Only the native input boundary is substituted; CapturePolicy and all frozen
    # reads below are compiled production functions, not an independent policy.
    parent = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_PrioritySettings.BP_PrioritySettings_C")
    path = "/Game/WorkerOptimizerEditorTests/BP_PolicyInput"
    bp = BP.create("/Game/WorkerOptimizerEditorTests", "BP_PolicyInput", parent)
    try:
        for name in ("CategoryValue", "TypeValue", "ModeValue", "ReserveValue", "AutoValue"):
            BP.add_variable(bp, name, "string")
            BP.set_variable_instance_editable(bp, name, True)
        graph = BP.add_function_graph(bp, "ReadOption")
        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(graph, """(fn ReadOption (Context OptionId Fallback)
                (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.category.Food") (return (Variables|Default|GetCategoryValue)))
                (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.type.fishery") (return (Variables|Default|GetTypeValue)))
                (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.mode") (return (Variables|Default|GetModeValue)))
                (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.reserve") (return (Variables|Default|GetReserveValue)))
                (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.auto_assignment") (return (Variables|Default|GetAutoValue)))
                (return Fallback))""")
            BP.compile_blueprint(bp, warnings_as_errors=True)
            assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
        settings = unreal.new_object(bp.generated_class())
        call = lambda name, *args: settings.call_method(name, args=args)
        def values(category, type_value, mode, reserve):
            for key, value in zip(("CategoryValue", "TypeValue", "ModeValue", "ReserveValue"), (category, type_value, mode, reserve)):
                settings.set_editor_property(key, value)
        assert call("BeginPolicyKeys")
        assert call("AddPolicyKey", "fishery", "Food") and call("FinishPolicyKeys")
        values("4", "1", "Strict", "7")
        assert call("CapturePolicy", settings)
        settings.set_editor_property("AutoValue", "WorkerOptimizer.ui.auto.minutes_5")
        assert str(call("ReadAutoMode", settings)) == "minutes_5", "Auto mode remains live while policy is frozen"
        settings.set_editor_property("AutoValue", "WorkerOptimizer.ui.auto.off")
        assert str(call("ReadAutoMode", settings)) == "off"
        values("0", "3", "Weighted", "100")
        assert call("ReadPriority", settings, "Food", "fishery") == 1
        assert call("ReadPriority", settings, "Food", "new_type") == 4
        assert call("ReadStrictMode", settings) and call("ReadReserve", settings) == 7
        assert call("AddPolicyKey", "new_type", "Food")
        assert call("ReadPriority", settings, "Food", "new_type") == 4
        assert call("ReleasePolicy")
        assert call("ReadPriority", settings, "Food", "fishery") == 3
        assert not call("ReadStrictMode", settings) and call("ReadReserve", settings) == 100
        assert call("CapturePolicy", settings)
        assert call("ReadPriority", settings, "Food", "new_type") == 0
        assert call("ReadPriority", settings, "Food", "fishery") == 3
        assert call("ReleasePolicy")
        assert call("CapturePolicy", settings) and call("ReleasePolicy")
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        root = "/Game/Mods/WorkerOptimizer/"
        load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
        controller_path = "/Game/WorkerOptimizerEditorTests/BP_ControllerPolicyInput"
        controller_bp = BP.create("/Game/WorkerOptimizerEditorTests", "BP_ControllerPolicyInput", load("BP_WorkerOptimizer"))
        controller_graph = BP.add_function_graph(controller_bp, "InstallPolicyInput")
        BP.add_object_function_param(controller_graph, "InputSettings", parent, True)
        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(controller_graph, "(fn InstallPolicyInput (InputSettings) (Variables|Default|SetSettings InputSettings))")
            BP.compile_blueprint(controller_bp, warnings_as_errors=True)
            assert unreal.EditorAssetLibrary.save_loaded_asset(controller_bp)
        controller = actors.spawn_actor_from_class(controller_bp.generated_class(), unreal.Vector(0, 0, -100000))
        bridge = actors.spawn_actor_from_class(load("BP_ActionBridge"), unreal.Vector(0, 0, -100000))
        try:
            assert bridge.call_method("InitializeBridge", args=(unreal.new_object(load("WBP_ActionContext")),))
            assert controller.call_method("Initialize", args=(controller, bridge))
            # Substitute only the same mutable native-input boundary above.
            controller.call_method("InstallPolicyInput", args=(settings,))
            def finish_report():
                for _ in range(100):
                    if not controller.get_editor_property("ReportPending"):
                        return
                    controller.call_method("AdvanceRun", args=(1.0,))
                raise AssertionError("Early-cancel report exceeded its finite bound")
            values("4", "1", "Strict", "7")
            assert controller.call_method("BeginRun")
            values("0", "3", "Weighted", "100")
            assert call("ReadPriority", controller, "Food", "fishery") == 1, "Accepted run must freeze type before its first advance"
            assert call("ReadPriority", controller, "Food", "new_type") == 4, "Accepted run must freeze category before its first advance"
            assert call("ReadStrictMode", controller) and call("ReadReserve", controller) == 7
            scorer = controller.get_editor_property("Scorer")
            assert scorer.call_method("Configure", args=(25.0, -10.0, 20.0, 15.0, 10.0))
            assert controller.call_method("AcceptConfig", args=(True,))
            assert controller.get_editor_property("RequestedReserve") == 7
            assert call("ReadPriority", controller, "Food", "new_type") == 4
            assert controller.call_method("CancelRun") and not settings.get_editor_property("PolicyFrozen")
            finish_report()
            assert controller.call_method("BeginRun")
            assert call("ReadPriority", controller, "Food", "fishery") == 3
            assert call("ReadPriority", controller, "Food", "new_type") == 0
            assert not call("ReadStrictMode", controller) and call("ReadReserve", controller) == 100
            assert controller.call_method("CancelRun")
            finish_report()
            # A refused capture must not expose an accepted run or retain a lock.
            assert call("CapturePolicy", controller)
            assert not controller.call_method("BeginRun")
            assert not controller.get_editor_property("RunActive") and not settings.get_editor_property("PolicyFrozen")
            assert controller.call_method("BeginRun") and controller.call_method("CancelRun")
            unreal.log("WO_CONTROLLER_ADMISSION_POLICY_TESTS_PASS: category/type/mode/reserve frozen before first advance, next run recaptures and failed capture releases admission lock")
        finally:
            controller.call_method("Shutdown")
            actors.destroy_actor(bridge)
            actors.destroy_actor(controller)
            scorer = controller = bridge = actors = load = controller_graph = controller_bp = None
            unreal.SystemLibrary.collect_garbage()
            assert unreal.EditorAssetLibrary.delete_asset(controller_path)
        unreal.log("WO_POLICY_INPUT_BOUNDARY_TESTS_PASS: frozen category/type/mode/reserve, newly discovered type, release and recapture; native OptionManager integration not executed")
    finally:
        # Release Python wrappers before unloading the temporary child package.
        call = values = settings = graph = bp = parent = None
        unreal.SystemLibrary.collect_garbage()
        assert unreal.EditorAssetLibrary.delete_asset(path)


policy_input_boundary()
