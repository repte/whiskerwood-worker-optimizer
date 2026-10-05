"""Exercise the actual saved chord configuration and visibility input matching."""

import itertools
import uuid
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_HotkeyConfig.BP_HotkeyConfig_C")
    assert cls, "Production hotkey configuration does not exist"
    config = unreal.new_object(cls)
    assert config.call_method("ResetDefaults")
    original = config.call_method("ExportChord").export_text()
    assert "Key=O" in original
    assert config.call_method("MatchesModifiers", args=(False, True, True, False))
    assert not config.call_method("PollKey", args=(None,))
    bp = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_HotkeyConfig")
    polling = BP.get_node_infos(BP.find_nodes(BP.get_graph(bp, "PollKey")))
    assert sum("WasInputKeyJustPressed" in n.type_id for n in polling) >= 9, "Short chords must retain modifier presses for this frame"

    def chord(key, modifiers=(False, False, False, False)):
        value = unreal.InputChord()
        fields = ','.join(f'{field}={str(flag)}' for field, flag in zip(('bShift', 'bCtrl', 'bAlt', 'bCmd'), modifiers))
        assert value.import_text(f'(Key={key},{fields})')
        return value

    for flags in itertools.product((False, True), repeat=4):
        binding = chord("K", flags)
        assert config.call_method("ApplyChord", args=(binding,))
        assert config.get_editor_property("Dirty")
        for observed in itertools.product((False, True), repeat=4):
            assert config.call_method("MatchesModifiers", args=observed) == (flags == observed)
    before = config.call_method("ExportChord").export_text()
    for key in ("None", "LeftMouseButton", "Gamepad_FaceButton_Bottom", "LeftShift", "RightControl", "Escape"):
        assert not config.call_method("ApplyChord", args=(chord(key),)), key
        assert config.call_method("ExportChord").export_text() == before
    assert config.call_method("ApplyChord", args=(chord("F9", (True, False, False, False)),))
    assert not config.call_method("ConsumeKey", args=(True, True, True, False, False, False)), "Rebinding key stays suppressed while held"
    assert not config.call_method("ConsumeKey", args=(False, False, True, False, False, False))
    assert config.call_method("ConsumeKey", args=(True, True, True, False, False, False))
    assert not config.call_method("ConsumeKey", args=(False, True, True, False, False, False)), "Holding must not repeat the toggle"
    assert not config.call_method("ConsumeKey", args=(True, True, True, True, False, False)), "Extra modifier is a different chord"
    for name in ("", "MainSave", "WorkerOptimizer_", "WorkerOptimizer_../outside", "WorkerOptimizer_sub/file", "WorkerOptimizer_sub\\file"):
        assert not config.call_method("ValidSlot", args=(name,))
        assert not config.call_method("SaveSettings", args=(name,))

    slot = "WorkerOptimizer_Test_" + uuid.uuid4().hex
    assert not unreal.GameplayStatics.does_save_game_exist(slot, 0)
    try:
        assert config.call_method("LoadSettings", args=(slot,)), "Missing config uses valid defaults"
        assert config.call_method("ExportChord").export_text() == original
        assert not config.get_editor_property("Dirty")
        binding = chord("F9", (True, False, False, False))
        assert config.call_method("ApplyChord", args=(binding,))
        assert config.call_method("SaveSettings", args=(slot,))
        assert not config.get_editor_property("Dirty")
        fresh = unreal.new_object(cls)
        assert fresh.call_method("LoadSettings", args=(slot,))
        assert fresh.call_method("ExportChord").export_text() == binding.export_text()
        assert not fresh.get_editor_property("Dirty")
        assert unreal.GameplayStatics.delete_game_in_slot(slot, 0)
        # Wrong-class preferences fail visibly and retain a usable default chord.
        wrong_bp = BP.create("/Game/WorkerOptimizerTests", "BP_WrongPreferences_" + uuid.uuid4().hex, unreal.SaveGame.static_class())
        BP.compile_blueprint(wrong_bp)
        wrong = unreal.new_object(wrong_bp.generated_class())
        assert unreal.GameplayStatics.save_game_to_slot(wrong, slot, 0)
        assert not fresh.call_method("LoadSettings", args=(slot,))
        assert fresh.call_method("ExportChord").export_text() == original
        assert str(fresh.get_editor_property("FailureCode")) == "invalid_hotkey_file"
    finally:
        if unreal.GameplayStatics.does_save_game_exist(slot, 0):
            assert unreal.GameplayStatics.delete_game_in_slot(slot, 0)
    unreal.log("WO_HOTKEY_TESTS_PASS: free keyboard chords, exact 256 modifier combinations, invalid/mouse/gamepad/modifier rejection, unchanged binding on failure, namespace guards, real native save/load roundtrip, defaults and wrong-class fallback; unique project test slot removed")


run()
