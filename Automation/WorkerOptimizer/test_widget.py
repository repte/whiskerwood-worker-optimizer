"""Exercise the real native UMG widget, not a parallel UI model."""

import unreal
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    cls = load("WBP_WorkerOptimizer")
    assert cls, "Production gameplay widget does not exist"
    assert "UIWriteCount" in BP.list_variables(unreal.load_asset(root + "WBP_WorkerOptimizer")), "Unchanged UI refresh has no actual-setter instrumentation/cache"
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
        writes = widget.get_editor_property("UIWriteCount")
        for _ in range(100):
            assert widget.call_method("RefreshUI")
        assert widget.get_editor_property("UIWriteCount") == writes, "Unchanged refresh must not execute any UI setters"
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
        assert settings.get_visibility() == unreal.SlateVisibility.COLLAPSED
        assert config.get_editor_property("Dirty")
        config.call_method("ResetDefaults")
        assert widget.call_method("RefreshUI")
        assert settings.get_editor_property("background_color").export_text() == normal_settings
        assert "not saved" not in str(settings.get_editor_property("tool_tip_text")).lower()
        assert not config.call_method("LoadSettings", args=("invalid-slot",))
        assert widget.call_method("RefreshUI")
        assert settings.get_visibility() == unreal.SlateVisibility.COLLAPSED
        config.call_method("ResetDefaults")
        invalid_chord = unreal.InputChord()
        assert invalid_chord.import_text("(Key=Escape)")
        assert not widget.call_method("KeyChanged", args=(invalid_chord,))
        assert not config.get_editor_property("Dirty")
        config.call_method("ResetDefaults")
        assert widget.call_method("RefreshUI")
        assert not widget.call_method("ToggleButton")
        assert widget.get_editor_property("ButtonVisible")
        assert widget.get_editor_property("Controls").get_visibility() == unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE
        assert not controller.get_editor_property("RunActive"), "Visibility is never an optimization trigger"
        assert not widget.call_method("ToggleButton")
        # Explicit UI fixtures do not initialize or run the optimizer.
        from ui_test_fixture import inputs
        inputs.call_method("Controller", args=(controller,))
        assert not widget.call_method("ToggleSettings")
        assert not widget.get_editor_property("SettingsOpen")
        assert not widget.get_editor_property('GeometryWatching')
        assert widget.get_editor_property("PanelHost").get_visibility() == unreal.SlateVisibility.COLLAPSED
        assert not widget.get_editor_property("PanelHost").get_editor_property("Initialized")
        assert not widget.call_method("OpenLogbook")
        assert not widget.call_method("ToggleButton")
        assert not widget.get_editor_property("SettingsOpen"), "Hiding closes the key capture panel"
        assert not widget.get_editor_property('GeometryWatching'), 'Closed UI must not retain its geometry observer'
        writes=widget.get_editor_property('UIWriteCount')
        widget.call_method('OnGeometryPulse')
        assert widget.get_editor_property('UIWriteCount')==writes, 'A stale completion callback must be inert after closing'
        assert not widget.call_method("ToggleButton")
        assert not widget.call_method("ClickAction"), "Controller not initialized yet"
        view = unreal.new_object(load("WBP_ActionContext"))
        assert bridge.call_method("InitializeBridge", args=(view,))
        assert controller.call_method("Initialize", args=(controller, bridge))
        assert widget.call_method("RefreshUI")
        assert 'building list' in str(widget.get_editor_property('ActionButton').get_editor_property('tool_tip_text')).lower()
        writes = widget.get_editor_property("UIWriteCount")
        assert controller.get_editor_property("Settings").call_method("FinishPolicyKeys")
        assert widget.call_method("RefreshUI")
        assert writes < widget.get_editor_property("UIWriteCount") <= writes + 3, "Readiness updates only the enabled state and its presentation"
        assert widget.get_editor_property('ActionButton').get_is_enabled()
        assert 'building list' not in str(widget.get_editor_property('ActionButton').get_editor_property('tool_tip_text')).lower()
        ready_writes=widget.get_editor_property('UIWriteCount')
        assert widget.call_method('RefreshUI')
        assert widget.get_editor_property('UIWriteCount')==ready_writes, 'Unchanged ready state must not repaint'
        idle_color = widget.get_editor_property("ActionButton").get_editor_property("background_color").export_text()
        widget.get_editor_property("ActionButton").on_clicked.broadcast()
        assert controller.get_editor_property("RunActive"), "Only explicit click begins work"
        busy_color = widget.get_editor_property("ActionButton").get_editor_property("background_color").export_text()
        unreal.log("WO_WIDGET_COLORS " + idle_color + " -> " + busy_color)
        assert widget.get_editor_property('ActionButtonIcon').get_visibility() == unreal.SlateVisibility.HIDDEN
        assert widget.get_editor_property('BusyText').get_visibility() == unreal.SlateVisibility.COLLAPSED, 'Manual mode keeps feedback within the assignment icon'
        assert not widget.get_editor_property("ActionButton").get_is_enabled(), "Active manual assignment must disable the assignment icon"
        assert widget.get_editor_property("BusyIndicator").get_visibility() == unreal.SlateVisibility.HIT_TEST_INVISIBLE
        assert "cancel" not in str(widget.get_editor_property("ActionButton").get_editor_property("tool_tip_text")).lower()
        assert not widget.call_method("ClickAction"), "Direct clicks must not cancel or enqueue another run"
        widget.get_editor_property("ActionButton").on_clicked.broadcast()
        assert controller.get_editor_property("RunActive"), "Repeated button events must leave active work untouched"
        assert str(controller.get_editor_property("FailureCode")) != "cancelled"
        assert not widget.call_method("ToggleSettings"), "Settings access remains dormant"
        assert not widget.call_method("OpenLogbook"), "History access remains dormant"
        assert not widget.call_method("ToggleButton")
        assert controller.get_editor_property("RunActive"), "Hide/show must not affect active work"
        # Internal lifecycle cancellation remains available; there is no user cancel route.
        assert controller.call_method("CancelRun")
        # Automatic admission must use the same HUD lock, even without a HUD click.
        auto_controller = actors.spawn_actor_from_class(load("BP_WorkerOptimizer"), unreal.Vector(0, 0, -100000))
        extra_actors.append(auto_controller)
        auto_widget = factory.call_method("Create", args=(world, cls, None))
        try:
            assert auto_controller.call_method("Initialize", args=(auto_controller, bridge))
            assert auto_controller.get_editor_property("Settings").call_method("FinishPolicyKeys")
            assert auto_widget.call_method("InitializeUI", args=(auto_controller, config))
            assert auto_controller.call_method("BeginTriggeredRun", args=("minutes_5",))
            assert not auto_widget.get_editor_property('ActionButton').get_is_enabled(), 'Status delegate must update automatic admission without polling'
            assert not auto_widget.get_editor_property("ActionButton").get_is_enabled(), "Automatic assignment must disable the same icon"
            assert auto_widget.get_editor_property("BusyIndicator").get_visibility() == unreal.SlateVisibility.HIT_TEST_INVISIBLE
            assert not auto_widget.call_method("ClickAction")
            auto_widget.get_editor_property("ActionButton").on_clicked.broadcast()
            assert auto_controller.get_editor_property("RunActive")
            assert str(auto_controller.get_editor_property("RunTrigger")) == "minutes_5"
        finally:
            auto_widget.call_method('ShutdownUI')
            auto_widget.remove_from_parent()
            auto_controller.call_method("Shutdown")
        # A returned native failure must release admission once its report finishes.
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
        def finish_report():
            for _ in range(100):
                if not controller.get_editor_property("ReportPending"):
                    return
                controller.call_method("AdvanceTerminalReport")
            raise AssertionError("Widget fixture report did not finish")

        finish_report()
        assert controller.call_method("BeginRun")
        snapshot = controller.get_editor_property("Snapshot")
        snapshot.call_method("ResetSnapshot")
        assert snapshot.call_method("AddBuilding", args=(building,))
        snapshot.call_method("FinishBuildings")
        assert snapshot.call_method("AddWorker", args=(worker, building))
        snapshot.call_method("AdvanceCapture")
        snapshot.call_method("AdvanceCapture")
        runner = controller.get_editor_property("Runner")
        assert runner.call_method("StartApplication", args=(snapshot, bridge, [0], [0], [0], [True], 10.0))[-1]
        assert runner.call_method("AdvanceApplication", args=(10.0,))
        assert not runner.get_editor_property("ValidationActive") and not runner.get_editor_property("Waiting")
        assert runner.call_method("RecordDispatch", args=(True, 10.0))
        assert widget.call_method("RefreshUI")
        assert widget.get_editor_property("BusyIndicator").get_visibility() == unreal.SlateVisibility.HIT_TEST_INVISIBLE
        assert not widget.get_editor_property("ActionButton").get_is_enabled(), "Active native confirmation must remain busy and disabled"
        assert not runner.call_method("ObserveAction", args=(building, 21.0))
        assert str(runner.get_editor_property("FailureCode")) == "action_timeout"
        assert not controller.call_method("FailRun", args=("action_timeout",))
        assert controller.get_editor_property("RunDone") and not controller.get_editor_property("RunActive")
        assert not runner.get_editor_property("Waiting")
        finish_report()
        assert not controller.get_editor_property("ReportPending")
        assert widget.call_method("RefreshUI")
        assert widget.get_editor_property("BusyIndicator").get_visibility() == unreal.SlateVisibility.COLLAPSED, "A completed failure must replace the spinner"
        assert widget.get_editor_property("BusyText").get_visibility() == unreal.SlateVisibility.COLLAPSED
        assert widget.get_editor_property("ActionButtonIcon").get_visibility() == unreal.SlateVisibility.HIT_TEST_INVISIBLE
        outcome = widget.get_editor_property("OutcomeIcon")
        assert outcome.get_visibility() == unreal.SlateVisibility.HIT_TEST_INVISIBLE
        assert outcome.get_editor_property("brush").get_editor_property("resource_object") == unreal.load_asset(root + "T_WorkerOptimizerStatusError")
        expected_failure = widget.call_method("UIString", args=("failed",))
        actual_tooltip = str(widget.get_editor_property("ActionButton").get_editor_property("tool_tip_text"))
        assert actual_tooltip == expected_failure, ("Timeout must use the existing localized failure message", actual_tooltip, expected_failure)
        assert widget.get_editor_property("ActionButton").get_is_enabled(), "A returned native failure must not permanently block a new run"
        assert not controller.get_editor_property("RunActive")
        writes = widget.get_editor_property("UIWriteCount")
        assert widget.call_method("RefreshUI")
        assert widget.get_editor_property("UIWriteCount") == writes, "Stable terminal failure must not repaint"
        put(slots[0], "Agent", None)
        put(wf, "m_workerSlots", slots)
        put(component, "m_workers", wf)
        assert not runner.call_method("ObserveAction", args=(None, 22.0))
        assert runner.get_editor_property("AppliedCount") == 0, "Unrelated later changes are not late success"
        assert not runner.get_editor_property("Waiting")
        # Isolate the report-only admission gate with transient native UI inputs.
        report_fixture = BP.create("/Game/WorkerOptimizerEditorTests", "BP_WidgetReportInputs", unreal.Object.static_class())
        report_graph = BP.add_function_graph(report_fixture, "SetPending")
        BP.add_object_function_param(report_graph, "Controller", load("BP_WorkerOptimizer"), True)
        BP.add_function_param(report_graph, "Pending", "bool", True)
        BP.compile_blueprint(report_fixture)
        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(report_graph, '(fn SetPending (Controller Pending) (Class|BPWorkerOptimizer|SetReportPending :self Controller :ReportPending Pending))')
            BP.compile_blueprint(report_fixture, warnings_as_errors=True)
        report_inputs = unreal.new_object(report_fixture.generated_class())
        report_inputs.call_method("SetPending", args=(controller, True))
        assert widget.call_method("RefreshUI")
        assert widget.get_editor_property("BusyIndicator").get_visibility() == unreal.SlateVisibility.COLLAPSED, "Report completion must not restart a failed run's spinner"
        assert not widget.get_editor_property("ActionButton").get_is_enabled(), "Report completion must still block a new run"
        assert not widget.call_method("ClickAction")
        report_inputs.call_method("SetPending", args=(controller, False))
        assert widget.call_method("RefreshUI")
        assert widget.get_editor_property("ActionButton").get_is_enabled(), "Completed report and native confirmation must re-enable assignment"
        assert widget.get_editor_property("BusyIndicator").get_visibility() == unreal.SlateVisibility.COLLAPSED
        assert str(widget.get_editor_property("ActionButton").get_editor_property("tool_tip_text")) == widget.call_method("UIString", args=("failed",))
        assert widget.call_method("ClickAction") and controller.get_editor_property("RunActive"), "The same icon must start a fresh manual request after failure"
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
    unreal.log("WO_WIDGET_TESTS_PASS: single assignment icon, dormant feature access, guarded initialization, busy lock, terminal timeout/late confirmation and shutdown")


run()
