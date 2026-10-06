"""Run actual snapshot diagnostics and the partial-success UI with native fixtures."""

import unreal


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
    put = lambda obj, key, value: obj.set_editor_property(key, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []

    def spawn(cls):
        result = actors.spawn_actor_from_class(cls, unreal.Vector(0, 0, -100000))
        spawned.append(result)
        return result

    controller, bridge = spawn(load("BP_WorkerOptimizer")), spawn(load("BP_ActionBridge"))
    assert bridge.call_method("InitializeBridge", args=(unreal.new_object(load("WBP_ActionContext")),))
    assert controller.call_method("Initialize", args=(controller, bridge))
    assert controller.get_editor_property("Settings").call_method("FinishPolicyKeys")
    snapshot = controller.get_editor_property("Snapshot")
    widget = None
    try:
        snapshot.call_method("ResetSnapshot")
        assert not snapshot.call_method("RecordCompatibilityIssue", args=(None,))
        building = spawn(native("GridActor"))
        put(building, "ID", 99001)
        put(building, "Health", 100)
        put(building, "isPlayerOwned", True)
        prefab = building.get_editor_property("PrefabInfo")
        assert prefab.import_text("(prefabKey=future_workplace)")
        put(building, "PrefabInfo", prefab)
        for slots, house, found in ((0, 0, True), (4, 1, True), (4, 0, False)):
            assert not snapshot.call_method("ObserveUnsupportedDefinition", args=(building, slots, house, found))
        assert not list(snapshot.get_editor_property("CompatibilityBuildings"))
        assert snapshot.call_method("ObserveUnsupportedDefinition", args=(building, 4, 0, True))
        assert snapshot.call_method("RecordCompatibilityIssue", args=(building,))
        assert list(snapshot.get_editor_property("CompatibilityBuildings")) == [building]
        messages = list(snapshot.get_editor_property("CompatibilityMessages"))
        assert len(messages) == 1 and "future_workplace" in messages[0] and "99001" in messages[0]
        assert "preserved" in messages[0]

        snapshot.call_method("ResetSnapshot")
        for owned, health in ((False, 100), (True, 0)):
            put(building, "isPlayerOwned", owned)
            put(building, "Health", health)
            assert not snapshot.call_method("RecordCompatibilityIssue", args=(building,))
        put(building, "isPlayerOwned", True)
        put(building, "Health", 100)
        component = building.call_method("AddComponentByClass", args=(native("Industry"), False, unreal.Transform(), False))
        workforce = component.get_editor_property("m_workers")
        assert workforce.import_text("(bDisabled=True,m_workerSlots=((bIsRequiredToRun=True)))")
        worker = spawn(native("Prototype_Agent"))
        slot = workforce.get_editor_property("m_workerSlots")[0]
        put(slot, "Agent", worker)
        put(workforce, "m_workerSlots", [slot])
        put(component, "m_workers", workforce)
        before = component.get_editor_property("m_workers").export_text()
        assert not snapshot.call_method("AddBuilding", args=(building,))
        assert not list(snapshot.get_editor_property("CompatibilityBuildings")), "Pause is not an incompatibility"
        assert worker in snapshot.get_editor_property("ProtectedWorkers")
        extra_workplace = building.call_method("AddComponentByClass", args=(native("Industry"), False, unreal.Transform(), False))
        assert extra_workplace
        assert not snapshot.call_method("AddBuilding", args=(building,))
        assert list(snapshot.get_editor_property("CompatibilityBuildings")) == [building]
        assert before == component.get_editor_property("m_workers").export_text()
        assert worker in snapshot.get_editor_property("ProtectedWorkers")

        snapshot.call_method("ResetSnapshot")
        employer = spawn(native("GridActor"))
        put(employer, "ID", 99002)
        put(employer, "Health", 100)
        put(employer, "isPlayerOwned", True)
        snapshot.call_method("FinishBuildings")
        assert not snapshot.call_method("AddWorker", args=(worker, employer))
        assert list(snapshot.get_editor_property("CompatibilityBuildings")) == [employer]
        assert worker in snapshot.get_editor_property("ProtectedWorkers")

        config = unreal.new_object(load("BP_HotkeyConfig"))
        config.call_method("ResetDefaults")
        factory = unreal.get_default_object(unreal.load_class(None, "/Script/UMG.WidgetBlueprintLibrary"))
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        widget = factory.call_method("Create", args=(world, load("WBP_WorkerOptimizer"), None))
        assert widget.call_method("InitializeUI", args=(controller, config))
        # UI observation boundary: no game assignment is dispatched by this test.
        controller.call_method("CompleteRun")
        assert widget.call_method("RefreshUI")
        action = widget.get_editor_property("ActionButton")
        # Intentional preservation is informational in the redesigned HUD.
        # The terminal report remains the source even after a fresh snapshot.
        tooltip = str(action.get_editor_property("tool_tip_text"))
        assert tooltip.startswith("Worker Optimizer: Completed"), tooltip
        assert "future_workplace" not in tooltip and "99002" not in tooltip
        assert widget.get_editor_property("ActionState") == 3
        icon = widget.get_editor_property("OutcomeIcon")
        assert icon.get_visibility() == unreal.SlateVisibility.HIT_TEST_INVISIBLE
        assert icon.get_editor_property("brush").get_editor_property("resource_object") == unreal.load_asset(root + "T_WorkerOptimizerStatusCompleted")
        completed_color = action.get_editor_property("background_color").export_text()
        snapshot.call_method("ResetSnapshot")
        assert not list(snapshot.get_editor_property("CompatibilityMessages"))
        assert widget.call_method("RefreshUI")
        assert str(action.get_editor_property("tool_tip_text")) == tooltip
        assert completed_color == action.get_editor_property("background_color").export_text()
        unreal.log("WO_COMPATIBILITY_TESTS_PASS: definition and employee evidence, no housing/pause/foreign warnings, deduplication, protected occupants, reset and partial-success UI; native definition/logging success remains shipping-only")
    finally:
        if widget:
            widget.call_method("ShutdownUI")
            widget.remove_from_parent()
        controller.call_method("Shutdown")
        for obj in reversed(spawned):
            actors.destroy_actor(obj)


run()
