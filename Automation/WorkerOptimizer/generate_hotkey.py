"""Generate isolated native SaveGame preferences for a freely selectable chord."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
bp = unreal.load_asset(ROOT + "/BP_HotkeyConfig")
if bp is None:
    bp = BP.create(ROOT, "BP_HotkeyConfig", unreal.SaveGame.static_class())
chord_struct = unreal.load_object(None, "/Script/Slate.InputChord")
assert chord_struct
existing = set(BP.list_variables(bp))
if "VisibilityChord" not in existing:
    BP.add_struct_variable(bp, "VisibilityChord", chord_struct)
for name, kind in (("Dirty", "bool"), ("ReleaseGate", "bool"), ("FailureCode", "name")):
    if name not in existing:
        BP.add_variable(bp, name, kind)
definitions = {
    "HasObject": [("Object", unreal.Object.static_class())], "ResetDefaults": [], "ExportChord": [],
    "ValidChord": [("Chord", chord_struct)], "ApplyChord": [("Chord", chord_struct)],
    "MatchesModifiers": [(name, "bool") for name in ("Shift", "Control", "Alt", "Command")],
    "ConsumeKey": [(name, "bool") for name in ("Pressed", "Held", "Shift", "Control", "Alt", "Command")],
    "PollKey": [("Player", unreal.PlayerController.static_class())],
    "ValidSlot": [("Slot", "string")], "SaveSettings": [("Slot", "string")], "LoadSettings": [("Slot", "string")],
}
graphs = {}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
for name, params in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
    if name not in existing_graphs:
        for param, kind in params:
            if isinstance(kind, str):
                BP.add_function_param(graphs[name], param, kind, True)
            elif kind == chord_struct:
                BP.add_struct_function_param(graphs[name], param, kind, True)
            else:
                BP.add_object_function_param(graphs[name], param, kind, True)
        if name == "ExportChord":
            BP.add_struct_function_param(graphs[name], "Chord", chord_struct, False)
        else:
            BP.add_function_param(graphs[name], "Result", "bool", False)
BP.compile_blueprint(bp)


def g(name):
    return f"(Variables|Default|Get{name})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def down(key):
    return f'(Game|Player|IsInputKeyDown :self Player :Key "{key}")'


def modifier(name):
    # Press and release may arrive in the same frame for a short chord.
    def active(key):
        return f'(or {down(key)} (Game|Player|WasInputKeyJustPressed :self Player :Key "{key}"))'
    return f'(or {active("Left" + name)} {active("Right" + name)})'


code = {}
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))"""
code["ResetDefaults"] = f"""(fn ResetDefaults ()
    {put('VisibilityChord', '(Utilities|Struct|MakeInputChord :Key "O" :bCtrl true :bAlt true)')}
    {put('Dirty', 'false')} {put('ReleaseGate', 'false')} {put('FailureCode', '"None"')} (return true))"""
code["ExportChord"] = f"""(fn ExportChord () (return {g('VisibilityChord')}))"""
code["ValidChord"] = """(fn ValidChord (Chord)
    (bind (key shift ctrl alt cmd) (Utilities|Struct|BreakInputChord Chord))
    (if (not (Input|Key|IsValidKey key)) (return false))
    (if (not (Input|Key|IsKeyboardKey key)) (return false))
    (if (Input|Key|IsModifierKey key) (return false))
    (bind (escape es ec ea em) (Utilities|Struct|BreakInputChord (Utilities|Struct|MakeInputChord :Key "Escape")))
    (if (== key escape) (return false))
    (return true))"""
code["ApplyChord"] = f"""(fn ApplyChord (Chord)
    (bind valid (CallFunction|ValidChord :Chord Chord))
    (if (not valid) {put('FailureCode', '"invalid_hotkey"')} (return false))
    {put('VisibilityChord', 'Chord')} {put('Dirty', 'true')} {put('ReleaseGate', 'true')}
    {put('FailureCode', '"None"')} (return true))"""
code["MatchesModifiers"] = f"""(fn MatchesModifiers (Shift Control Alt Command)
    (bind (key wantShift wantCtrl wantAlt wantCmd) (Utilities|Struct|BreakInputChord {g('VisibilityChord')}))
    (return (and (and (== Shift wantShift) (== Control wantCtrl)) (and (== Alt wantAlt) (== Command wantCmd)))))"""
code["ConsumeKey"] = f"""(fn ConsumeKey (Pressed Held Shift Control Alt Command)
    (if {g('ReleaseGate')}
      (if (not Held) {put('ReleaseGate', 'false')}) (return false))
    (if (not Pressed) (return false))
    (bind valid (CallFunction|ValidChord :Chord {g('VisibilityChord')}))
    (if (not valid) (return false))
    (bind matched (CallFunction|MatchesModifiers :Shift Shift :Control Control :Alt Alt :Command Command))
    (return matched))"""
code["PollKey"] = f"""(fn PollKey (Player)
    (if (not (CallFunction|HasObject :Object Player)) (return false))
    (bind valid (CallFunction|ValidChord :Chord {g('VisibilityChord')}))
    (if (not valid) (return false))
    (bind (key shift ctrl alt cmd) (Utilities|Struct|BreakInputChord {g('VisibilityChord')}))
    (bind matched (CallFunction|ConsumeKey :Pressed (Game|Player|WasInputKeyJustPressed :self Player :Key key)
      :Held (Game|Player|IsInputKeyDown :self Player :Key key)
      :Shift {modifier('Shift')} :Control {modifier('Control')} :Alt {modifier('Alt')} :Command {modifier('Command')}))
    (return matched))"""
code["ValidSlot"] = """(fn ValidSlot (Slot)
    (if (or (<= (Utilities|String|Len Slot) 16) (> (Utilities|String|Len Slot) 100)) (return false))
    (if (not (Utilities|String|StartsWith :SourceString Slot :InPrefix "WorkerOptimizer_")) (return false))
    (if (or (Utilities|String|Contains :SearchIn Slot :Substring "/")
      (or (Utilities|String|Contains :SearchIn Slot :Substring "\\\\") (Utilities|String|Contains :SearchIn Slot :Substring ".."))) (return false))
    (return true))"""
code["SaveSettings"] = f"""(fn SaveSettings (Slot)
    (bind validSlot (CallFunction|ValidSlot :Slot Slot))
    (if (not validSlot) {put('FailureCode', '"invalid_hotkey_slot"')} (return false))
    (bind valid (CallFunction|ValidChord :Chord {g('VisibilityChord')}))
    (if (not valid) {put('FailureCode', '"invalid_hotkey"')} (return false))
    (bind saved (SaveGame|SaveGametoSlot :SaveGameObject self :SlotName Slot :UserIndex 0))
    (if (not saved) {put('FailureCode', '"hotkey_save_failed"')} (return false))
    {put('Dirty', 'false')} {put('FailureCode', '"None"')} (return true))"""
code["LoadSettings"] = f"""(fn LoadSettings (Slot)
    (CallFunction|ResetDefaults)
    (bind validSlot (CallFunction|ValidSlot :Slot Slot))
    (if (not validSlot) {put('FailureCode', '"invalid_hotkey_slot"')} (return false))
    (bind exists (SaveGame|DoesSaveGameExist :SlotName Slot :UserIndex 0))
    (if (not exists) (return true))
    (bind loaded (SaveGame|LoadGamefromSlot :SlotName Slot :UserIndex 0))
    (bind typed (Utilities|Casting|CastToBP_HotkeyConfig :Object loaded)
      (:CastFailed {put('FailureCode', '"invalid_hotkey_file"')} (return false))
      (:then
        (bind chord (CallFunction|ExportChord :self typed))
        (bind applied (CallFunction|ApplyChord :Chord chord))
        (if (not applied) (return false))
        {put('Dirty', 'false')} {put('ReleaseGate', 'false')} (return true))))"""
for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_HOTKEY_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-Hotkey.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_HOTKEY_GENERATED")
exec(Path(__file__).with_name("test_hotkey.py").read_text(encoding="utf-8"))
