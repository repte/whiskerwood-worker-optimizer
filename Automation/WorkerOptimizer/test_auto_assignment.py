"""Injected-clock checks against the compiled production scheduler."""
import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_AutoAssignment.BP_AutoAssignment_C")
    assert cls, "Production automatic assignment scheduler is missing"
    for mode, interval in (("minutes_5", 300), ("minutes_10", 600), ("minutes_15", 900)):
        scheduler = unreal.new_object(cls)
        call = lambda name, *args: scheduler.call_method(name, args=args)
        assert call("Configure", mode, 100.0, 2, 20)
        assert not call("Poll", 100 + interval - 0.01, False, True, False)
        assert call("Poll", 100 + interval, False, True, False)
        assert scheduler.get_editor_property("Pending")
        assert not call("Poll", 100 + 10 * interval, True, True, False)
        assert scheduler.get_editor_property("Pending"), "Paused deadlines coalesce to one pending request"
        assert call("Poll", 100 + 10 * interval, False, True, False)
        assert call("OnRunStarted", 100 + 10 * interval)
        assert not scheduler.get_editor_property("Pending")
        assert not call("Poll", 100 + 20 * interval, False, True, True)
        assert call("OnRunEnded", 100 + 20 * interval)
        assert not call("Poll", 100 + 21 * interval - 0.01, False, True, False)
        assert call("Poll", 100 + 21 * interval, False, True, False)
        assert call("Configure", "off", 100 + 21 * interval, 2, 20)
        assert not scheduler.get_editor_property("Pending")
        assert not call("Poll", 100 + 50 * interval, False, True, False)
        # A manual accepted start discards pending work and restarts after end.
        assert call("Configure", mode, 50000.0, 2, 20)
        assert call("Poll", 50000 + interval, False, False, False) is False
        assert scheduler.get_editor_property("Pending")
        assert call("OnRunStarted", 50000 + interval)
        assert call("OnRunEnded", 50010 + interval)
        assert not call("Poll", 50010 + 2 * interval - 0.01, False, True, False)
        assert call("Poll", 50010 + 2 * interval, False, True, False)
        # Off while running never cancels the run and suppresses later requests.
        assert call("OnRunStarted", 50010 + 2 * interval)
        assert call("Configure", "off", 50011 + 2 * interval, 2, 20)
        assert scheduler.get_editor_property("Running")
        assert call("OnRunEnded", 50012 + 2 * interval)
        assert not call("Poll", 90000.0, False, True, False)
        # Session reset/load and backward/invalid clocks cannot catch up offline.
        assert call("ResetSession") and not scheduler.get_editor_property("Pending")
        assert call("Configure", mode, 1_000_000_000.0, 5, 1)
        assert not call("Poll", 1_000_000_000 + interval - 0.01, False, True, False)
        assert call("Poll", 1_000_000_000 + interval, False, True, False)
        assert not call("Poll", 100.0, False, True, False)
        assert not scheduler.get_editor_property("Pending")
        assert not call("Poll", float("nan"), False, True, False)
        assert not call("Poll", float("inf"), False, True, False)
        assert call("Configure", mode, 100.0, 5, 1)
        assert not call("Poll", 100 + interval - 0.01, False, True, False)
    scheduler = unreal.new_object(cls)
    call = lambda name, *args: scheduler.call_method(name, args=args)
    assert call("Configure", "day_start", 0.0, 3, 10)
    assert not call("Poll", 0.0, False, True, False), "Loading the current day is not a daily event"
    assert not call("ObserveDay", 3, 10)
    assert call("ObserveDay", 3, 11)
    assert not call("ObserveDay", 3, 11)
    assert not call("Poll", 1.0, True, True, False)
    assert call("Poll", 1.0, False, True, False)
    assert call("OnRunStarted", 1.0)
    assert call("ObserveDay", 3, 12)
    assert not call("Poll", 2.0, False, True, True)
    assert call("OnRunEnded", 2.0)
    assert not scheduler.get_editor_property("Pending"), "Day changes during a run are consumed at terminal reset"
    assert not call("Poll", 2.0, False, True, False)
    assert not call("ObserveDay", 3, 12)
    assert call("ObserveDay", 4, 1)
    assert call("Poll", 3.0, False, True, False)
    assert call("Configure", "off", 3.0, 4, 1)
    assert not call("Poll", 4.0, False, True, False)
    assert call("ResetSession")
    assert call("Configure", "day_start", 10.0, 4, 1)
    assert not call("ObserveDay", 4, 1) and not call("Poll", 10.0, False, True, False)
    assert not call("Configure", "unsupported", 10.0, 4, 1)
    assert str(scheduler.get_editor_property("Mode")) == "off"
    unreal.log("WO_AUTO_ASSIGNMENT_TESTS_PASS: deadlines 300/600/900, pause coalescing, readiness/busy, manual/terminal reset, off while busy, day/load duplicates, rollover, invalid clocks and long-uptime precision")


def scheduling_clock_boundary():
    path = "/Game/Mods/WorkerOptimizer/BP_WorkerOptimizer"
    bp = unreal.load_asset(path)
    names = {str(graph.get_name()) for graph in BP.list_graphs(bp)}
    assert "ReadSchedulingClock" in names, "Production scheduling still uses the legacy runner clock"
    legacy = BP.get_graph(bp, "ReadClock")
    legacy_output = next(pin for node in BP.get_node_infos(BP.find_nodes(legacy)) for pin in node.input_pins if pin.name == "Now")
    unreal.log("WO_SCHEDULING_CLOCK_LEGACY_TYPE " + str(BP._resolve_pin(legacy_output.pin_id).get_pin_type_display_string()))
    for name in ("ReadSchedulingClock", "ComposeSchedulingClock"):
        graph = BP.get_graph(bp, name)
        outputs = [pin for node in BP.get_node_infos(BP.find_nodes(graph)) for pin in node.input_pins if pin.name == "NowSeconds"]
        assert len(outputs) == 1
        assert "double" in str(BP._resolve_pin(outputs[0].pin_id).get_pin_type_display_string()).lower(), "Generated scheduling output must actually be double precision"
    compose = BP.get_graph(bp, "ComposeSchedulingClock")
    conversions = [node for node in BP.get_node_infos(BP.find_nodes(compose)) if node.type_id == "Math|Conversions|ToFloat(Integer)"]
    assert len(conversions) == 1
    converted = next(pin for pin in conversions[0].output_pins if pin.name == "ReturnValue")
    assert "double" in str(BP._resolve_pin(converted.pin_id).get_pin_type_display_string()).lower(), "Integer conversion must produce double before addition"
    for name in ("FailRun", "CompleteRun", "BeginTriggeredRun"):
        source = BP.read_graph_dsl(BP.get_graph(bp, name))
        assert "ReadSchedulingClock" in source and "|ReadClock)" not in source
    lifecycle = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_MapLoad")
    assert "ReadSchedulingClock" in BP.read_graph_dsl(BP.get_graph(lifecycle, "PollAutomatic"))
    child_path = "/Game/WorkerOptimizerEditorTests/BP_SchedulingClockInput"
    child = BP.create("/Game/WorkerOptimizerEditorTests", "BP_SchedulingClockInput", bp.generated_class())
    actor = None
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    try:
        for name, kind in (("InputSeconds", "int"), ("InputFraction", "real")):
            BP.add_variable(child, name, kind)
            BP.set_variable_instance_editable(child, name, True)
        graph = BP.add_function_graph(child, "ReadClockParts")
        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(graph, "(fn ReadClockParts () (return (Variables|Default|GetInputSeconds) (Variables|Default|GetInputFraction)))")
            BP.compile_blueprint(child, warnings_as_errors=True)
            assert unreal.EditorAssetLibrary.save_loaded_asset(child)
        actor = actors.spawn_actor_from_class(child.generated_class(), unreal.Vector(0, 0, -100000))
        scheduler_class = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_AutoAssignment.BP_AutoAssignment_C")

        def clock(seconds, fraction):
            actor.set_editor_property("InputSeconds", seconds)
            actor.set_editor_property("InputFraction", fraction)
            return actor.call_method("ReadSchedulingClock")

        for mode, interval in (("minutes_5", 300), ("minutes_10", 600), ("minutes_15", 900)):
            scheduler = unreal.new_object(scheduler_class)
            call = lambda name, *args: scheduler.call_method(name, args=args)
            assert call("Configure", mode, clock(1_000_000_000, 0.0), 5, 1)
            before = clock(1_000_000_000 + interval - 1, 0.99)
            assert abs(before - (1_000_000_000 + interval - 0.01)) < 0.00001
            assert not call("Poll", before, False, True, False), "Actual scheduling clock must not round an early instant past its deadline"
            deadline = clock(1_000_000_000 + interval, 0.0)
            assert call("Poll", deadline, False, True, False)
            assert call("OnRunStarted", deadline)
            ended = clock(1_000_000_000 + interval + 123, 0.25)
            assert call("OnRunEnded", ended)
            assert abs(scheduler.get_editor_property("NextDeadline") - (ended + interval)) < 0.00001
        unreal.log("WO_SCHEDULING_CLOCK_TESTS_PASS: generated double outputs, production consumer wiring, real ReadClockParts boundary to scheduler at 1e9 seconds for 300/600/900 and terminal reset")
    finally:
        if actor:
            actors.destroy_actor(actor)
        actor = scheduler = call = clock = graph = child = actors = bp = lifecycle = scheduler_class = None
        unreal.SystemLibrary.collect_garbage()
        assert unreal.EditorAssetLibrary.delete_asset(child_path)


run()
scheduling_clock_boundary()
