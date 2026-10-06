"""Validate full assignments and compile them into native action queues."""

import unreal


def put(obj, key, value):
    obj.set_editor_property(key, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    cls = load("BP_ActionPlan")
    assert cls, "Production action plan does not exist"
    plan = unreal.new_object(cls)
    snapshot = unreal.new_object(load("BP_WorkforceSnapshot"))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)

    def spawn(name):
        actor = actors.spawn_actor_from_class(native(name), unreal.Vector(0, 0, -100000))
        spawned.append(actor)
        return actor

    def building(number, component_name, occupants, required):
        actor = spawn("GridActor")
        put(actor, "ID", number)
        put(actor, "isPlayerOwned", True)
        put(actor, "Health", 100)
        component = actor.call_method("AddComponentByClass", args=(native(component_name), False, unreal.Transform(), False))
        wf = component.get_editor_property("m_workers")
        assert wf.import_text("(m_workerSlots=(" + ",".join("()" for _ in occupants) + "))")
        slots = list(wf.get_editor_property("m_workerSlots"))
        for i, person in enumerate(occupants):
            put(slots[i], "Agent", person)
            put(slots[i], "bIsRequiredToRun", required[i])
        put(wf, "m_workerSlots", slots)
        put(component, "m_workers", wf)
        return actor, component

    def capture(buildings, workers, workplaces):
        snapshot.call_method("ResetSnapshot")
        for actor in buildings:
            assert snapshot.call_method("AddBuilding", args=(actor,))
        snapshot.call_method("FinishBuildings")
        for worker, workplace in zip(workers, workplaces):
            assert snapshot.call_method("AddWorker", args=(worker, workplace))
        snapshot.call_method("AdvanceCapture")
        snapshot.call_method("AdvanceCapture")

    def build(targets, success=True):
        started = plan.call_method("BeginBuild", args=(snapshot, targets))[-1]
        if started:
            assert not plan.get_editor_property("BuildingStarts"), "Plan setup still initializes every building synchronously"
            for _ in range(1000):
                if plan.get_editor_property("BuildDone"):
                    break
                plan.call_method("AdvanceBuild")
        assert plan.get_editor_property("BuildDone")
        assert plan.get_editor_property("BuildSucceeded") == success, (targets, plan.get_editor_property("FailureCode"))
        result = list(zip(*(list(plan.get_editor_property(name)) for name in
                           ("ActionBuildings", "ActionSlots", "ActionWorkers", "ActionFire"))))
        if not success:
            assert not result, "An invalid plan must not expose a partial action queue"
        return result

    def apply_observed_queue(buildings, components, workers, workplaces, targets):
        # Editor native action bodies are stubs. Drive only the dispatch/observation
        # boundary; production validation and snapshot reconciliation execute normally.
        queue = build(targets)
        runner = unreal.new_object(load("BP_ApplicationRunner"))
        bridge = actors.spawn_actor_from_class(load("BP_ActionBridge"), unreal.Vector(0, 0, -100000))
        spawned.append(bridge)
        assert bridge.call_method("InitializeBridge", args=(unreal.new_object(load("WBP_ActionContext")),))
        columns = [list(column) for column in zip(*queue)] if queue else [[], [], [], []]
        assert runner.call_method("StartApplication", args=(snapshot, bridge, *columns, 0.0))[-1]
        for _ in range(len(columns[0]) + 1):
            if not runner.get_editor_property("ValidationActive"):
                break
            assert runner.call_method("AdvanceApplication", args=(0.0,))
        assert not runner.get_editor_property("ValidationActive") and not runner.get_editor_property("Waiting")
        places = list(workplaces)
        for index, (building_index, slot_index, worker_index, fire) in enumerate(queue):
            assert bridge.call_method("ValidateAction", args=(snapshot, building_index, slot_index,
                worker_index, fire, places[worker_index])), (index, queue)
            assert runner.call_method("RecordDispatch", args=(True, float(index)))
            wf = components[building_index].get_editor_property("m_workers")
            slots = list(wf.get_editor_property("m_workerSlots"))
            if fire and slots[slot_index].get_editor_property("bIsRequiredToRun"):
                # Native FIRE_WORKER also releases all optional incumbents.
                # The production queue must have accounted for each one first.
                for optional in slots:
                    if not optional.get_editor_property("bIsRequiredToRun"):
                        occupant = optional.get_editor_property("Agent")
                        assert occupant is None, "Required fire would cause an untracked native dismissal"
            put(slots[slot_index], "Agent", None if fire else workers[worker_index])
            put(wf, "m_workerSlots", slots)
            put(components[building_index], "m_workers", wf)
            places[worker_index] = None if fire else buildings[building_index]
            assert runner.call_method("ObserveAction", args=(places[worker_index], float(index) + 0.5))
        assert runner.get_editor_property("Done") and runner.get_editor_property("Succeeded")
        assert runner.get_editor_property("AppliedCount") == len(queue)
        final = [slot.get_editor_property("Agent") for component in components
                 for slot in component.get_editor_property("m_workers").get_editor_property("m_workerSlots")]
        for actual, target in zip(final, targets):
            if target != -2:
                assert actual == (workers[target] if target >= 0 else None)

    try:
        workers = [spawn("Prototype_Agent") for _ in range(4)]
        for index, worker in enumerate(workers):
            ch = worker.get_editor_property("m_characteristics")
            assert ch.import_text(f'(ID={1200 + index},guild="guild{index}")')
            put(worker, "m_characteristics", ch)
        a, ac = building(1300, "Industry", [workers[0], workers[1]], [True, False])
        b, bc = building(1301, "Industry", [workers[2]], [True])
        capture([a, b], workers, [a, a, b, None])
        before = [c.get_editor_property("m_workers").export_text() for c in (ac, bc)]
        assert build([0, 1, 2]) == [], "Already optimal assignments are no-ops"
        assert build([2, 1, 0]) == [(0, 1, 1, True), (0, 0, 0, True), (1, 0, 2, True),
                                   (0, 0, 2, False), (1, 0, 0, False), (0, 1, 1, False)]
        assert build([3, 2, 1]) == [(0, 1, 1, True), (0, 0, 0, True), (0, 0, 3, False),
                                   (1, 0, 2, True), (1, 0, 1, False), (0, 1, 2, False)]
        assert before == [c.get_editor_property("m_workers").export_text() for c in (ac, bc)], "Queue construction must be read-only"
        for invalid in ([0, 0, 2], [0, 1], [0, 1, 2, 3], [4, 1, 2], [-3, 1, 2], [-2, 1, 2], [-1, 1, 2]):
            build(invalid, False)
        assert build([-1, -1, 2]) == [(0, 1, 1, True), (0, 0, 0, True)]
        apply_observed_queue([a, b], [ac, bc], workers, [a, a, b, None], [3, 2, 1])
        for component, original in zip((ac, bc), before):
            original_wf = component.get_editor_property("m_workers")
            assert original_wf.import_text(original)
            put(component, "m_workers", original_wf)
        capture([a, b], workers, [a, a, b, None])
        wf = ac.get_editor_property("m_workers")
        put(wf, "bDisabled", True)
        put(ac, "m_workers", wf)
        build([2, 1, 0], False)
        put(wf, "bDisabled", False)
        put(ac, "m_workers", wf)

        # Unavailable incumbents are explicit preserved slots, never firing targets.
        capture([a, b], [workers[0], workers[2], workers[3]], [a, b, None])
        assert build([0, -2, 1]) == []
        build([0, -1, 1], False)
        build([0, 2, 1], False)
        build([2, -2, 1], False)

        # Unavoidable partial crews must preserve locked occupants without blocking
        # optimization elsewhere. Movable workers must not be stranded beside them.
        partial, pc = building(1304, "Industry", [workers[1], None], [True, True])
        capture([partial, b], [workers[2], workers[3]], [b, None])
        assert build([-2, -1, 1]) == [(1, 0, 0, True), (1, 0, 1, False)]
        assert build([-2, 1, 0]) == [(0, 1, 1, False)]
        assert pc.get_editor_property("m_workers").get_editor_property("m_workerSlots")[0].get_editor_property("Agent") == workers[1]

        # Preservation is not a new hire: an incumbent with changed admission
        # requirements remains untouched even if no longer eligible for a new hire.
        partial_wf = pc.get_editor_property("m_workers")
        partial_slots = list(partial_wf.get_editor_property("m_workerSlots"))
        assert partial_slots[0].import_text("(educationRequirement=Educated)")
        put(partial_wf, "m_workerSlots", partial_slots)
        put(pc, "m_workers", partial_wf)
        capture([partial, b], [workers[2], workers[3]], [b, None])
        assert build([-2, -1, 0]) == []

        # The real planner's extra column represents only this protected incumbent.
        # Decode it back to preservation, then run the real queue/confirmation path.
        layout_cls = load("BP_ProblemLayout")
        assert layout_cls, "Production snapshot-to-planner layout does not exist"
        layout = unreal.new_object(layout_cls)

        def make_layout(success=True):
            assert layout.call_method("BeginLayout", args=(snapshot,))
            for _ in range(1000):
                if layout.get_editor_property("LayoutDone"):
                    break
                layout.call_method("AdvanceLayout")
            assert layout.get_editor_property("LayoutDone")
            assert layout.get_editor_property("LayoutSucceeded") == success, layout.get_editor_property("FailureCode")

        make_layout()
        assert list(layout.get_editor_property("RowBuildings")) == [0, 0, 1]
        assert list(layout.get_editor_property("RowSlots")) == [0, 1, 0]
        assert list(layout.get_editor_property("Minimum")) == [True, True, True]
        assert list(layout.get_editor_property("FixedSlots")) == [2, -1, -1]
        assert list(layout.get_editor_property("ColumnWorkers")) == [0, 1, -2]
        assert list(layout.get_editor_property("ColumnActors")) == [workers[2], workers[3], workers[1]]
        staffing = unreal.new_object(load("BP_StaffingPlanner"))
        staffing.call_method("StartPlan", args=(
            [-1.0, -1.0, 0.0, -1.0, -1.0, -1.0, 2.0, 9.0, -1.0],
            list(layout.get_editor_property("RowBuildings")), list(layout.get_editor_property("Minimum")),
            [4, 0], len(layout.get_editor_property("ColumnActors")), True))
        assert staffing.call_method("RequireFlexibleMinimum", args=(list(layout.get_editor_property("FlexibleMinimumBuildings")),))[-1]
        assert staffing.call_method("RequireFixedSlots", args=(list(layout.get_editor_property("FixedSlots")),))[-1]
        for _ in range(1000):
            if staffing.get_editor_property("PlanDone"):
                break
            staffing.call_method("AdvancePlan")
        assert staffing.get_editor_property("PlanSucceeded")
        targets = [layout.get_editor_property("ColumnWorkers")[value] if value >= 0 else -1
                   for value in staffing.get_editor_property("PlanAssignment")]
        assert targets == [-2, -1, 1]
        apply_observed_queue([partial, b], [pc, bc], [workers[2], workers[3]], [b, None], targets)
        assert pc.get_editor_property("m_workers").get_editor_property("m_workerSlots")[0].get_editor_property("Agent") == workers[1]

        school, sc = building(1302, "School", [workers[0], workers[1]], [True, False])
        capture([school], workers, [school, school, None, None])
        make_layout()
        assert list(layout.get_editor_property("SchoolBuildings")) == [True]
        assert build([2, 1]) == [(0, 1, 1, True), (0, 0, 0, True), (0, 0, 2, False), (0, 1, 1, False)], "A movable student must be restored after the native teacher dismissal"
        ch = workers[2].get_editor_property("m_characteristics")
        assert ch.import_text('(guild="guild1")')
        put(workers[2], "m_characteristics", ch)
        capture([school], workers, [school, school, None, None])
        build([2, 1], False)
        assert build([2, 3]) == [(0, 1, 1, True), (0, 0, 0, True), (0, 0, 2, False), (0, 1, 3, False)]
        build([-1, 1], False)
        # Teacher dependency is semantic, even if an updated definition omits its required flag.
        school_wf = sc.get_editor_property("m_workers")
        school_slots = list(school_wf.get_editor_property("m_workerSlots"))
        put(school_slots[0], "bIsRequiredToRun", False)
        put(school_wf, "m_workerSlots", school_slots)
        put(sc, "m_workers", school_wf)
        capture([school], workers, [school, school, None, None])
        make_layout()
        assert list(layout.get_editor_property("Minimum")) == [True, False], "No required flags still reserve a first worker; school coupling is a separate constraint"
        build([-1, 1], False)
        put(school_slots[0], "bIsRequiredToRun", True)
        put(school_wf, "m_workerSlots", school_slots)
        put(sc, "m_workers", school_wf)
        capture([school], [workers[0], workers[2], workers[3]], [school, None, None])
        build([1, -2], False)
        build([2, -2], False)

        # Duplicate current occupancy invalidates the input, even for preserved slots.
        invalid, _ = building(1303, "Industry", [workers[3], workers[3]], [True, False])
        capture([invalid], [], [])
        make_layout(False)
        assert list(layout.get_editor_property("RowBuildings")) == [], "Failure must discard partial planner input"
        build([-2, -2], False)

        optional, oc = building(1305, "Industry", [None, workers[1]], [False, False])
        capture([optional], [], [])
        original_optional = oc.get_editor_property("m_workers").export_text()
        make_layout()
        assert list(layout.get_editor_property("Minimum")) == [False, False], "Flexible minimum is not pinned to an arbitrary slot"
        assert list(layout.get_editor_property("FlexibleMinimumBuildings")) == [True]
        assert list(layout.get_editor_property("FixedSlots")) == [-1, 0]
        assert list(layout.get_editor_property("ColumnWorkers")) == [-2]
        assert original_optional == oc.get_editor_property("m_workers").export_text(), "Layout creation must be read-only"
        paused = oc.get_editor_property("m_workers")
        put(paused, "bDisabled", True)
        put(oc, "m_workers", paused)
        make_layout(False)
        assert str(layout.get_editor_property("FailureCode")) == "world_changed"
        assert not layout.call_method("BeginLayout", args=(None,))
        assert layout.get_editor_property("LayoutDone") and not layout.get_editor_property("LayoutSucceeded")
        capture([], [], [])
        make_layout()
        assert list(layout.get_editor_property("ColumnActors")) == []
        assert list(layout.get_editor_property("FixedSlots")) == []
        assert build([]) == []
        plan.call_method("AdvanceBuild")
        assert plan.get_editor_property("BuildSucceeded")
        unreal.log("WO_ACTION_PLAN_TESTS_PASS: snapshot layout through constrained planner, full-plan validation, no-ops/swaps, ordered fires/required/optional hires, locked and unavoidable partial crews, planned school dependencies, malformed/stale/duplicate rejection, read-only layout/queue construction and serial-runner integration through explicit observations")
    finally:
        for actor in reversed(spawned):
            actors.destroy_actor(actor)


run()
