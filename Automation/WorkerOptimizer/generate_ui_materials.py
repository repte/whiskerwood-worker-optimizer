"""Generate a native UI shader animation; no Blueprint Tick or runtime helper."""
from pathlib import Path
import runpy
import sys

import unreal

sys.path.insert(0, str(Path(__file__).parent))
from ui_authoring import ROOT, color

NAME = "M_WorkerOptimizerBusy"
SPINNER_CODE = """float2 p = UV * 2 - 1;
float r = length(p);
float ring = smoothstep(.68, .76, r) * (1 - smoothstep(.92, 1, r));
float phase = frac(atan2(p.y, p.x) / 6.2831853 + 1 - T * 1.25);
return ring * (.12 + .88 * smoothstep(.05, 1, phase));"""

material = unreal.load_asset(ROOT + "/" + NAME)
if material is None:
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        NAME, ROOT, unreal.Material, unreal.MaterialFactoryNew())
assert isinstance(material, unreal.Material), NAME
material.set_editor_property("material_domain", unreal.MaterialDomain.MD_UI)
material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
library = unreal.MaterialEditingLibrary
# The native bulk-delete iterates the collection it mutates; snapshot first.
for expression in list(library.get_material_expressions(material)):
    library.delete_material_expression(material, expression)
assert library.get_num_material_expressions(material) == 0

uv = library.create_material_expression(material, unreal.MaterialExpressionTextureCoordinate, -600, -100)
clock = library.create_material_expression(material, unreal.MaterialExpressionTime, -600, 100)
opacity = library.create_material_expression(material, unreal.MaterialExpressionCustom, -300, 0)
tint = library.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, -300, -200)
assert all((uv, clock, opacity, tint))
clock.set_editor_property("ignore_pause", True)
clock.set_editor_property("override_period", True)
clock.set_editor_property("period", 0.8)
inputs = []
for name in ("UV", "T"):
    material_input = unreal.CustomInput()
    material_input.set_editor_property("input_name", name)
    inputs.append(material_input)
opacity.set_editor_property("inputs", inputs)
opacity.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
opacity.set_editor_property("code", SPINNER_CODE)
opacity.set_editor_property("description", "Worker Optimizer native busy ring")
tint.set_editor_property("constant", color("run"))
assert library.connect_material_expressions(uv, "", opacity, "UV")
assert library.connect_material_expressions(clock, "", opacity, "T")
assert library.connect_material_property(tint, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
assert library.connect_material_property(opacity, "", unreal.MaterialProperty.MP_OPACITY)
errors = library.recompile_material(material)
assert not errors, errors
assert unreal.EditorAssetLibrary.save_loaded_asset(material)
runpy.run_path(str(Path(__file__).with_name("test_ui_materials.py")), run_name="__main__")
unreal.log("WO_UI_MATERIALS_GENERATED")
