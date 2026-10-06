"""Drive the production controller end-to-end across explicit editor-native boundaries."""

import unreal


def put(obj, name, value):
    obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    cls = load("BP_WorkerOptimizer")
    assert cls, "Production runtime controller does not exist"
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)

    def spawn(actor_class):
        actor = actors.spawn_actor_from_class(actor_class, unreal.Vector(0, 0, -100000))
        spawned.append(actor)
        return actor

    def component_building(number, capacity, occupant=None, paused=False):
        actor = spawn(native("GridActor"))
        for name, value in (("ID", number), ("isPlayerOwned", True), ("Health", 100)):
            put(actor, name, value)
        comp = actor.call_method("AddComponentByClass", args=(native("Industry"), False, unreal.Transform(), False))
        wf = comp.get_editor_property("m_workers")
        assert wf.import_text("(m_workerSlots=(" + ",".join("(bIsRequiredToRun=True)" if i == 0 else "()" for i in range(capacity)) + "))")
        slots = list(wf.get_editor_property("m_workerSlots"))
        put(slots[0], "Agent", occupant)
        put(wf, "m_workerSlots", slots)
        put(wf, "bDisabled", paused)
        put(comp, "m_workers", wf)
        return actor, comp

    try:
        controller = spawn(cls)
        tick = unreal.get_default_object(cls).get_editor_property("primary_actor_tick")
        assert tick.get_editor_property("start_with_tick_enabled")
        assert controller.call_method("IsActorTickEnabled")
        assert controller.call_method("ReadClock") >= 0.0
        assert not controller.call_method("BeginRun")
        bridge = spawn(load("BP_ActionBridge"))
        assert bridge.call_method("InitializeBridge", args=(unreal.new_object(load("WBP_ActionContext")),))
        assert controller.call_method("Initialize", args=(controller, bridge))
        parts = {name: controller.get_editor_property(name) for name in
                 ("Snapshot", "Layout", "Matrix", "Planner", "Search", "Scorer", "Settings", "ActionPlan", "Runner", "AutoAssignment")}
        assert all(parts.values())
        assert all(part.get_outer() == controller for part in parts.values()), "Session objects belong to this world controller"
        assert str(parts["AutoAssignment"].get_editor_property("Mode")) == "off"
        assert controller.call_method("Initialize", args=(controller, bridge))
        assert controller.get_editor_property("Snapshot") == parts["Snapshot"], "Reinitializing must not discard session state"
        assert not controller.call_method("Initialize", args=(bridge, bridge))
        assert not controller.call_method("BeginRun"), "Run admission waits for complete session policy keys"
        # This commandlet has no native game instance/catalog. Explicitly finish
        # the empty input fixture; production discovery stays separately guarded.
        assert parts["Settings"].call_method("FinishPolicyKeys")
        assert not controller.call_method("BeginTriggeredRun", args=("unsupported",))
        assert controller.call_method("BeginRun")
        assert str(controller.get_editor_property("RunTrigger")) == "manual"
        assert parts["AutoAssignment"].get_editor_property("Running")
        assert parts["Settings"].get_editor_property("PolicyFrozen"), "Accepted admission must already own its frozen policy"
        controller.call_method("ReceiveTick", args=(0.016,))
        assert controller.get_editor_property("RunDone") and not controller.get_editor_property("RunSucceeded")
        assert str(controller.get_editor_property("FailureCode")) == "configuration_unavailable", "Do not mask editor-native configuration failure"
        assert not parts["Settings"].get_editor_property("PolicyFrozen"), "Configuration failure releases the admission snapshot"
        assert not parts["AutoAssignment"].get_editor_property("Running")
        def finish_report():
            for _ in range(20000):
                if not controller.get_editor_property("ReportPending"):
                    return controller.get_editor_property("CompletedReport")
                controller.call_method("AdvanceRun", args=(1.0,))
            raise AssertionError("Terminal report exceeded finite fixture bound")

        first_report = finish_report()
        assert first_report.get_editor_property("ReportDone")
        assert not first_report.get_editor_property("CountsKnown"), "Early configuration failure must not inherit last run counts"
        assert controller.get_editor_property("CompletedRecordCount") == 1
        assert not controller.call_method("AdvanceTerminalReport")
        assert controller.get_editor_property("CompletedRecordCount") == 1
        workers = [spawn(native("Prototype_Agent")) for _ in range(5)]
        for index, worker in enumerate(workers):
            ch = worker.get_editor_property("m_characteristics")
            assert ch.import_text(f'(ID={4100 + index},guild="guild{index}")')
            put(worker, "m_characteristics", ch)
        fixtures = [component_building(4200 + index, capacity) for index, capacity in enumerate((2, 2, 1))]
        paused, paused_comp = component_building(4203, 1, workers[4], True)
        paused_before = paused_comp.get_editor_property("m_workers").export_text()
        originals = [comp.get_editor_property("m_workers").export_text() for _, comp in fixtures]
        snapshot, matrix, search, runner = (parts[n] for n in ("Snapshot", "Matrix", "Search", "Runner"))
        now = 1.0

        def current_place(worker):
            for actor, comp in fixtures + [(paused, paused_comp)]:
                if any(slot.get_editor_property("Agent") == worker for slot in comp.get_editor_property("m_workers").get_editor_property("m_workerSlots")):
                    return actor
            return None

        def observe_action(apply=True):
            nonlocal now
            for _ in range(len(runner.get_editor_property("ActionFire")) + 1):
                if not runner.get_editor_property("ValidationActive"):
                    break
                assert runner.call_method("AdvanceApplication", args=(now,))
            assert not runner.get_editor_property("ValidationActive")
            i = runner.get_editor_property("ActionIndex")
            b = runner.get_editor_property("ActionBuildings")[i]
            slot_index = runner.get_editor_property("ActionSlots")[i]
            w = runner.get_editor_property("ActionWorkers")[i]
            fire = runner.get_editor_property("ActionFire")[i]
            worker = snapshot.get_editor_property("Workers")[w]
            if not runner.get_editor_property("Waiting"):
                assert bridge.call_method("ValidateAction", args=(snapshot, b, slot_index, w, fire, current_place(worker)))
                assert runner.call_method("RecordDispatch", args=(True, now))
                now += 0.1
            if apply:
                actor = snapshot.get_editor_property("Buildings")[b]
                comp = next(comp for candidate, comp in fixtures if candidate == actor)
                wf = comp.get_editor_property("m_workers")
                slots = list(wf.get_editor_property("m_workerSlots"))
                put(slots[slot_index], "Agent", None if fire else worker)
                put(wf, "m_workerSlots", slots)
                put(comp, "m_workers", wf)
                assert runner.call_method("ObserveAction", args=(None if fire else actor, now))
                now += 0.1

        def step():
            nonlocal now
            phase = controller.get_editor_property("Phase")
            if phase == 0:
                assert parts["Scorer"].call_method("Configure", args=(25.0, -10.0, 20.0, 15.0, 10.0))
                assert controller.call_method("AcceptConfig", args=(True,))
            elif phase == 1 and snapshot.get_editor_property("WorkerPhase") and not snapshot.get_editor_property("Workers"):
                # GetWorkplace is stubbed in the editor; observations are supplied
                # before native capture encounters these same agents.
                for worker in workers[:4]:
                    assert snapshot.call_method("AddWorker", args=(worker, current_place(worker)))
                controller.call_method("AdvanceRun", args=(now,))
            elif phase == 3 and search.get_editor_property("State") == 2 and matrix.get_editor_property("MatrixActive"):
                if matrix.get_editor_property("SetupActive"):
                    matrix.call_method("AdvanceMatrix")
                elif matrix.get_editor_property("Stage") == 0:
                    matrix.call_method("RecordDefinition", args=("fixture", True))
                elif matrix.get_editor_property("AwaitingScore"):
                    wood = matrix.get_editor_property("EdgeBuilding") == fixtures[2][0]
                    column = matrix.get_editor_property("EdgeColumn")
                    score = (150.0 if column == 3 else 50.0) if wood else 100.0
                    assert matrix.call_method("RecordScore", args=(True, score))
                else:
                    if matrix.get_editor_property("EdgeIndex") == 0 and not matrix.get_editor_property("PolicyImported"):
                        priorities = [0 if actor == fixtures[2][0] else 4 for actor in snapshot.get_editor_property("Buildings")]
                        assert matrix.call_method("UsePolicy", args=(priorities, True))[-1]
                    matrix.call_method("PrepareEdge")
            elif phase == 6 and runner.get_editor_property("Active"):
                observe_action()
            else:
                controller.call_method("AdvanceRun", args=(now,))
            now += 0.01

        def reach(phase=None):
            for _ in range(20000):
                if controller.get_editor_property("RunDone") or (phase is not None and controller.get_editor_property("Phase") == phase):
                    break
                step()
            if phase is None:
                assert controller.get_editor_property("RunDone") and controller.get_editor_property("RunSucceeded"), controller.get_editor_property("FailureCode")
                finish_report()
            else:
                assert controller.get_editor_property("Phase") == phase and controller.get_editor_property("RunActive"), controller.get_editor_property("FailureCode")

        assert controller.call_method("BeginRun")
        assert controller.get_editor_property("CurrentReport") != first_report
        assert not controller.call_method("BeginRun")
        reach()
        assert controller.get_editor_property("AppliedCount") == 3, "Default reserve must leave one of four movable residents free"
        completed = controller.get_editor_property("CompletedReport")
        assert completed.get_editor_property("ConfirmedChanges") == 3
        assert completed.get_editor_property("ConfirmedHires") == 3
        old_id = completed.get_editor_property("RunId")
        assert old_id and first_report.get_editor_property("RunId") != old_id
        counts = [sum(slot.get_editor_property("Agent") is not None for slot in comp.get_editor_property("m_workers").get_editor_property("m_workerSlots")) for _, comp in fixtures]
        assert counts == [1, 1, 1], counts
        assert fixtures[2][1].get_editor_property("m_workers").get_editor_property("m_workerSlots")[0].get_editor_property("Agent") == workers[3]
        assert paused_before == paused_comp.get_editor_property("m_workers").export_text()
        assert workers[4] in snapshot.get_editor_property("ProtectedWorkers")
        assert workers[4] not in snapshot.get_editor_property("Workers")
        assert controller.call_method("BeginTriggeredRun", args=("minutes_5",))
        assert str(controller.get_editor_property("RunTrigger")) == "minutes_5"
        reach()
        assert controller.get_editor_property("AppliedCount") == 0, "Automatic admission uses the identical native pipeline"
        assert not parts["AutoAssignment"].get_editor_property("Running")
        free = next(worker for worker in workers[:4] if current_place(worker) is None)
        wf = fixtures[0][1].get_editor_property("m_workers")
        slots = list(wf.get_editor_property("m_workerSlots"))
        put(slots[1], "Agent", free)
        put(wf, "m_workerSlots", slots)
        put(fixtures[0][1], "m_workers", wf)
        assert all(current_place(worker) is not None for worker in workers[:4])
        assert controller.call_method("BeginRun")
        reach()
        assert sum(current_place(worker) is None for worker in workers[:4]) == 1, "Reserve also releases an already employed resident"
        assert controller.get_editor_property("AppliedCount") >= 1
        assert paused_before == paused_comp.get_editor_property("m_workers").export_text()

        def restore_fixtures():
            for (_, comp), original in zip(fixtures, originals):
                wf = comp.get_editor_property("m_workers")
                assert wf.import_text(original)
                put(comp, "m_workers", wf)

        def set_paused(index, value):
            wf = fixtures[index][1].get_editor_property("m_workers")
            put(wf, "bDisabled", value)
            put(fixtures[index][1], "m_workers", wf)

        def await_replan():
            for _ in range(20000):
                if controller.get_editor_property("RunDone") or controller.get_editor_property("Phase") == 1:
                    return
                step()
            raise AssertionError("World-change handling did not reach a bounded outcome")

        restore_fixtures()
        records = controller.get_editor_property("CompletedRecordCount")
        assert controller.call_method("BeginRun")
        active_report = controller.get_editor_property("CurrentReport")
        reach(5)
        set_paused(0, True)
        await_replan()
        assert controller.get_editor_property("RunActive"), "A changed building must replan automatically, not require a second click"
        assert controller.get_editor_property("ReplanCount") == 1
        assert parts["Settings"].get_editor_property("PolicyFrozen")
        assert parts["AutoAssignment"].get_editor_property("Running")
        assert controller.get_editor_property("CurrentReport") == active_report
        assert not controller.call_method("BeginRun")
        reach()
        assert controller.get_editor_property("CompletedRecordCount") == records + 1
        assert controller.get_editor_property("CompletedReport") == active_report
        assert not any(slot.get_editor_property("Agent") for slot in fixtures[0][1].get_editor_property("m_workers").get_editor_property("m_workerSlots"))

        restore_fixtures()
        records = controller.get_editor_property("CompletedRecordCount")
        assert controller.call_method("BeginRun")
        for attempt in range(3):
            reach(5)
            set_paused(attempt, True)
            await_replan()
            assert controller.get_editor_property("ReplanCount") == min(attempt + 1, 2), (attempt, controller.get_editor_property("ReplanCount"), controller.get_editor_property("FailureCode"))
            assert controller.get_editor_property("RunActive") == (attempt < 2), "At most two automatic replans per request"
        assert str(controller.get_editor_property("FailureCode")) == "world_changed"
        finish_report()
        assert controller.get_editor_property("CompletedRecordCount") == records + 1
        assert controller.get_editor_property("CompletedReport").get_editor_property("ConfirmedChanges") == 0

        restore_fixtures()
        records = controller.get_editor_property("CompletedRecordCount")
        assert controller.call_method("BeginRun")
        reach(6)
        observe_action(False)
        runner.call_method("FailApplication", args=("world_changed",))
        controller.call_method("SyncApplication")
        assert controller.get_editor_property("RunActive"), "Pending native confirmation must remain part of this request"
        assert controller.get_editor_property("ReplanCount") == 0, "Never reset a snapshot under a pending command"
        assert runner.get_editor_property("Waiting")
        assert not controller.call_method("BeginRun")
        observe_action(True)
        controller.call_method("SyncApplication")
        assert controller.get_editor_property("Phase") == 1
        assert controller.get_editor_property("ReplanCount") == 1
        reach()
        assert controller.get_editor_property("AppliedCount") == 3, "Confirmed changes survive internal replan"
        assert controller.get_editor_property("CompletedRecordCount") == records + 1
        assert controller.get_editor_property("CompletedReport").get_editor_property("ConfirmedHires") == 3
        for phase in range(7):
            assert controller.call_method("BeginRun")
            reach(phase)
            assert controller.call_method("CancelRun")
            assert controller.get_editor_property("RunDone") and not controller.get_editor_property("RunSucceeded")
            assert not parts["Settings"].get_editor_property("PolicyFrozen"), "Cancellation releases the frozen run policy"
            finish_report()
            assert controller.get_editor_property("CompletedReport").get_editor_property("ConfirmedChanges") == 0
            assert completed.get_editor_property("RunId") == old_id and completed.get_editor_property("ConfirmedChanges") == 3
        for (_, comp), original in zip(fixtures, originals):
            wf = comp.get_editor_property("m_workers")
            assert wf.import_text(original)
            put(comp, "m_workers", wf)
        assert controller.call_method("BeginRun")
        reach(6)
        observe_action(False)
        assert controller.call_method("CancelRun")
        assert controller.get_editor_property("ReportPending")
        assert not controller.get_editor_property("CurrentReport").get_editor_property("FinishStarted"), "Late native confirmation remains part of the one terminal record"
        assert parts["AutoAssignment"].get_editor_property("Running"), "Unresolved cancelled native command remains scheduler-busy"
        assert not controller.call_method("BeginRun"), "An unresolved native command blocks a second run"
        observe_action(True)
        controller.call_method("AdvanceRun", args=(now,))
        assert not parts["AutoAssignment"].get_editor_property("Running"), "Late confirmation ends the busy period before restarting its deadline"
        assert not controller.get_editor_property("RunSucceeded") and controller.get_editor_property("AppliedCount") == 1
        late_report = finish_report()
        assert late_report.get_editor_property("ConfirmedChanges") == 1
        assert str(late_report.get_editor_property("Outcome")) == "cancelled"
        assert controller.call_method("BeginRun")
        record_count = controller.get_editor_property("CompletedRecordCount")
        shutdown_save = controller.get_editor_property("CurrentReport").get_editor_property("SaveIdentity")
        controller.call_method("Shutdown")
        shutdown_report = controller.get_editor_property("CompletedReport")
        assert shutdown_report.get_editor_property("ReportDone") and not shutdown_report.get_editor_property("CountsKnown")
        assert not shutdown_report.get_editor_property("ConfirmationWindowKnown")
        assert str(shutdown_report.get_editor_property("Outcome")) == "cancelled"
        assert shutdown_report.get_editor_property("SaveIdentity") == shutdown_save
        assert "observation_unavailable" in [str(v) for v in shutdown_report.get_editor_property("GroupReasons")]
        assert controller.get_editor_property("CompletedRecordCount") == record_count + 1
        assert not controller.call_method("Shutdown") and controller.get_editor_property("CompletedRecordCount") == record_count + 1
        assert not controller.get_editor_property("Initialized")
        assert not controller.call_method("BeginRun")
        unreal.log("WO_CONTROLLER_TESTS_PASS: real capture/layout/search/validation/application pipeline, food/logging shortage plus one free builder, paused-worker preservation, three confirmed hires then no-op, phase cancellation/reuse, unresolved-command restart lock, late confirmation and shutdown; native data/dispatch success supplied at explicit observation boundaries")
    finally:
        for actor in reversed(spawned):
            actors.destroy_actor(actor)


run()
