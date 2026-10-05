"""Read native UI/input/save signatures and game UI assets for the mod widget."""

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

bp = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_PrioritySettings")
graph = BP.get_graph(bp, "ReadPriority")
suffixes = ("MakeInputChord", "BreakInputChord", "MakeLiteralKey", "IsValidKey", "IsKeyboardKey", "IsModifierKey",
            "WasInputKeyJustPressed", "IsInputKeyDown", "SaveGametoSlot", "LoadGamefromSlot", "DoesSaveGameExist",
            "DeleteGameinSlot", "GetKeyDisplayName", "GetInputChordDisplayName", "SetVisibility", "SetToolTipText",
            "SetText", "IsSelectingKey", "GetIsSelectingKey", "SetSelectedKey", "GetEffectingButton")
for node in BP.find_node_types(graph, "", []):
    if node.rsplit("|", 1)[-1].lower() in {n.lower() for n in suffixes}:
        pins = BP.get_node_type_pins(graph, node)
        unreal.log("WO_UI_NODE " + node + " in=" + str([(p.name, p.type_id) for p in pins.input_pins])
                   + " out=" + str([(p.name, p.type_id) for p in pins.output_pins]))
registry = unreal.AssetRegistryHelpers.get_asset_registry()
for asset in registry.get_assets_by_path("/Game", recursive=True):
    path = str(asset.package_name)
    if str(asset.asset_class_path.asset_name) in ("Texture2D", "MaterialInstanceConstant") and any(
            token in path.lower() for token in ("worker", "whisker", "close", "settings", "gear", "icon", "refresh")):
        unreal.log("WO_UI_MEDIA " + path)
unreal.log("WO_UI_INSPECTION_COMPLETE")
