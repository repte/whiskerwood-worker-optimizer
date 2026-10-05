"""Exercise the real native UMG widget, not a parallel UI model."""

import unreal


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    cls = load("WBP_WorkerOptimizer")
    assert cls, "Production gameplay widget does not exist"
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    factory = unreal.get_default_object(unreal.load_class(None, "/Script/UMG.WidgetBlueprintLibrary"))
    widget = factory.call_method("Create", args=(world, cls, None))
    assert widget, "Native widget creation failed"
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    controller = actors.spawn_actor_from_class(load("BP_WorkerOptimizer"), unreal.Vector(0, 0, -100000))
    bridge = actors.spawn_actor_from_class(load("BP_ActionBridge"), unreal.Vector(0, 0, -100000))
    config = unreal.new_object(load("BP_HotkeyConfig"))
    config.call_method("ResetDefaults")
    extra_actors = []
    try:
        assert widget.get_editor_property("ActionButton")
        assert widget.get_editor_property("KeySelector")
        controls_slot = widget.get_editor_property("Controls").slot
        assert controls_slot.get_position().x >= 160, "Optimizer overlaps the game's left HUD toggles"
        assert not widget.call_method("ClickAction"), "Uninitialized widget must be inert"
        assert not widget.call_method("InitializeUI", args=(None, config))
        assert widget.call_method("InitializeUI", args=(controller, config))
        assert widget.call_method("InitializeUI", args=(controller, config))
        assert not config.get_editor_property("Dirty"), "Displaying the selected key must not edit preferences"
        assert not controller.get_editor_property("RunActive")
        assert widget.get_editor_property("ButtonVisible")
        assert not widget.get_editor_property("SettingsOpen")
        settings = widget.get_editor_property("SettingsButton")
        normal_settings = settings.get_editor_property("background_color").export_text()
        # Fail before native persistence: this exercises the real config error path
        # without touching a player preference file or fabricating a disk failure.
        assert config.call_method("ApplyChord", args=(config.call_method("ExportChord"),))
        assert not config.call_method("SaveSettings", args=("invalid-slot",))
        assert widget.call_method("RefreshUI")
        assert settings.get_editor_property("background_color").export_text() != normal_settings
        assert "not saved" in str(settings.get_editor_property("tool_tip_text")).lower()
        assert config.get_editor_property("Dirty")
        config.call_method("ResetDefaults")
        assert widget.call_method("RefreshUI")
        assert settings.get_editor_property("background_color").export_text() == normal_settings
        assert "not saved" not in str(settings.get_editor_property("tool_tip_text")).lower()
        assert not config.call_method("LoadSettings", args=("invalid-slot",))
        assert widget.call_method("RefreshUI")
        assert "default" in str(settings.get_editor_property("tool_tip_text")).lower()
        config.call_method("ResetDefaults")
        invalid_chord = unreal.InputChord()
        assert invalid_chord.import_text("(Key=Escape)")
        assert not widget.call_method("KeyChanged", args=(invalid_chord,))
        assert "invalid" in str(settings.get_editor_property("tool_tip_text")).lower()
        config.call_method("ResetDefaults")
        assert widget.call_method("RefreshUI")
        assert widget.call_method("ToggleButton")
        assert not widget.get_editor_property("ButtonVisible")
        assert widget.get_editor_property("Controls").get_visibility() == unreal.SlateVisibility.COLLAPSED
        assert not controller.get_editor_property("RunActive"), "Visibility is never an optimization trigger"
        assert widget.call_method("ToggleButton")
        assert widget.call_method("ToggleSettings")
        assert widget.get_editor_property("SettingsOpen")
        assert widget.get_editor_property("SettingsPanel").get_visibility() == unreal.SlateVisibility.VISIBLE
        assert widget.call_method("ToggleButton")
        assert not widget.get_editor_property("SettingsOpen"), "Hiding closes the key capture panel"
        assert widget.call_method("ToggleButton")
        assert not widget.call_method("ClickAction"), "Controller not initialized yet"
        view = unreal.new_object(load("WBP_ActionContext"))
        assert bridge.call_method("InitializeBridge", args=(view,))
        assert controller.call_method("Initialize", args=(controller, bridge))
        assert widget.call_method("RefreshUI")
        idle_color = widget.get_editor_property("ActionButton").get_editor_property("background_color").export_text()
        widget.get_editor_property("ActionButton").on_clicked.broadcast()
        assert controller.get_editor_property("RunActive"), "Only explicit click begins work"
        busy_color = widget.get_editor_property("ActionButton").get_editor_property("background_color").export_text()
        unreal.log("WO_WIDGET_COLORS " + idle_color + " -> " + busy_color)
        assert busy_color != idle_color, "Busy must be visible without hovering"
        widget.get_editor_property("ActionButton").on_clicked.broadcast()
        assert not controller.get_editor_property("RunActive"), "Second click cancels active work"
        assert str(controller.get_editor_property("FailureCode")) == "cancelled"
        # An already-dispatched action may still be pending after cancellation.
        native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
        put = lambda obj, name, value: obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        worker = actors.spawn_actor_from_class(native("Prototype_Agent"), unreal.Vector(0, 0, -100000))
        building = actors.spawn_actor_from_class(native("GridActor"), unreal.Vector(0, 0, -100000))
        extra_actors.extend((worker, building))
        ch = worker.get_editor_property("m_characteristics")
        assert ch.import_text("(ID=9600)")
        put(worker, "m_characteristics", ch)
        put(building, "ID", 9601)
        put(building, "isPlayerOwned", True)
        put(building, "Health", 100)
        component = building.call_method("AddComponentByClass", args=(native("Industry"), False, unreal.Transform(), False))
        wf = component.get_editor_property("m_workers")
        assert wf.import_text("(m_workerSlots=((bIsRequiredToRun=True)))")
        slots = list(wf.get_editor_property("m_workerSlots"))
        put(slots[0], "Agent", worker)
        put(wf, "m_workerSlots", slots)
        put(component, "m_workers", wf)
        snapshot = controller.get_editor_property("Snapshot")
        snapshot.call_method("ResetSnapshot")
        assert snapshot.call_method("AddBuilding", args=(building,))
        snapshot.call_method("FinishBuildings")
        assert snapshot.call_method("AddWorker", args=(worker, building))
        snapshot.call_method("AdvanceCapture")
        snapshot.call_method("AdvanceCapture")
        runner = controller.get_editor_property("Runner")
        assert runner.call_method("StartApplication", args=(snapshot, bridge, [0], [0], [0], [True], 10.0))[-1]
        assert runner.call_method("RecordDispatch", args=(True, 10.0))
        runner.call_method("FailApplication", args=("cancelled",))
        assert runner.get_editor_property("Waiting")
        assert widget.call_method("RefreshUI")
        assert not widget.get_editor_property("ActionButton").get_is_enabled(), "Pending native result must visibly block a new run"
        assert not widget.call_method("ClickAction")
        assert widget.call_method("ShutdownUI")
        assert not widget.call_method("ClickAction")
        assert not widget.call_method("ToggleButton")
    finally:
        widget.remove_from_parent()
        controller.call_method("Shutdown")
        actors.destroy_actor(controller)
        actors.destroy_actor(bridge)
        for obj in extra_actors:
            actors.destroy_actor(obj)
    unreal.log("WO_WIDGET_TESTS_PASS: native tree, guarded initialize, visibility-only toggle, settings collapse, explicit click start/cancel and shutdown")


run()
