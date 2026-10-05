"""Inspect actual UMG styles and slot sizing after native rendering."""

import unreal

bp = unreal.load_asset("/Game/Mods/WorkerOptimizer/WBP_WorkerOptimizer")
umg = unreal.get_default_object(unreal.UMGToolSet)
for item in umg.call_method("GetWidgets", args=(bp,)).widgets:
    widget = item.widget
    unreal.log("WO_WIDGET_STYLE " + str(item.widget_name) + " " + str(widget.get_class().get_name()))
    if isinstance(widget, unreal.Button):
        unreal.log("WO_WIDGET_STYLE button=" + widget.get_editor_property("widget_style").export_text())
    if isinstance(widget, unreal.Image):
        unreal.log("WO_WIDGET_STYLE image=" + widget.get_editor_property("brush").export_text())
    if isinstance(widget, unreal.InputKeySelector):
        unreal.log("WO_WIDGET_STYLE keyfont=" + widget.get_editor_property("text_style").export_text())
    if item.slot and isinstance(item.slot, unreal.ButtonSlot):
        unreal.log("WO_WIDGET_STYLE padding=" + item.slot.get_editor_property("padding").export_text())
unreal.log("WO_WIDGET_STYLE_COMPLETE")
