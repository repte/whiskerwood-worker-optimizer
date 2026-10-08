"""Exercise compiled UMG visibility against the native gameplay HUD guard."""

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


ROOT = "/Game/Mods/WorkerOptimizer/"
load = lambda name: unreal.load_class(None, ROOT + name + "." + name + "_C")
put = lambda obj, key, value: obj.set_editor_property(
    key, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def create_widget():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    factory = unreal.get_default_object(unreal.load_class(None, "/Script/UMG.WidgetBlueprintLibrary"))
    widget = factory.call_method("Create", args=(world, load("WBP_WorkerOptimizer"), None))
    assert widget, "Native optimizer widget creation failed"
    return widget


def require_graph(asset, name):
    graphs = {str(graph.get_name()) for graph in BP.list_graphs(unreal.load_asset(ROOT + asset))}
    assert name in graphs, "Gameplay visibility function is missing: " + name


def test_initial_visibility():
    widget = create_widget()
    try:
        assert widget.get_visibility() == unreal.SlateVisibility.COLLAPSED, "Assignment icon must start hidden before gameplay is ready"
        require_graph("WBP_WorkerOptimizer", "ApplyGameplayVisibility")
        assert not widget.get_editor_property("GameplayVisible")
        button_visible = widget.get_editor_property("ButtonVisible")
        widget.call_method("ApplyGameplayVisibility", args=(True,))
        assert widget.get_editor_property("GameplayVisible")
        assert widget.get_visibility() == unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE
        widget.call_method("ApplyGameplayVisibility", args=(False,))
        assert not widget.get_editor_property("GameplayVisible")
        assert widget.get_visibility() == unreal.SlateVisibility.COLLAPSED
        assert widget.get_editor_property("ButtonVisible") == button_visible, "HUD visibility must not change the manual icon preference"
        assert not widget.get_editor_property("Controller"), "Visibility must not create an optimizer"
        widget.call_method("ApplyGameplayVisibility", args=(True,))
        assert widget.call_method("ShutdownUI")
        assert widget.get_editor_property("Closed")
        assert not widget.get_editor_property("GameplayVisible")
        assert widget.get_visibility() == unreal.SlateVisibility.COLLAPSED
        assert not widget.call_method("ApplyGameplayVisibility", args=(True,)), "A closed widget must refuse to reappear"
        assert not widget.call_method("RefreshUI")
        assert widget.get_visibility() == unreal.SlateVisibility.COLLAPSED
    finally:
        widget.remove_from_parent()


def test_native_hud():
    require_graph("BP_MapLoad", "HudAllowsDisplay")
    require_graph("BP_MapLoad", "SyncGameplayVisibility")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    session = actors.spawn_actor_from_class(load("BP_MapLoad"), unreal.Vector(0, 0, -100000))
    widget = create_widget()
    controller = None
    try:
        system = unreal.get_default_object(unreal.load_class(None, "/Script/Engine.KismetSystemLibrary"))
        system.call_method("SetObjectPropertyByName", args=(session, "UI", widget))
        assert session.get_editor_property("UI") == widget
        native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
        transform = unreal.Transform()
        gameplay = unreal.get_default_object(unreal.GameplayStatics)
        controller = gameplay.call_method("BeginDeferredActorSpawnFromClass", args=(
            session, native("PlayerController_Play"), transform,
            unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None,
            unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
        controller = gameplay.call_method("FinishSpawningActor", args=(
            controller, transform, unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
        assert controller, "Native player-controller fixture creation failed"
        hud = unreal.new_object(native("PlayHud"))

        def check(h=hud, p=controller):
            return session.call_method("HudAllowsDisplay", args=(h, p))

        def player(key, value):
            state = controller.get_editor_property("m_state")
            put(state, key, value)
            put(controller, "m_state", state)

        def state(key, value, nested=None):
            target = hud.get_editor_property("m_hudState")
            field = f"{key}={'True' if value else 'False'}"
            assert target.import_text(f"({nested}=({field}))" if nested else f"({field})")

        assert not check(None, controller)
        assert not check(hud, None)
        assert not check(None, None)
        put(hud, "m_uiHasFadedIn", True)
        player("m_showHud", True)
        player("m_dev_hideAllHud", False)
        player("m_showReplayMenu", False)
        player("activeArcoView", None)
        state("showHudRoot", True, "sectionVisibilities")
        state("showSaving", False)
        state("victoryPending", False)
        assert check(), "Normal gameplay must show the assignment icon"
        state("IsPaused", True, "TimeHudState")
        assert check(), "Simulation pause must keep manual assignment available"
        state("isPausedByEod", True, "TimeHudState")
        state("eodPending", True)
        assert check(), "Day-end pause must not hide the assignment icon"
        state("victoryPending", True)
        assert check(), "An available victory action is not an open menu"
        state("showSaving", True)
        assert not check(), "Saving overlay must hide the assignment icon"
        state("showSaving", False)
        for key, blocked, allowed in (("m_showHud", False, True),
                                     ("m_dev_hideAllHud", True, False),
                                     ("m_showReplayMenu", True, False)):
            player(key, blocked)
            assert not check(), "Missing player guard: " + key
            player(key, allowed)
            assert check(), "Restored player guard remains hidden: " + key
        view = unreal.new_object(native("ArcoView"))
        player("activeArcoView", view)
        assert not check(), "An open game view must hide the assignment icon"
        player("activeArcoView", None)
        state("showHudRoot", False, "sectionVisibilities")
        assert not check(), "Hidden HUD root must hide the assignment icon"
        state("showHudRoot", True, "sectionVisibilities")
        put(hud, "m_uiHasFadedIn", False)
        assert not check(), "Loading or fading HUD must hide the assignment icon"
        put(hud, "m_uiHasFadedIn", True)
        assert check()
        widget.call_method("ApplyGameplayVisibility", args=(True,))
        assert not session.call_method("SyncGameplayVisibility"), "Editor world is not a gameplay session"
        assert widget.get_visibility() == unreal.SlateVisibility.COLLAPSED, "World guard must hide an existing widget"
        assert not widget.get_editor_property("GameplayVisible")
        widget.call_method("ApplyGameplayVisibility", args=(True,))
        assert widget.get_visibility() == unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE, "A hidden widget must remain restorable"
    finally:
        session.call_method("Shutdown")
        widget.remove_from_parent()
        if controller and unreal.SystemLibrary.is_valid(controller):
            actors.destroy_actor(controller)
        if unreal.SystemLibrary.is_valid(session):
            actors.destroy_actor(session)


def test_hidden_run_lifecycle():
    require_graph("WBP_WorkerOptimizer", "ApplyGameplayVisibility")
    require_graph("BP_MapLoad", "SyncGameplayVisibility")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []

    def spawn(name, owner=None):
        obj = actors.spawn_actor_from_class(load(name), unreal.Vector(0, 0, -100000))
        spawned.append(obj)
        if owner:
            obj.call_method("SetOwner", args=(owner,))
        return obj

    session = spawn("BP_MapLoad")
    widget = create_widget()
    try:
        api = unreal.new_object(unreal.load_class(None, "/Script/SystemCore.ModAPI"))
        assert session.call_method("AttachAPI", args=(api,))
        assert unreal.WorkerOptimizerTestSupport.broadcast_loading_finished(api)
        controller = spawn("BP_WorkerOptimizer", session)
        bridge = spawn("BP_ActionBridge", session)
        view = unreal.new_object(load("WBP_ActionContext"))
        assert session.call_method("InstallSession", args=(controller, bridge, view))
        config = unreal.new_object(load("BP_HotkeyConfig"))
        config.call_method("ResetDefaults")
        assert session.call_method("InstallUI", args=(widget, config))
        assert widget.get_visibility() == unreal.SlateVisibility.COLLAPSED, "Initialization must not reveal UI in an editor world"
        preference = (widget.get_editor_property("ButtonVisible"),
                      config.get_editor_property("Dirty"),
                      config.call_method("ExportChord").export_text())
        assert preference[0]
        assert controller.get_editor_property("Settings").call_method("FinishPolicyKeys")
        widget.call_method("ApplyGameplayVisibility", args=(True,))
        assert widget.call_method("RefreshUI")
        assert not controller.get_editor_property("RunActive"), "Showing the icon must not start assignment"
        assert controller.call_method("BeginRun"), "Fixture must start a real optimizer run"
        report = controller.get_editor_property("CurrentReport")
        fields = ("RunActive", "RunDone", "RunSucceeded", "Phase", "RunTrigger",
                  "FailureCode", "ReportPending", "ReplanCount", "AppliedCount", "QueuedCount")

        def run_state():
            return tuple(controller.get_editor_property(name) for name in fields)

        active = run_state()
        assert active[0] and controller.call_method("IsActorTickEnabled")
        widget.call_method("ApplyGameplayVisibility", args=(False,))
        for _ in range(3):
            assert widget.call_method("RefreshUI"), "Hidden initialized UI is still healthy"
            assert session.call_method("PumpUI"), "PumpUI reports UI health, not its visibility"
            assert widget.get_visibility() == unreal.SlateVisibility.COLLAPSED, "Refresh and polling must not reopen hidden UI"
            assert not widget.get_editor_property("GameplayVisible")
            assert run_state() == active, "Hiding and refreshing must not restart, cancel, or alter active assignment"
            assert controller.get_editor_property("CurrentReport") == report, "Visibility must preserve the same run identity"
            assert controller.call_method("IsActorTickEnabled"), "Hidden UI must not disable the optimizer's tick"
            assert preference == (widget.get_editor_property("ButtonVisible"),
                                  config.get_editor_property("Dirty"),
                                  config.call_method("ExportChord").export_text())
        widget.call_method("ApplyGameplayVisibility", args=(True,))
        assert widget.get_visibility() == unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE
        assert run_state() == active
        assert not session.call_method("SyncGameplayVisibility")
        assert widget.get_visibility() == unreal.SlateVisibility.COLLAPSED
        assert run_state() == active
        # The real editor boundary fails configuration, but still executes while hidden.
        controller.call_method("ReceiveTick", args=(0.016,))
        assert controller.get_editor_property("RunDone")
        assert not controller.get_editor_property("RunActive")
        assert not controller.get_editor_property("RunSucceeded")
        assert str(controller.get_editor_property("FailureCode")) == "configuration_unavailable", "Hidden work must reach its normal editor-native boundary, not cancellation"
        assert controller.get_editor_property("CurrentReport") == report
        assert widget.call_method("RefreshUI")
        assert session.call_method("PumpUI")
        assert widget.get_visibility() == unreal.SlateVisibility.COLLAPSED, "Completion notification must not reveal hidden UI"
        assert session.call_method("Shutdown")
        assert widget.get_editor_property("Closed")
        assert not widget.get_editor_property("GameplayVisible")
        assert widget.get_visibility() == unreal.SlateVisibility.COLLAPSED
        assert not widget.call_method("ApplyGameplayVisibility", args=(True,))
        assert not widget.call_method("RefreshUI")
        assert not session.call_method("PumpUI")
        assert widget.get_visibility() == unreal.SlateVisibility.COLLAPSED
    finally:
        if unreal.SystemLibrary.is_valid(session):
            session.call_method("Shutdown")
        widget.remove_from_parent()
        for obj in reversed(spawned):
            if unreal.SystemLibrary.is_valid(obj):
                actors.destroy_actor(obj)


def run():
    failures = []
    for test in (test_initial_visibility, test_native_hud, test_hidden_run_lifecycle):
        try:
            test()
            unreal.log("WO_GAMEPLAY_VISIBILITY_PASS " + test.__name__)
        except AssertionError as error:
            failures.append(test.__name__ + ": " + str(error))
            unreal.log_warning("WO_GAMEPLAY_VISIBILITY_FAIL " + failures[-1])
    assert not failures, "; ".join(failures)
    unreal.log("WO_GAMEPLAY_VISIBILITY_TESTS_PASS: compiled widget and native HUD guards, hidden-run progress, preferences, healthy polling and teardown")


run()
