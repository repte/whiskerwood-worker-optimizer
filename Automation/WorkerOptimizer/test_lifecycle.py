"""Verify compiled map-load ownership, delegate and shutdown guards."""

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    cls = load("BP_MapLoad")
    assert cls, "Production map-load hook does not exist"
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    api = unreal.new_object(unreal.load_class(None, "/Script/SystemCore.ModAPI"))
    event = api.get_editor_property("onLoadingFinished")
    bp = unreal.load_asset(root + "BP_MapLoad")
    for function, node_name in (("BindDay", "BindEventtoOnDayStart"), ("UnbindDay", "UnbindEventfromOnDayStart")):
        graph = BP.get_graph(bp, function)
        source = BP.read_graph_dsl(graph)
        assert node_name in source and "GetAPI" in source, "Bind/unbind must use the owned API"
        delegates = [node for node in BP.find_nodes(graph) if isinstance(node, unreal.K2Node_CreateDelegate)]
        assert len(delegates) == 1 and BP.get_create_event_function(delegates[0]) == "OnDayStart"
    assert "UnbindDay" in BP.read_graph_dsl(BP.get_graph(bp, "Shutdown"))
    broadcast = lambda: unreal.WorkerOptimizerTestSupport.broadcast_loading_finished(api)
    assert not unreal.WorkerOptimizerTestSupport.broadcast_loading_finished(None)

    def spawn(kind, owner=None):
        obj = actors.spawn_actor_from_class(kind, unreal.Vector(0, 0, -100000))
        spawned.append(obj)
        if owner:
            obj.call_method("SetOwner", args=(owner,))
        return obj

    try:
        foreign_listener = spawn(cls)
        event.add_function(foreign_listener, "OnLoaded")
        primary = spawn(cls)
        assert not primary.call_method("CreateSession"), "Must wait for load completion"
        assert primary.call_method("AttachAPI", args=(api,))
        assert primary.call_method("AttachAPI", args=(api,)), "Repeated binding must be harmless"
        assert event.contains_function(primary, "OnLoaded")
        assert not primary.get_editor_property("Loaded")
        assert not primary.get_editor_property("Controller")
        duplicate = spawn(cls)
        assert not duplicate.call_method("AttachAPI", args=(api,))
        assert not event.contains_function(duplicate, "OnLoaded")
        assert not duplicate.get_editor_property("Primary")
        assert str(duplicate.get_editor_property("FailureCode")) == "duplicate_instance"

        # Broadcast the actual native delegate, not just the target Blueprint function.
        assert broadcast()
        assert primary.get_editor_property("Loaded")
        assert not duplicate.get_editor_property("Loaded")
        assert not primary.get_editor_property("Ready")
        assert str(primary.get_editor_property("FailureCode")) == "player_unavailable"
        assert not foreign_listener.get_editor_property("Loaded")
        assert broadcast()
        assert not primary.get_editor_property("Controller"), "Repeated load event must not create a second session"

        controller = spawn(load("BP_WorkerOptimizer"), primary)
        bridge = spawn(load("BP_ActionBridge"), primary)
        view = unreal.new_object(load("WBP_ActionContext"))
        alien = spawn(load("BP_WorkerOptimizer"))
        assert not primary.call_method("InstallSession", args=(alien, bridge, view)), "Do not adopt foreign actors"
        assert not primary.call_method("InstallSession", args=(controller, bridge, None))
        assert primary.call_method("InstallSession", args=(controller, bridge, view))
        assert primary.get_editor_property("Ready")
        assert controller.get_editor_property("Initialized")
        logbook = primary.get_editor_property("Logbook")
        assert logbook and controller.get_editor_property("Logbook") == logbook, "History service belongs to this session"
        assert logbook.get_editor_property("Context") == primary
        assert controller.get_editor_property("Context") == primary
        assert not controller.get_editor_property("RunActive"), "Loading never starts optimization"
        assert primary.call_method("PollAutomatic") is False, "Missing editor-native calendar/pause inputs cannot trigger work"
        primary.call_method("OnDayStart", args=(99,))
        assert not controller.get_editor_property("RunActive")
        assert bridge.get_editor_property("BridgeReady")
        assert bridge.get_editor_property("ActionContext") == view
        assert not bridge.call_method("IsActorTickEnabled")
        snapshot = controller.get_editor_property("Snapshot")
        assert primary.call_method("InstallSession", args=(controller, bridge, view))
        assert controller.get_editor_property("Snapshot") == snapshot
        assert not primary.call_method("InstallSession", args=(alien, bridge, view))
        assert broadcast()
        assert primary.get_editor_property("Controller") == controller
        assert not controller.get_editor_property("RunActive")

        duplicate.call_method("Shutdown")
        assert event.contains_function(primary, "OnLoaded"), "A duplicate must not unbind the primary"
        primary.call_method("Shutdown")
        assert logbook.get_editor_property("Closed"), "Unload closes storage after terminal report publication"
        assert not event.contains_function(primary, "OnLoaded")
        assert event.contains_function(foreign_listener, "OnLoaded"), "Never unbind another mod's event handler"
        assert primary.get_editor_property("ShuttingDown")
        assert not primary.get_editor_property("Ready")
        assert not primary.get_editor_property("Controller")
        assert not primary.get_editor_property("Bridge")
        assert not primary.get_editor_property("ActionView")
        assert not unreal.SystemLibrary.is_valid(controller)
        assert not unreal.SystemLibrary.is_valid(bridge)
        assert unreal.SystemLibrary.is_valid(alien), "Only destroy session-owned actors"
        assert broadcast()
        assert not primary.get_editor_property("Controller")
        assert not primary.call_method("AttachAPI", args=(api,))
        assert not primary.call_method("CreateSession")
        assert primary.call_method("Shutdown"), "Teardown is idempotent"

        replacement = spawn(cls)
        assert replacement.call_method("AttachAPI", args=(api,)), "A torn-down primary no longer owns the world"
        replacement.call_method("Shutdown")
        unavailable = spawn(cls)
        unavailable.call_method("ReceiveBeginPlay")
        assert str(unavailable.get_editor_property("FailureCode")) == "mod_api_unavailable"
        assert not unavailable.get_editor_property("Loaded")
        unavailable.call_method("Shutdown")
        unreal.log("WO_LIFECYCLE_TESTS_PASS: native load delegate broadcast, one primary per world, delayed session creation, owned controller/bridge/view, no automatic optimization, repeated events, foreign-object rejection, scoped unbinding and teardown; native game widget creation remains shipping-only")
    finally:
        if 'foreign_listener' in locals():
            event.remove_function(foreign_listener, "OnLoaded")
        for obj in reversed(spawned):
            if unreal.SystemLibrary.is_valid(obj):
                if isinstance(obj, unreal.Actor) and obj.get_class() == cls:
                    obj.call_method("Shutdown")
                actors.destroy_actor(obj)


run()
