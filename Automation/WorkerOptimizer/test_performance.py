"""Check compiled bounded metrics and precise elapsed-time arithmetic."""

import math

import unreal


def metrics():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_PerformanceMetrics.BP_PerformanceMetrics_C")
    assert cls, "Production bounded performance metrics interface does not exist"
    obj = unreal.new_object(cls)
    assert obj.call_method("ResetMetrics")
    return obj


def test_histogram_bounds():
    obj = metrics()
    sizes = {name: len(obj.get_editor_property(name)) for name in ("Histogram", "Counts", "Maxima")}
    for value, repeat in ((0.001, 95), (0.005, 4), (0.07, 1)):
        for _ in range(repeat):
            assert obj.call_method("RecordSample", args=(2, value))
    assert obj.get_editor_property("Counts")[2] == 100
    assert math.isclose(obj.call_method("PercentileUpperBound", args=(2, 95.0)), 0.001)
    assert math.isclose(obj.call_method("PercentileUpperBound", args=(2, 99.0)), 0.008)
    assert math.isclose(obj.get_editor_property("Maxima")[2], 0.07)
    assert obj.call_method("PercentileUpperBound", args=(2, 100.0)) >= 0.07
    for phase, value in ((-1, 0.1), (12, 0.1), (2, -0.001), (2, math.nan), (2, math.inf), (2, -math.inf)):
        assert not obj.call_method("RecordSample", args=(phase, value))
    assert obj.get_editor_property("Counts")[2] == 100, "Rejected values must not pollute percentiles"
    for _ in range(2000):
        assert obj.call_method("RecordSample", args=(11, 2.5))
    assert obj.call_method("PercentileUpperBound", args=(11, 99.0)) == 2.5, "Overflow bucket must use exact maximum"
    for name, size in sizes.items():
        assert len(obj.get_editor_property(name)) == size, "Collection memory must not grow with duration"
    assert obj.call_method("PercentileUpperBound", args=(0, 99.0)) == 0.0
    assert obj.call_method("PercentileUpperBound", args=(2, 101.0)) == -1.0


def test_reset_metrics():
    obj = metrics()
    assert obj.call_method("RecordSample", args=(4, 0.031))
    assert obj.call_method("ResetMetrics")
    assert not any(obj.get_editor_property("Counts"))
    assert not any(obj.get_editor_property("Histogram"))
    assert not any(obj.get_editor_property("Maxima"))
    assert obj.call_method("RecordSample", args=(4, 0.0001))
    assert math.isclose(obj.call_method("PercentileUpperBound", args=(4, 99.0)), 0.0001)


def test_acceptance_boundaries():
    obj = metrics()
    for gate in (0.0002, 0.002, 0.004, 0.008):
        assert obj.call_method("ResetMetrics")
        assert obj.call_method("RecordSample", args=(8, gate))
        assert math.isclose(obj.call_method("PercentileUpperBound", args=(8, 99.0)), gate)
        assert obj.call_method("RecordSample", args=(8, gate + 1e-9))
        assert obj.call_method("PercentileUpperBound", args=(8, 99.0)) > gate
        assert obj.get_editor_property("Maxima")[8] > gate


def test_long_uptime_elapsed():
    obj = metrics()
    assert math.isclose(obj.call_method("ElapsedSeconds", args=(1000000, 0.25, 1000000, 0.251)), 0.001, abs_tol=1e-10)
    assert math.isclose(obj.call_method("ElapsedSeconds", args=(1000000, 0.9995, 1000001, 0.0005)), 0.001, abs_tol=1e-10)


def test_diagnostics_opt_in():
    root = "/Game/Mods/WorkerOptimizer/"
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    cls = unreal.load_class(None, root + "BP_WorkerOptimizer.BP_WorkerOptimizer_C")
    actor = actors.spawn_actor_from_class(cls, unreal.Vector(0, 0, -100000))
    bridge_cls = unreal.load_class(None, root + "BP_ActionBridge.BP_ActionBridge_C")
    bridge = actors.spawn_actor_from_class(bridge_cls, unreal.Vector(0, 0, -100000))
    fixture_actors = []
    try:
        from editor_toolset.toolsets.blueprint import BlueprintTools as BP
        bp = unreal.load_asset(root + "BP_WorkerOptimizer")
        assert "DumpStaffingProbe" not in {str(graph.get_name()) for graph in BP.list_graphs(bp)}, "Release must remove inert diagnostic probe graphs"
        assert not actor.get_editor_property("MeasurePerformance"), "Development metrics must default off"
        assert not actor.call_method("FlushPerformanceSummary")
        view_cls = unreal.load_class(None, root + "WBP_ActionContext.WBP_ActionContext_C")
        assert bridge.call_method("InitializeBridge", args=(unreal.new_object(view_cls),))
        assert actor.call_method("Initialize", args=(actor, bridge))
        assert actor.get_editor_property("Settings").call_method("FinishPolicyKeys")
        obj = actor.get_editor_property("Metrics")
        assert obj
        def finish_report():
            for _ in range(100):
                if not actor.get_editor_property("ReportPending"):
                    return
                actor.call_method("AdvanceTerminalReport")
            raise AssertionError("Early failure report exceeded its finite bound")
        assert actor.call_method("BeginRun")
        actor.call_method("Pump")
        finish_report()
        assert not any(obj.get_editor_property("Counts")), "Disabled metrics must collect no samples"
        actor.set_editor_property("MeasurePerformance", True, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        assert actor.call_method("BeginRun")
        assert not actor.call_method("ResetPerformanceMetrics"), "Reset must not discard an active capture"
        assert not actor.call_method("FlushPerformanceSummary"), "Summary must not run inside an active capture"
        assert actor.get_editor_property("MeasurePerformance"), "Busy flush must preserve collection"
        actor.call_method("Pump")
        assert obj.get_editor_property("Counts")[0] == 1
        assert obj.get_editor_property("Counts")[8] == 1
        assert not actor.get_editor_property("RunSucceeded"), "Editor configuration failure remains explicit"
        finish_report()
        assert actor.call_method("ResetPerformanceMetrics")
        assert not any(obj.get_editor_property("Counts"))
        assert obj.call_method("BuildSummary"), "Aggregate output must be available without hot-path logging"
        assert obj.call_method("RecordSample", args=(8, 0.001))
        runner = actor.get_editor_property("Runner")
        native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
        worker = actors.spawn_actor_from_class(native("Prototype_Agent"), unreal.Vector(0, 0, -100000))
        building = actors.spawn_actor_from_class(native("GridActor"), unreal.Vector(0, 0, -100000))
        fixture_actors.extend((worker, building))
        put = lambda target, name, value: target.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        characteristics = worker.get_editor_property("m_characteristics")
        assert characteristics.import_text("(ID=99100)")
        put(worker, "m_characteristics", characteristics)
        for name, value in (("ID", 99101), ("isPlayerOwned", True), ("Health", 100)):
            put(building, name, value)
        component = building.call_method("AddComponentByClass", args=(native("Industry"), False, unreal.Transform(), False))
        workforce = component.get_editor_property("m_workers")
        assert workforce.import_text("(m_workerSlots=((bIsRequiredToRun=True)))")
        slots = list(workforce.get_editor_property("m_workerSlots"))
        put(slots[0], "Agent", worker)
        put(workforce, "m_workerSlots", slots)
        put(component, "m_workers", workforce)
        snapshot = actor.get_editor_property("Snapshot")
        snapshot.call_method("ResetSnapshot")
        assert snapshot.call_method("AddBuilding", args=(building,))
        snapshot.call_method("FinishBuildings")
        assert snapshot.call_method("AddWorker", args=(worker, building))
        started = runner.call_method("StartApplication", args=(snapshot, bridge, [0], [0], [0], [True], 10.0))
        assert started[-1] if isinstance(started, tuple) else started
        assert runner.call_method("AdvanceApplication", args=(10.0,))
        assert not runner.get_editor_property("ValidationActive") and not runner.get_editor_property("Waiting")
        assert runner.call_method("RecordDispatch", args=(True, 10.0)), "Native dispatch acceptance is an explicit editor observation"
        assert not actor.call_method("FlushPerformanceSummary")
        assert actor.get_editor_property("MeasurePerformance"), "Waiting flush must preserve collection"
        put(slots[0], "Agent", None)
        put(workforce, "m_workerSlots", slots)
        put(component, "m_workers", workforce)
        assert runner.call_method("ObserveAction", args=(None, 11.0))
        assert not runner.get_editor_property("Waiting")
        assert not actor.call_method("FlushPerformanceSummary"), "Native ModAPI summary output is unavailable in this editor fixture"
        assert not actor.get_editor_property("MeasurePerformance"), "Accepted idle flush must stop collection even when emission is unavailable"
        assert obj.get_editor_property("Counts")[8] == 1, "Stopping a capture must retain observations"
    finally:
        for fixture in reversed(fixture_actors):
            actors.destroy_actor(fixture)
        actors.destroy_actor(bridge)
        actors.destroy_actor(actor)


def test_lifecycle_collection():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []

    def spawn(name, owner=None):
        obj = actors.spawn_actor_from_class(load(name), unreal.Vector(0, 0, -100000))
        spawned.append(obj)
        if owner:
            obj.call_method("SetOwner", args=(owner,))
        return obj

    hook = spawn("BP_MapLoad")
    try:
        api = unreal.new_object(unreal.load_class(None, "/Script/SystemCore.ModAPI"))
        assert hook.call_method("AttachAPI", args=(api,))
        assert unreal.WorkerOptimizerTestSupport.broadcast_loading_finished(api)
        actor = spawn("BP_WorkerOptimizer", hook)
        bridge = spawn("BP_ActionBridge", hook)
        view = unreal.new_object(load("WBP_ActionContext"))
        assert hook.call_method("InstallSession", args=(actor, bridge, view))
        # Native catalog discovery is unavailable in this commandlet fixture.
        assert actor.get_editor_property("Settings").call_method("FinishPolicyKeys")
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        factory = unreal.get_default_object(unreal.load_class(None, "/Script/UMG.WidgetBlueprintLibrary"))
        widget = factory.call_method("Create", args=(world, load("WBP_WorkerOptimizer"), None))
        config = unreal.new_object(load("BP_HotkeyConfig"))
        config.call_method("ResetDefaults")
        assert hook.call_method("InstallUI", args=(widget, config))
        obj = actor.get_editor_property("Metrics")
        assert hook.call_method("PumpLifecycle")
        assert not any(obj.get_editor_property("Counts"))
        actor.set_editor_property("MeasurePerformance", True, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        assert hook.call_method("PumpLifecycle")
        assert hook.call_method("PumpLifecycle")
        assert obj.get_editor_property("Counts")[10] == 2
        assert obj.get_editor_property("Counts")[9] == 1, "First cadence observation has no preceding interval"
        assert actor.call_method("BeginRun")
        assert hook.call_method("PumpLifecycle")
        assert obj.get_editor_property("Counts")[11] == 1
        actor.set_editor_property("MeasurePerformance", False, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        assert hook.call_method("PumpLifecycle")
        assert not hook.get_editor_property("HasPerformancePrevious"), "Disabled spans must not appear as a giant frame interval"
        assert hook.call_method("ReleaseSession")
        assert not hook.get_editor_property("HasPerformancePrevious")
    finally:
        hook.call_method("Shutdown")
        for obj in reversed(spawned):
            if unreal.SystemLibrary.is_valid(obj):
                actors.destroy_actor(obj)


def test_step_work_bound():
    for name in ("BP_AssignmentSolver", "BP_StaffingPlanner", "BP_PlanSearch", "BP_ScoreMatrix"):
        cls = unreal.load_class(None, f"/Game/Mods/WorkerOptimizer/{name}.{name}_C")
        obj = unreal.new_object(cls)
        assert obj.get_editor_property("StepWorkLimit") == 64, name
        assert obj.get_editor_property("LastStepWork") == 0, name
    solver = unreal.new_object(unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_AssignmentSolver.BP_AssignmentSolver_C"))
    solver.set_editor_property("StepWorkLimit", 3)
    solver.call_method("Initialize", args=([1.0] * (15 * 20), 15, 20))
    for _ in range(20000):
        if solver.get_editor_property("Done"):
            break
        solver.call_method("Advance")
        assert 0 < solver.get_editor_property("LastStepWork") <= 3
    assert solver.get_editor_property("Done") and solver.get_editor_property("Succeeded")
    assert list(solver.get_editor_property("Assignment")) == list(range(15))
    planner = unreal.new_object(unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C"))
    planner.set_editor_property("StepWorkLimit", 1)
    planner.call_method("StartPlan", args=([1.0] * 300, [0] * 15, [True] + [False] * 14, [2], 20, True))
    assert planner.call_method("KeepUnassigned", args=(2, 20, [float(w) for w in range(20)]))[-1]
    states = set()
    rows, workers, buildings = 17, 20, 1  # Includes the two reserve rows.
    width = rows + workers
    bound = 100 + 10 * (rows + workers + buildings)
    bound += rows * (rows + 1) * (workers + 5) + buildings * (buildings + rows)
    bound += 6 * (2 * rows * workers + rows * (rows + 1) * (3 * width + 10) + 10 * (rows + workers))
    for _ in range(bound):
        if planner.get_editor_property("PlanDone"):
            break
        states.add(planner.get_editor_property("State"))
        planner.call_method("AdvancePlan")
        assert planner.get_editor_property("LastStepWork") == 1
    assert planner.get_editor_property("PlanDone") and planner.get_editor_property("PlanSucceeded")
    assert {10, 11, 13, 18, 21, 24, 22, 5, 8, 27}.issubset(states), states
    assert len(set(planner.get_editor_property("PlanAssignment"))) == 15


def test_cancel_during_initialization():
    load = lambda name: unreal.load_class(None, f"/Game/Mods/WorkerOptimizer/{name}.{name}_C")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    building = actors.spawn_actor_from_class(unreal.load_class(None, "/Script/ProjectArco.GridActor"), unreal.Vector(0, 0, -100000))
    try:
        for key, value in (("ID", 99200), ("isPlayerOwned", True), ("Health", 100)):
            building.set_editor_property(key, value)
        component = building.call_method("AddComponentByClass", args=(unreal.load_class(None, "/Script/ProjectArco.Industry"), False, unreal.Transform(), False))
        wf = component.get_editor_property("m_workers")
        assert wf.import_text("(m_workerSlots=((bIsRequiredToRun=True),()))")
        component.set_editor_property("m_workers", wf)
        before = wf.export_text()
        snapshot = unreal.new_object(load("BP_WorkforceSnapshot"))
        snapshot.call_method("ResetSnapshot")
        assert snapshot.call_method("AddBuilding", args=(building,))
        snapshot.call_method("FinishBuildings")
        for _ in range(10):
            if snapshot.get_editor_property("CaptureDone"):
                break
            snapshot.call_method("AdvanceCapture")
        layout = unreal.new_object(load("BP_ProblemLayout"))
        assert layout.call_method("BeginLayout", args=(snapshot,))
        for _ in range(100):
            if layout.get_editor_property("LayoutDone"):
                break
            layout.call_method("AdvanceLayout")
        assert layout.get_editor_property("LayoutSucceeded")
        matrix, planner, search = [unreal.new_object(load(n)) for n in ("BP_ScoreMatrix", "BP_StaffingPlanner", "BP_PlanSearch")]
        scorer, settings = [unreal.new_object(load(n)) for n in ("BP_JobScorer", "BP_PrioritySettings")]
        assert scorer.call_method("Configure", args=(25.0, -10.0, 20.0, 15.0, 10.0))
        for advances in (0, 1, "matrix"):
            assert search.call_method("BeginSearch", args=(layout, matrix, planner, scorer, settings, settings))
            assert not list(search.get_editor_property("Teachers")), "Setup must not synchronously initialize every building"
            if advances == "matrix":
                for _ in range(100):
                    if matrix.get_editor_property("MatrixActive"):
                        break
                    search.call_method("AdvanceSearch")
                assert matrix.get_editor_property("MatrixActive") and matrix.get_editor_property("SetupActive")
            else:
                for _ in range(advances):
                    search.call_method("AdvanceSearch")
            assert search.call_method("CancelSearch")
            assert search.get_editor_property("SearchDone") and not search.get_editor_property("SearchSucceeded")
            assert not list(search.get_editor_property("BestAssignment"))
            assert planner.get_editor_property("PlanDone") and not planner.get_editor_property("PlanSucceeded")
            assert matrix.get_editor_property("MatrixDone") and not matrix.get_editor_property("MatrixSucceeded")
            assert component.get_editor_property("m_workers").export_text() == before
    finally:
        actors.destroy_actor(building)


def test_incremental_matches_oracle():
    import runpy
    from pathlib import Path
    tests = runpy.run_path(str(Path(__file__).with_name("test_planner.py")))
    for scores in ([[9, 8, 1], [8, 1, 7], [2, 4, 3]], [[1, -1, 0], [0, 1, -1], [-1, 0, 1]]):
        buildings, minimum, priorities = [0, 0, 1], [True, False, True], [4, 2]
        for strict in (False, True):
            result = tests["plan"](scores, buildings, minimum, priorities, strict, step_limit=1)
            assert tests["policy_key"](result, scores, buildings, minimum, priorities, strict) == tests["oracle"](scores, buildings, minimum, priorities, strict)


if __name__ == "__main__":
    test_histogram_bounds()
    test_reset_metrics()
    test_acceptance_boundaries()
    test_long_uptime_elapsed()
    test_diagnostics_opt_in()
    test_lifecycle_collection()
    test_step_work_bound()
    test_cancel_during_initialization()
    test_incremental_matches_oracle()
    unreal.log("WO_PERFORMANCE_TESTS_PASS: bounded histogram, rejected samples, exact maxima, reset, long-uptime precision, default-off controller collection, primitive-step bounds, initialization cancellation and incremental exact oracles; editor behavior only")
