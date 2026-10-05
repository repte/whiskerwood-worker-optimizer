"""Render the shipped UMG tree at desktop and compact viewport sizes."""

import unreal

root = "/Game/Mods/WorkerOptimizer/"
load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
controller = actors.spawn_actor_from_class(load("BP_WorkerOptimizer"), unreal.Vector(0, 0, -100000))
bridge = actors.spawn_actor_from_class(load("BP_ActionBridge"), unreal.Vector(0, 0, -100000))
view = unreal.new_object(load("WBP_ActionContext"))
config = unreal.new_object(load("BP_HotkeyConfig"))
config.call_method("ResetDefaults")
factory = unreal.get_default_object(unreal.load_class(None, "/Script/UMG.WidgetBlueprintLibrary"))
widget = factory.call_method("Create", args=(world, load("WBP_WorkerOptimizer"), None))
try:
    assert bridge.call_method("InitializeBridge", args=(view,))
    assert controller.call_method("Initialize", args=(controller, bridge))
    assert widget.call_method("InitializeUI", args=(controller, config))
    for width, height in ((3440, 1440), (1920, 1080), (1280, 720), (800, 600), (400, 300)):
        assert widget.call_method("ApplyLayout", args=(float(width), float(height)))
        assert unreal.WorkerOptimizerTestSupport.render_widget_artifact(widget, width, height, f"idle-{width}.png")
        assert widget.call_method("ToggleSettings")
        assert unreal.WorkerOptimizerTestSupport.render_widget_artifact(widget, width, height, f"settings-{width}.png")
        assert widget.call_method("ToggleSettings")
    assert widget.call_method("ClickAction")
    assert unreal.WorkerOptimizerTestSupport.render_widget_artifact(widget, 1280, 720, "busy-1280.png")
    assert widget.call_method("ClickAction")
    assert unreal.WorkerOptimizerTestSupport.render_widget_artifact(widget, 1280, 720, "cancelled-1280.png")
    assert config.call_method("ApplyChord", args=(config.call_method("ExportChord"),))
    assert not config.call_method("SaveSettings", args=("invalid-slot",))
    assert widget.call_method("RefreshUI")
    assert unreal.WorkerOptimizerTestSupport.render_widget_artifact(widget, 1280, 720, "hotkey-unsaved-1280.png")
    unreal.log("WO_WIDGET_RENDER_PASS: native Slate tree rendered at 3440x1440, 1920x1080, 1280x720, 800x600 and 400x300 logical units")
finally:
    widget.call_method("ShutdownUI")
    widget.remove_from_parent()
    controller.call_method("Shutdown")
    actors.destroy_actor(controller)
    actors.destroy_actor(bridge)
