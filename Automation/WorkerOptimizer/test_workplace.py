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
    unreal.log("WO_WORKPLACE_TESTS_PASS: null/unknown/ambiguous rejected; three component types, pause flag preserved")


run()
