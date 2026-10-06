"""Compiled report behavior, with a mutable native-workplace input boundary."""

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType


def put(obj, name, value):
    obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def test_finalize_once(report):
    assert not report.call_method("BeginFinish", args=("failed", "replacement", None, None, None))
    frozen = report.get_editor_property("Outcome")
    assert not report.call_method("AdvanceReport")
    assert report.get_editor_property("Outcome") == frozen


def test_early_cancel_unknown_counts(report):
    assert not report.get_editor_property("CountsKnown")
    assert report.get_editor_property("ConfirmedMinimumCrews") == -1
    assert report.get_editor_property("FreeEligibleResidents") == -1
    assert report.get_editor_property("ConfirmedChanges") == 0


def test_partial_failure_keeps_confirmed_changes(report):
    assert report.get_editor_property("ConfirmedChanges") == 1
    assert report.get_editor_property("ConfirmedFires") == 1 and report.get_editor_property("ConfirmedHires") == 0
    assert str(report.get_editor_property("Outcome")) == "failed"
    assert str(report.get_editor_property("Failure")) == "action_rejected"


def test_grouped_qualified_worker_shortage(report):
    reasons = [str(v) for v in report.get_editor_property("GroupReasons")]
    assert "eligible_worker_competition" in reasons and "no_eligible_candidate" not in reasons, reasons
    group = reasons.index("eligible_worker_competition")
    assert report.get_editor_property("GroupCounts")[group] == 2
    return group


def test_final_observation_differs_from_plan(report):
    assert report.get_editor_property("ConfirmedMinimumCrews") == -1, "Changed evidence must not masquerade as a complete observed count"
    assert "world_changed" in [str(v) for v in report.get_editor_property("GroupReasons")]
    assert not report.get_editor_property("CountsKnown")


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    cls = load("BP_RunReport")
    assert cls, "Production BP_RunReport is missing"
    report_bp = unreal.load_asset(root + "BP_RunReport")
    expected_inputs = {"BeginReport": {"RunId", "Trigger", "SaveIdentity", "StartedAt", "Reserve"},
                       "BeginFinish": {"Outcome", "Failure", "Snapshot", "Layout", "Runner"}}
    for function, names in expected_inputs.items():
        nodes = BP.get_node_infos(BP.find_nodes(BP.get_graph(report_bp, function)))
        entry_names = {pin.name for node in nodes if "FunctionEntry" in str(node.node.get_class().get_name()) for pin in node.output_pins}
        assert names <= entry_names, (function, entry_names)
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    fixture = None
    report = None
    try:
        fixture = BP.create(root.rstrip("/"), "BP_TestReportInputs", cls)
        BP.add_object_variable(fixture, "InputWorkers", native("Prototype_Agent"), container_type=ContainerType.ARRAY)
        BP.add_object_variable(fixture, "InputPlaces", native("GridActor"), container_type=ContainerType.ARRAY)
        BP.add_variable(fixture, "InputsKnown", "bool")
        for name in ("InputWorkers", "InputPlaces", "InputsKnown"):
            BP.set_variable_instance_editable(fixture, name, True)
        graph = BP.add_function_graph(fixture, "ReadReportedWorkplace")
        BP.write_graph_dsl(graph, """(fn ReadReportedWorkplace (Worker)
          (bind i (Utilities|Array|FindItem (Variables|Default|GetInputWorkers) Worker))
          (if (or (< i 0) (not (Variables|Default|GetInputsKnown))) (return false))
          (return true (Utilities|Array|Get(acopy) :Array (Variables|Default|GetInputPlaces) :\"Dimension 1\" i)))""")
        BP.compile_blueprint(fixture, warnings_as_errors=True)

        def spawn(kind):
            actor = actors.spawn_actor_from_class(native(kind), unreal.Vector(0, 0, -100000))
            spawned.append(actor)
            return actor

        def worker(number, education="None"):
            actor = spawn("Prototype_Agent")
            ch = actor.get_editor_property("m_characteristics")
            assert ch.import_text(f"(ID={number},education={education})")
            put(actor, "m_characteristics", ch)
            return actor

        def building(number, slots_text, kind="fixture", paused=False):
            actor = spawn("GridActor")
            for key, value in (("ID", number), ("isPlayerOwned", True), ("Health", 100)):
                put(actor, key, value)
            info = actor.get_editor_property("prefabInfo")
            put(info, "prefabKey", kind)
            put(actor, "prefabInfo", info)
            comp = actor.call_method("AddComponentByClass", args=(native("Industry"), False, unreal.Transform(), False))
            wf = comp.get_editor_property("m_workers")
            assert wf.import_text("(m_workerSlots=(" + slots_text + "))")
            put(wf, "bDisabled", paused)
            put(comp, "m_workers", wf)
            return actor, comp

        def occupy(pair, index, person):
            wf = pair[1].get_editor_property("m_workers")
            slots = list(wf.get_editor_property("m_workerSlots"))
            put(slots[index], "Agent", person)
            put(wf, "m_workerSlots", slots)
            put(pair[1], "m_workers", wf)

        def capture(pairs, people, places):
            snapshot = unreal.new_object(load("BP_WorkforceSnapshot"))
            snapshot.call_method("ResetSnapshot")
            for pair in pairs:
                snapshot.call_method("AddBuilding", args=(pair[0],))
            snapshot.call_method("FinishBuildings")
            for person, place in zip(people, places):
                assert snapshot.call_method("AddWorker", args=(person, place))
            layout = unreal.new_object(load("BP_ProblemLayout"))
            assert layout.call_method("BeginLayout", args=(snapshot,))
            for _ in range(2000):
                if layout.get_editor_property("LayoutDone"):
                    break
                layout.call_method("AdvanceLayout")
            assert layout.get_editor_property("LayoutSucceeded")
            return snapshot, layout

        def begin(people=(), places=(), reserve=0):
            obj = unreal.new_object(fixture.generated_class())
            put(obj, "InputWorkers", list(people))
            put(obj, "InputPlaces", list(places))
            put(obj, "InputsKnown", True)
            assert obj.get_editor_property("StepWorkLimit") == 1
            assert obj.call_method("BeginReport", args=("test-run", "manual", "test-save", unreal.DateTime(), reserve))
            assert not obj.call_method("BeginReport", args=("replacement", "manual", "", unreal.DateTime(), 0))
            return obj

        def finish(obj, snapshot, layout, runner=None, outcome="completed", failure="None"):
            assert obj.call_method("BeginFinish", args=(outcome, failure, snapshot, layout, runner))
            assert not obj.call_method("BeginFinish", args=("failed", "replacement", snapshot, layout, runner))
            for _ in range(10000):
                if obj.get_editor_property("ReportDone"):
                    return
                assert obj.call_method("AdvanceReport")
                assert obj.get_editor_property("LastStepWork") <= 1
            raise AssertionError("Report exceeded finite fixture work bound")

        # test_finalize_once / test_early_cancel_unknown_counts
        report = begin()
        finish(report, None, None, outcome="cancelled", failure="cancelled")
        test_early_cancel_unknown_counts(report)
        test_finalize_once(report)

        # test_grouped_qualified_worker_shortage: one qualified resident occupied
        # elsewhere is competition, not evidence of zero qualified residents.
        apprentice = worker(9100, "Apprentice")
        occupied = building(9200, "(bIsRequiredToRun=True,educationRequirement=Apprentice)", "schoolwork")
        shortages = [building(9201 + i, "(bIsRequiredToRun=True,educationRequirement=Apprentice)", "schoolwork") for i in range(2)]
        occupy(occupied, 0, apprentice)
        snapshot, layout = capture([occupied] + shortages, [apprentice], [occupied[0]])
        report = begin([apprentice], [occupied[0]], reserve=1)
        finish(report, snapshot, layout)
        group = test_grouped_qualified_worker_shortage(report)
        assert report.call_method("GetAffectedPage", args=(group, 0, 1)) == [9201]
        assert report.call_method("GetAffectedPage", args=(group, 1, 1)) == [9202]
        assert not report.call_method("GetAffectedPage", args=(group, 2147483647, 50))
        assert report.get_editor_property("ConfirmedMinimumCrews") == 1
        assert report.get_editor_property("FreeEligibleResidents") == 0
        assert not report.get_editor_property("ReserveSatisfied")
        occupy(occupied, 0, None)
        free_snapshot, free_layout = capture(shortages, [apprentice], [None])
        report = begin([apprentice], [None], reserve=0)
        finish(report, free_snapshot, free_layout)
        free_reasons = [str(v) for v in report.get_editor_property("GroupReasons")]
        assert "unfilled_crew" in free_reasons and "eligible_worker_competition" not in free_reasons, "An observed free eligible resident with reserve zero is not competition"
        occupy(occupied, 0, apprentice)
        free_apprentice = worker(9101, "Apprentice")
        order_groups = []
        for people, places in (([apprentice, free_apprentice], [occupied[0], None]),
                               ([free_apprentice, apprentice], [None, occupied[0]])):
            order_snapshot, order_layout = capture([occupied] + shortages, people, places)
            report = begin(people, places, reserve=0)
            finish(report, order_snapshot, order_layout, outcome="failed", failure="action_rejected")
            order_reasons = [str(v) for v in report.get_editor_property("GroupReasons")]
            assert "unfilled_crew" in order_reasons and "eligible_worker_competition" not in order_reasons, "Employed/free eligible worker ordering must not change the factual shortage reason"
            group = order_reasons.index("unfilled_crew")
            assert report.get_editor_property("GroupCounts")[group] == 2
            assert list(report.call_method("GetAffectedPage", args=(group, 0, 50))) == [9201, 9202]
            order_groups.append((order_reasons, list(report.get_editor_property("GroupCounts")),
                                 list(report.get_editor_property("AffectedBuildingIds"))))
        assert order_groups[0] == order_groups[1], "Identical observed towns must retain identical grouped reasons/counts/IDs"
        report = begin([apprentice], [occupied[0]])
        put(report, "InputsKnown", False)
        finish(report, snapshot, layout)
        unknown_reasons = [str(v) for v in report.get_editor_property("GroupReasons")]
        assert "eligibility_unknown" in unknown_reasons and "no_eligible_candidate" not in unknown_reasons

        # test_final_observation_differs_from_plan / flexible real occupancy.
        flex = building(9210, "(),()", "flex")
        occupy(flex, 1, apprentice)
        snapshot, layout = capture([flex], [apprentice], [flex[0]])
        report = begin([apprentice], [flex[0]])
        finish(report, snapshot, layout)
        assert report.get_editor_property("ConfirmedMinimumCrews") == 1
        occupy(flex, 1, None)  # Native world changed after the completed plan.
        report = begin([apprentice], [None])
        finish(report, snapshot, layout)
        test_final_observation_differs_from_plan(report)

        occupy(flex, 1, apprentice)
        protected_snapshot, protected_layout = capture([flex], [], [])
        report = begin()
        finish(report, protected_snapshot, protected_layout)
        assert report.get_editor_property("ConfirmedMinimumCrews") == 1, "A protected real actor column is an observed occupant, not a local empty column"

        # Unknown observation must not silently become free-resident evidence.
        report = begin([apprentice], [None])
        put(report, "InputsKnown", False)
        finish(report, snapshot, layout)
        assert not report.get_editor_property("CountsKnown")
        assert report.get_editor_property("FreeEligibleResidents") == -1

        # test_partial_failure_keeps_confirmed_changes: actual runner confirmation.
        occupy(flex, 1, apprentice)
        snapshot, layout = capture([flex], [apprentice], [flex[0]])
        runner = unreal.new_object(load("BP_ApplicationRunner"))
        bridge = actors.spawn_actor_from_class(load("BP_ActionBridge"), unreal.Vector(0, 0, -100000))
        spawned.append(bridge)
        assert bridge.call_method("InitializeBridge", args=(unreal.new_object(load("WBP_ActionContext")),))
        assert runner.call_method("StartApplication", args=(snapshot, bridge, [0, 0], [1, 1], [0, 0], [True, False], 10.0))[-1]
        assert runner.call_method("AdvanceApplication", args=(10.0,))
        assert runner.call_method("RecordDispatch", args=(True, 10.0))
        occupy(flex, 1, None)
        assert runner.call_method("ObserveAction", args=(None, 11.0))
        runner.call_method("FailApplication", args=("action_rejected",))
        report = begin([apprentice], [None])
        finish(report, snapshot, layout, runner, "failed", "action_rejected")
        test_partial_failure_keeps_confirmed_changes(report)
        assert not report.call_method("CloseUnavailable", args=("cancelled", "cancelled", runner)), "Completed records cannot be overwritten by teardown"
        report = begin([apprentice], [None])
        assert report.call_method("CloseUnavailable", args=("cancelled", "cancelled", runner))
        assert report.get_editor_property("ConfirmedChanges") == 1 and report.get_editor_property("ConfirmedFires") == 1
        assert report.get_editor_property("ReportDone") and not report.get_editor_property("ConfirmationWindowKnown")
        assert not report.get_editor_property("CountsKnown")
        assert runner.call_method("ResetConfirmedActions")
        assert runner.get_editor_property("AppliedCount") == 0

        # Paused/unsupported records are separate from active supported crews.
        paused = building(9230, "(bIsRequiredToRun=True)", "pausedwork", True)
        snapshot, layout = capture([paused], [], [])
        report = begin()
        unsupported = spawn("GridActor")
        for key, value in (("ID", 9231), ("isPlayerOwned", True), ("Health", 100)):
            put(unsupported, key, value)
        assert snapshot.call_method("ObserveUnsupportedDefinition", args=(unsupported, 1, 0, True))
        finish(report, snapshot, layout)
        assert report.get_editor_property("ActiveSupportedBuildings") == 0
        assert report.get_editor_property("PausedBuildings") == 1
        assert report.get_editor_property("UnsupportedBuildings") == 1
        assert "preserved_paused" in [str(v) for v in report.get_editor_property("GroupReasons")]
        assert "preserved_unsupported" in [str(v) for v in report.get_editor_property("GroupReasons")]
        unreal.log("WO_RUN_REPORT_TESTS_PASS: finalize once, early unknown, native confirmed partial failure, grouped apprentice competition/IDs, actual flexible occupancy, world-change and unknown reserve evidence, bounded work and paused separation")
    finally:
        had_fixture = fixture is not None
        report = fixture = graph = begin = finish = None
        unreal.SystemLibrary.collect_garbage()
        if had_fixture:
            unreal.EditorAssetLibrary.delete_asset(root + "BP_TestReportInputs")
        for actor in reversed(spawned):
            actors.destroy_actor(actor)


run()
