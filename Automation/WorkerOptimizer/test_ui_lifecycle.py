"""Verify session-owned UI initialization, polling and teardown without game input."""

import unreal


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []

    def spawn(name, owner=None):
        obj = actors.spawn_actor_from_class(load(name), unreal.Vector(0, 0, -100000))
        spawned.append(obj)
        if owner:
            obj.call_method("SetOwner", args=(owner,))
        return obj

    session = spawn("BP_MapLoad")
    try:
        assert not session.call_method("InstallUI", args=(None, None)), "Unready session rejects UI"
        api = unreal.new_object(unreal.load_class(None, "/Script/SystemCore.ModAPI"))
        assert session.call_method("AttachAPI", args=(api,))
        assert unreal.WorkerOptimizerTestSupport.broadcast_loading_finished(api)
        controller = spawn("BP_WorkerOptimizer", session)
        bridge = spawn("BP_ActionBridge", session)
        view = unreal.new_object(load("WBP_ActionContext"))
        assert session.call_method("InstallSession", args=(controller, bridge, view))
        factory = unreal.get_default_object(unreal.load_class(None, "/Script/UMG.WidgetBlueprintLibrary"))
        widget = factory.call_method("Create", args=(world, load("WBP_WorkerOptimizer"), None))
        config = unreal.new_object(load("BP_HotkeyConfig"))
        config.call_method("ResetDefaults")
        assert not session.call_method("InstallUI", args=(None, config))
        assert session.call_method("InstallUI", args=(widget, config))
        assert session.get_editor_property("UI") == widget
        assert session.get_editor_property("Hotkey") == config
        assert session.call_method("InstallUI", args=(widget, config))
        alien_config = unreal.new_object(load("BP_HotkeyConfig"))
        assert not session.call_method("InstallUI", args=(widget, alien_config))
        for _ in range(3):
            assert session.call_method("PumpUI")
            assert not controller.get_editor_property("RunActive"), "Polling cannot start optimization"
        assert widget.call_method("ToggleButton")
        assert session.call_method("PumpUI")
        assert not widget.get_editor_property("ButtonVisible"), "Polling must continue while controls are hidden"
        tick = unreal.get_default_object(load("BP_MapLoad")).get_editor_property("primary_actor_tick")
        assert tick.get_editor_property("start_with_tick_enabled")
        assert tick.get_editor_property("tick_even_when_paused")
        assert session.call_method("Shutdown")
        assert widget.get_editor_property("Closed")
        assert not session.get_editor_property("UI")
        assert not session.get_editor_property("Hotkey")
        assert not session.call_method("PumpUI")
        assert not widget.call_method("ClickAction")
    finally:
        if unreal.SystemLibrary.is_valid(session):
            session.call_method("Shutdown")
        for obj in reversed(spawned):
            if unreal.SystemLibrary.is_valid(obj):
                actors.destroy_actor(obj)
    unreal.log("WO_UI_LIFECYCLE_TESTS_PASS: guarded session UI, no autorun, repeated polls, hidden polling, pause-enabled tick, teardown")


run()
