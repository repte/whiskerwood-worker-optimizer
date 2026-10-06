"""Test the production action guards; native dispatch is stubbed in the editor."""

import unreal


def put(obj, name, value):
    obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_ActionBridge.BP_ActionBridge_C")
    assert cls, "Production action bridge does not exist"
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []

    def spawn(cls):
        obj = actors.spawn_actor_from_class(cls, unreal.Vector(0, 0, -100000))
        assert obj
        spawned.append(obj)
        return obj

    def native(name):
        return unreal.load_class(None, "/Script/ProjectArco." + name)

    try:
        bridge = spawn(cls)
        assert not bridge.get_editor_property("primary_actor_tick").get_editor_property("start_with_tick_enabled"), "Native selection tick must start disabled"
        snapshot = unreal.new_object(unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_WorkforceSnapshot.BP_WorkforceSnapshot_C"))
        person = spawn(native("Prototype_Agent"))
        ch = person.get_editor_property("m_characteristics")
        assert ch.import_text("(ID=701)")
        put(person, "m_characteristics", ch)
        state = person.get_editor_property("m_state")
        put(state, "derived_productivity", 93.0)
        put(person, "m_state", state)
        building = spawn(native("GridActor"))
        put(building, "ID", 700)
        put(building, "isPlayerOwned", True)
        put(building, "Health", 100)
        component = building.call_method("AddComponentByClass", args=(native("Industry"), False, unreal.Transform(), False))
        workforce = component.get_editor_property("m_workers")
        assert workforce.import_text("(m_workerSlots=((bIsRequiredToRun=True),()))")
        put(component, "m_workers", workforce)

        def capture(workplace=None):
            snapshot.call_method("ResetSnapshot")
            assert snapshot.call_method("AddBuilding", args=(building,))
            snapshot.call_method("FinishBuildings")
            assert snapshot.call_method("AddWorker", args=(person, workplace))
            snapshot.call_method("AdvanceCapture")
            snapshot.call_method("AdvanceCapture")
            assert snapshot.get_editor_property("CaptureDone")

        def check(fire=False, workplace=None, b=0, s=0, w=0, snap=snapshot):
            return bridge.call_method("ValidateAction", args=(snap, b, s, w, fire, workplace))

        capture()
        assert check(), "An unchanged empty target and free worker should pass structural guards"
        assert str(bridge.get_editor_property("RejectionGuard")) == "None", "Successful validation clears old rejection evidence"
        put(state, "derived_productivity", 103.0)
        put(person, "m_state", state)
        assert check(), "Derived productivity93->103 must not reject an otherwise safe dispatch"
        assert workforce.import_text("(m_workerSlots=((educationRequirement=Master,bIsRequiredToRun=True),()))")
        put(component, "m_workers", workforce)
        capture()
        assert not check(), "Unqualified workers must fail the final action guard, not only planning"
        assert str(bridge.get_editor_property("RejectionGuard")) == "bridge.hire_role_eligibility"
        assert workforce.import_text("(m_workerSlots=((educationRequirement=ApprenticeOnly,bIsRequiredToRun=True),()))")
        put(component, "m_workers", workforce)
        assert ch.import_text("(ID=701,education=Apprentice)")
        put(person, "m_characteristics", ch)
        capture()
        assert not check(), "A selector-only match must never be sent to native hire"
        assert str(bridge.get_editor_property("RejectionGuard")) == "bridge.hire_role_eligibility"
        assert ch.import_text("(ID=701)")
        put(person, "m_characteristics", ch)
        assert workforce.import_text("(m_workerSlots=((bIsRequiredToRun=True),()))")
        put(component, "m_workers", workforce)
        capture()
        assert not check(s=1), "Optional slot is locked until every required slot is occupied"
        assert str(bridge.get_editor_property("RejectionGuard")) == "bridge.optional_before_required"
        for indices in ((-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 2, 0), (0, 0, -1), (0, 0, 1)):
            assert not check(b=indices[0], s=indices[1], w=indices[2]), indices
        assert not check(snap=None)
        assert not check(fire=True), "Cannot fire an unemployed worker"
        assert not check(workplace=building), "Cannot hire an already employed worker"
        snapshot.call_method("ResetSnapshot")
        assert not check(), "Partial capture must not be used"
        capture()
        collision = spawn(native("Prototype_Agent"))
        put(collision, "m_characteristics", ch)
        assert not snapshot.call_method("AddWorker", args=(collision, None))
        assert not snapshot.get_editor_property("SnapshotValid")
        assert not check()
        capture()
        for field, value in (("isPlayerOwned", False), ("Health", 0), ("ID", 999)):
            before = building.get_editor_property(field)
            put(building, field, value)
            assert not check(), field
            put(building, field, before)
        put(workforce, "bDisabled", True)
        put(component, "m_workers", workforce)
        assert not check(), "New pause must block hiring"
        put(workforce, "bDisabled", False)
        slots = list(workforce.get_editor_property("m_workerSlots"))
        put(slots[0], "Agent", person)
        put(workforce, "m_workerSlots", slots)
        put(component, "m_workers", workforce)
        assert not check(), "Changed occupancy must block hiring"
        capture(building)
        assert check(fire=True, workplace=building)
        assert not check(fire=True, workplace=building, s=1), "Fire must match the exact occupied slot"
        assert not check(fire=True, workplace=None), "Reported workplace changed"
        assert not check(workplace=building), "Must not overwrite occupied slots"
        put(workforce, "bDisabled", True)
        put(component, "m_workers", workforce)
        assert not check(fire=True, workplace=building), "New pause must block firing"
        put(workforce, "bDisabled", False)
        put(component, "m_workers", workforce)
        state = person.get_editor_property("m_state")
        put(state, "isBeingManhandled", True)
        put(person, "m_state", state)
        assert not check(fire=True, workplace=building), "Unavailable worker must not be moved"
        assert bridge.get_editor_property("QueuedActions") == 0
        assert component.get_editor_property("m_workers").get_editor_property("m_workerSlots")[0].get_editor_property("Agent") == person
        assert not bridge.call_method("InitializeBridge", args=(None,))
        assert not bridge.call_method("QueueAction", args=(snapshot, 0, 0, 0, True)), "Missing private context must refuse dispatch"
        put(state, "isBeingManhandled", False)
        put(person, "m_state", state)
        put(slots[0], "Agent", collision)
        put(workforce, "m_workerSlots", slots)
        put(component, "m_workers", workforce)
        capture()
        assert check(s=1), "Complete required crew should unlock an optional empty slot"
        put(slots[0], "Agent", None)
        put(slots[0], "bIsRequiredToRun", False)
        put(workforce, "m_workerSlots", slots)
        put(component, "m_workers", workforce)
        capture()
        assert check(s=1), "A workplace without required roles must remain assignable"
        context_cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/WBP_ActionContext.WBP_ActionContext_C")
        assert context_cls
        context = unreal.new_object(context_cls)
        assert bridge.call_method("InitializeBridge", args=(context,))
        assert bridge.get_editor_property("m_activeDetailWidget") == context
        assert not bridge.call_method("IsActorTickEnabled")
        assert not bridge.call_method("QueueAction", args=(snapshot, 0, 1, 0, False)), "Native definition stub cannot authorize a hire in editor"
        assert str(bridge.get_editor_property("RejectionGuard")) == "bridge.definition_unavailable"
        assert not bridge.call_method("RejectAction", args=("bridge.later_guard",))
        assert str(bridge.get_editor_property("RejectionGuard")) == "bridge.definition_unavailable", "First rejection must not be overwritten"
        assert bridge.get_editor_property("QueuedActions") == 0
        native_result = lambda fire=False, target=snapshot: bridge.call_method("ConfirmNativeResult", args=(target, 0, 1, 0, fire))
        assert not native_result(), "A returned native call with an unchanged empty slot is a rejection, not pending work"
        assert str(bridge.get_editor_property("RejectionGuard")) == "bridge.native_rejected"
        put(slots[1], "Agent", person)
        put(workforce, "m_workerSlots", slots)
        put(component, "m_workers", workforce)
        assert native_result(), "The exact intended hire is the native receipt"
        assert str(bridge.get_editor_property("RejectionGuard")) == "None"
        assert not native_result(fire=True), "An unchanged fire target must not be acknowledged"
        put(slots[1], "Agent", collision)
        put(workforce, "m_workerSlots", slots)
        put(component, "m_workers", workforce)
        assert not native_result(), "Another worker in the slot is not our successful hire"
        assert not native_result(fire=True), "Replacing an occupant is not the expected empty fire result"
        put(slots[1], "Agent", None)
        put(workforce, "m_workerSlots", slots)
        put(component, "m_workers", workforce)
        assert native_result(fire=True), "A cleared target slot confirms the native fire"
        assert not native_result(target=None), "Unavailable post-call observations cannot count as accepted"
        assert bridge.get_editor_property("QueuedActions") == 0, "Observing a native result must never dispatch another action"
        assert not bridge.call_method("InitializeBridge", args=(None,))
        assert not bridge.call_method("QueueAction", args=(snapshot, 0, 1, 0, False))
        assert str(bridge.get_editor_property("RejectionGuard")) == "bridge.not_ready", "New dispatch resets stale rejection evidence"
        unreal.log("WO_ACTION_BRIDGE_TESTS_PASS: native admission and exact post-call slot receipts, snapshot/indices/ownership/pause/availability/occupancy/required-crew guards, private context, disabled tick; no native actions executed")
    finally:
        for obj in reversed(spawned):
            actors.destroy_actor(obj)


run()
