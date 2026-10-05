"""Verify exact action results; only transient fixtures simulate native game changes."""

import unreal


def put(obj, key, value):
    obj.set_editor_property(key, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_WorkforceSnapshot.BP_WorkforceSnapshot_C")
    snapshot = unreal.new_object(cls)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)

    def spawn(name):
        actor = actors.spawn_actor_from_class(native(name), unreal.Vector(0, 0, -100000))
        spawned.append(actor)
        return actor

    def occupancy(component, index, person):
        wf = component.get_editor_property("m_workers")
        slots = list(wf.get_editor_property("m_workerSlots"))
        put(slots[index], "Agent", person)
        put(wf, "m_workerSlots", slots)
        put(component, "m_workers", wf)

    def state():
        return ([x.export_text() for x in snapshot.get_editor_property("Workforces")],
                list(snapshot.get_editor_property("WorkerWorkplaces")),
                [x.export_text() for x in snapshot.get_editor_property("States")])

    try:
        worker, other = spawn("Prototype_Agent"), spawn("Prototype_Agent")
        for number, person in enumerate((worker, other), 900):
            ch = person.get_editor_property("m_characteristics")
            assert ch.import_text(f"(ID={number})")
            put(person, "m_characteristics", ch)
        buildings, components = [], []
        for number in range(2):
            building = spawn("GridActor")
            put(building, "ID", 950 + number)
            put(building, "isPlayerOwned", True)
            put(building, "Health", 100)
            component = building.call_method("AddComponentByClass", args=(native("Industry"), False, unreal.Transform(), False))
            wf = component.get_editor_property("m_workers")
            assert wf.import_text("(m_workerSlots=((bIsRequiredToRun=True),()))")
            put(component, "m_workers", wf)
            buildings.append(building)
            components.append(component)

        def capture(workplace):
            snapshot.call_method("ResetSnapshot")
            for building in buildings:
                assert snapshot.call_method("AddBuilding", args=(building,))
            snapshot.call_method("FinishBuildings")
            assert snapshot.call_method("AddWorker", args=(worker, workplace))
            snapshot.call_method("AdvanceCapture")
            snapshot.call_method("AdvanceCapture")
            assert snapshot.get_editor_property("CaptureDone")

        confirm = lambda b=0, slot=0, w=0, fire=True, workplace=None: snapshot.call_method("ConfirmAction", args=(b, slot, w, fire, workplace))
        occupancy(components[0], 0, worker)
        capture(buildings[0])
        baseline = state()
        assert not confirm(workplace=buildings[0]), "Queued is not applied"
        assert state() == baseline
        for b, slot, w in ((-1, 0, 0), (2, 0, 0), (0, -1, 0), (0, 2, 0), (0, 0, -1), (0, 0, 1)):
            assert not confirm(b, slot, w)
        occupancy(components[0], 0, None)
        assert not confirm(workplace=buildings[0]), "Workplace and slot must both confirm the result"
        assert state() == baseline
        st = worker.get_editor_property("m_state")
        put(st, "derived_productivity", 100.0)
        put(worker, "m_state", st)
        assert confirm(), "Confirmed fire must advance only the owned expected snapshot"
        assert snapshot.call_method("BuildingUnchanged", args=(0,))
        assert snapshot.call_method("WorkerUnchanged", args=(0, None))
        baseline = state()
        assert not confirm(), "A confirmation must not be counted twice"
        assert state() == baseline

        occupancy(components[1], 0, worker)
        assert not confirm(1, fire=False), "Hire needs matching native workplace"
        assert state() == baseline
        put(st, "derived_productivity", 150.0)
        put(worker, "m_state", st)
        live_before = components[1].get_editor_property("m_workers").export_text()
        assert confirm(1, fire=False, workplace=buildings[1])
        assert components[1].get_editor_property("m_workers").export_text() == live_before, "Confirmation must not write live game arrays"
        assert snapshot.call_method("BuildingUnchanged", args=(1,))
        assert snapshot.call_method("WorkerUnchanged", args=(0, buildings[1]))
        assert not confirm(1, fire=False, workplace=buildings[1])

        # A matching target slot is not enough if any other slot or role changed.
        capture(buildings[1])
        baseline = state()
        occupancy(components[1], 0, None)
        occupancy(components[1], 1, other)
        assert not confirm(1)
        assert state() == baseline
        occupancy(components[1], 1, None)
        original_wf = components[1].get_editor_property("m_workers").export_text()
        for field in ("bDisabled", "bOvertime"):
            wf = components[1].get_editor_property("m_workers")
            put(wf, field, True)
            put(components[1], "m_workers", wf)
            assert not confirm(1), field
            assert state() == baseline
            assert wf.import_text(original_wf)
            put(components[1], "m_workers", wf)
        for change in ("educationRequirement=Master", "bIsRequiredToRun=False", "bGivesBonus=True"):
            wf = components[1].get_editor_property("m_workers")
            assert wf.import_text(f"(m_workerSlots=(({change}),()))")
            put(components[1], "m_workers", wf)
            assert not confirm(1), change
            assert state() == baseline
            assert wf.import_text(original_wf)
            put(components[1], "m_workers", wf)
        for field, value in (("isPlayerOwned", False), ("Health", 0), ("ID", 12345)):
            original = buildings[1].get_editor_property(field)
            put(buildings[1], field, value)
            assert not confirm(1), field
            assert state() == baseline
            put(buildings[1], field, original)
        ch = worker.get_editor_property("m_characteristics")
        original_ch = ch.export_text()
        assert ch.import_text('(traits=("scientist"))')
        put(worker, "m_characteristics", ch)
        assert not confirm(1), "Unrelated worker changes must not be absorbed"
        assert state() == baseline
        assert ch.import_text(original_ch)
        put(worker, "m_characteristics", ch)
        assert confirm(1)
        snapshot.call_method("ResetSnapshot")
        assert not confirm()
        unreal.log("WO_ACTION_CONFIRMATION_TESTS_PASS: exact fire/hire, pending vs confirmed, duplicate rejection, unrelated changes, identity/pause/roles, snapshot-only updates")
    finally:
        for actor in reversed(spawned):
            actors.destroy_actor(actor)


run()
