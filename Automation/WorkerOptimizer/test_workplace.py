"""Test read-only workplace adaptation with transient editor actors."""

import unreal


def run():
    adapter_class = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_WorkplaceAdapter.BP_WorkplaceAdapter_C")
    assert adapter_class is not None, "Production workplace adapter does not exist"
    adapter = unreal.new_object(adapter_class)
    known, _ = adapter.call_method("ReadWorkplace", args=(None,))
    assert not known, "Null workplace was accepted"
    actor_class = unreal.load_class(None, "/Script/ProjectArco.GridActor")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for component_name in ("Industry", "School", "HarvestingCamp"):
        actor = actors.spawn_actor_from_class(actor_class, unreal.Vector(0, 0, -100000))
        assert actor is not None
        try:
            known, _ = adapter.call_method("ReadWorkplace", args=(actor,))
            assert not known, "Actor without a workplace was accepted"
            component_class = unreal.load_class(None, "/Script/ProjectArco." + component_name)
            component = actor.call_method("AddComponentByClass", args=(component_class, False, unreal.Transform(), False))
            assert component is not None
            for paused in (False, True):
                workforce = component.get_editor_property("m_workers")
                workforce.set_editor_property("bDisabled", paused, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
                # Avoid editor reconstruction deleting this transient test component.
                component.set_editor_property("m_workers", workforce, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
                known, read = adapter.call_method("ReadWorkplace", args=(actor,))
                if not known:
                    interface = unreal.load_class(None, "/Script/ProjectArco.AgentEnterable")
                    unreal.log("WO_ADAPTER_DIAGNOSTIC " + str({
                        "actor": actor.get_class().get_path_name(),
                        "component": component.get_class().get_path_name(),
                        "components": [c.get_class().get_path_name() for c in actor.get_components_by_class(unreal.ActorComponent)],
                        "interface_components": [c.get_class().get_path_name() for c in actor.get_components_by_interface(interface)],
                        "implements": unreal.SystemLibrary.does_implement_interface(component, interface),
                        "direct_read": str(adapter.call_method("ReadComponent", args=(component,))),
                        "found_count": adapter.get_editor_property("FoundCount"),
                    }))
                assert known, f"Known {component_name} workplace rejected"
                assert read.get_editor_property("bDisabled") == paused, "Pause state lost"
                assert component.get_editor_property("m_workers").get_editor_property("bDisabled") == paused
            actor.call_method("AddComponentByClass", args=(component_class, False, unreal.Transform(), False))
            known, _ = adapter.call_method("ReadWorkplace", args=(actor,))
            assert not known, "Ambiguous multiple workplaces must fail closed"
        finally:
            actors.destroy_actor(actor)
    snapshot_class = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_WorkforceSnapshot.BP_WorkforceSnapshot_C")
    for component_name in ("ResourceBuilding", "GranaryResourceBuilding"):
        spawned = []
        try:
            building, neighbor = [actors.spawn_actor_from_class(actor_class, unreal.Vector(0, 0, -100000)) for _ in range(2)]
            spawned.extend((building, neighbor))
            person = actors.spawn_actor_from_class(unreal.load_class(None, "/Script/ProjectArco.Prototype_Agent"), unreal.Vector(0, 0, -100000))
            spawned.append(person)

            def put(obj, name, value):
                obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)

            for number, target in enumerate((building, neighbor), 200):
                put(target, "ID", number)
                put(target, "Health", 100)
                put(target, "isPlayerOwned", True)
            component_class = unreal.load_class(None, "/Script/ProjectArco." + component_name)
            component = building.call_method("AddComponentByClass", args=(component_class, False, unreal.Transform(), False))
            workforce = component.get_editor_property("m_workers")
            assert workforce.import_text("(m_workerSlots=((bIsRequiredToRun=True)))")
            slots = list(workforce.get_editor_property("m_workerSlots"))
            put(slots[0], "Agent", person)
            put(workforce, "m_workerSlots", slots)
            put(component, "m_workers", workforce)
            original = workforce.export_text()
            readable, read = adapter.call_method("ReadComponent", args=(component,))
            assert readable and read.get_editor_property("m_workerSlots")[0].get_editor_property("Agent") == person, "Legacy occupants must remain readable for protection"
            known, _ = adapter.call_method("ReadWorkplace", args=(building,))
            assert not known, f"{component_name} exposes legacy slots but has no native assignable workforce"

            neighbor_component = neighbor.call_method("AddComponentByClass", args=(unreal.load_class(None, "/Script/ProjectArco.Industry"), False, unreal.Transform(), False))
            neighbor_workforce = neighbor_component.get_editor_property("m_workers")
            assert neighbor_workforce.import_text("(m_workerSlots=((bIsRequiredToRun=True)))")
            put(neighbor_component, "m_workers", neighbor_workforce)
            snapshot = unreal.new_object(snapshot_class)
            snapshot.call_method("ResetSnapshot")
            assert not snapshot.call_method("AddBuilding", args=(building,))
            assert snapshot.call_method("AddBuilding", args=(neighbor,)), "Unsupported workplace blocked a supported neighbor"
            assert list(snapshot.get_editor_property("Buildings")) == [neighbor]
            assert person in snapshot.get_editor_property("ProtectedWorkers")
            snapshot.call_method("FinishBuildings")
            for reported in (None, building):
                assert not snapshot.call_method("AddWorker", args=(person, reported)), "Unsupported workplace occupant entered the movable pool"
            assert snapshot.get_editor_property("SnapshotValid"), "Unsupported workplace must not stop the run"
            assert component.get_editor_property("m_workers").export_text() == original, "Unsupported workplace was mutated"
        finally:
            for actor in reversed(spawned):
                actors.destroy_actor(actor)
    unreal.log("WO_WORKPLACE_TESTS_PASS: supported components preserved; native-incompatible resource family excluded with incumbents protected")


run()
