"""Verify the authored shader graph and presentation-only generation contract."""
from pathlib import Path
import sys


def run_source():
    folder = Path(__file__).parent
    source = (folder / "generate_ui_materials.py").read_text(encoding="utf-8")
    for required in ("MaterialDomain.MD_UI", "BlendMode.BLEND_TRANSLUCENT", '"ignore_pause", True',
                     "MaterialExpressionTime", "MP_EMISSIVE_COLOR", "MP_OPACITY", "recompile_material(material)", 'color("run")'):
        assert required in source, required
    for forbidden in ("EventTick", "SetTimer", "WorkerOptimizerUIAuthoring", "WorkerOptimizerTestSupport"):
        assert forbidden not in source, forbidden
    assert "unreal.CustomInput()" in source
    assert "CustomInput(input_name=" not in source
    assert "delete_all_material_expressions" not in source
    assert "list(library.get_material_expressions(material))" in source
    assert "get_num_material_expressions(material) == 0" in source
    required_assets = ("BP_UIListItem", "WBP_PrioritiesView", "WBP_HistoryRow", "WBP_HistoryDetailRow", "M_WorkerOptimizerBusy")
    for name in ("test_package_setup.py", "Test-Package.ps1"):
        manifest = (folder / name).read_text(encoding="utf-8")
        assert all(asset in manifest for asset in required_assets), name
    package = (folder / "prepare_package.py").read_text(encoding="utf-8")
    assert "generate_ui_materials.py" not in package
    assert package.index("test_ui_materials.py") < package.index("test_package_setup.py")
    assert "WO_UI_MATERIALS_READY" in package
    build = (folder / "Build-Mod.ps1").read_text(encoding="utf-8")
    assert "generate_" not in build
    markers = ("WO_PRIORITIES_VIEW_TESTS_PASS", "WO_UI_DESIGN_CONTRACT_PASS",
               "WO_UI_NOTIFICATIONS_NATIVE_PASS", "WO_UI_MATERIALS_TESTS_PASS")
    test_mod = (folder / "Test-Mod.ps1").read_text(encoding="utf-8")
    assert all(marker in test_mod for marker in markers)
    print("WO_UI_MATERIALS_SOURCE_PASS")


def run_native():
    import unreal
    material = unreal.load_asset("/Game/Mods/WorkerOptimizer/M_WorkerOptimizerBusy")
    assert isinstance(material, unreal.Material)
    assert material.get_editor_property("material_domain") == unreal.MaterialDomain.MD_UI
    assert material.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_TRANSLUCENT
    library = unreal.MaterialEditingLibrary
    expressions = library.get_material_expressions(material)
    assert library.get_num_material_expressions(material) == len(expressions) == 4, [type(expression).__name__ for expression in expressions]
    clocks = [expression for expression in expressions if isinstance(expression, unreal.MaterialExpressionTime)]
    assert len(clocks) == 1
    assert clocks[0].get_editor_property("ignore_pause")
    assert clocks[0].get_editor_property("override_period")
    assert abs(clocks[0].get_editor_property("period") - 0.8) < 0.0001
    opacity = library.get_material_property_input_node(material, unreal.MaterialProperty.MP_OPACITY)
    assert isinstance(opacity, unreal.MaterialExpressionCustom)
    assert opacity.get_editor_property("output_type") == unreal.CustomMaterialOutputType.CMOT_FLOAT1
    assert [str(item.get_editor_property("input_name")) for item in opacity.get_editor_property("inputs")] == ["UV", "T"]
    assert "atan2" in opacity.get_editor_property("code")
    tint = library.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    assert isinstance(tint, unreal.MaterialExpressionConstant3Vector)
    sys.path.insert(0, str(Path(__file__).parent))
    from ui_authoring import color
    expected = color("run")
    actual = tint.get_editor_property("constant")
    assert all(abs(getattr(actual, channel) - getattr(expected, channel)) < 0.00001 for channel in ("r", "g", "b"))
    unreal.log("WO_UI_MATERIALS_TESTS_PASS")


if __name__ == "__main__":
    run_source()
    if "unreal" in sys.modules:
        run_native()
