"""Focused compact-panel routing and native-control checks."""
from pathlib import Path
import sys

assert "unreal" in sys.modules or (Path(__file__).resolve().parents[2] / "Content/Mods/WorkerOptimizer/WBP_SettingsPanel.uasset").exists(), "Tabbed settings panel has not been authored"
import unreal
from ui_authoring import font_points
sys.path.insert(0,str(Path(__file__).parent))
from ui_test_fixture import inputs


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda n: unreal.load_class(None, root + n + "." + n + "_C")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    factory = unreal.get_default_object(unreal.load_class(None, "/Script/UMG.WidgetBlueprintLibrary"))
    panel = factory.call_method("Create", args=(world, load("WBP_SettingsPanel"), None))
    assert panel and not panel.get_editor_property("PanelOpen")
    assert panel.get_editor_property('ModeLabel').get_editor_property('font').get_editor_property('size') >= font_points(16)
    assert panel.get_editor_property('KeySelector').get_editor_property('text_style').get_editor_property('font').get_editor_property('size') == font_points(15)
    assert isinstance(panel.get_editor_property('ReserveInput'),unreal.EditableTextBox)
    assert isinstance(panel.get_editor_property('Views'),unreal.WidgetSwitcher)
    assert panel.get_editor_property('GeneralTab').get_editor_property('is_focusable')
    for name in ('StrictChoice','WeightedChoice','AutoOff','AutoDay','Auto5','Auto10','Auto15'):
        surface=panel.get_editor_property(name+'Surface')
        assert isinstance(surface,unreal.Border)
        assert panel.get_editor_property(name).get_parent() == surface
    assert isinstance(panel.get_editor_property('TitleEmblem'),unreal.Image)
    assert panel.call_method('ApplyPanelLayout',args=(1075.0,700.0))
    assert panel.get_editor_property('LayoutWidth') == 1075
    assert not panel.get_editor_property('Narrow')
    for name in ('ReserveHelp','ModeHelp','AutoHelp','HotkeyState'):
        assert panel.get_editor_property(name).get_editor_property('wrap_text_at') == 632
    assert panel.call_method('ApplyPanelLayout',args=(717.0,500.0))
    assert panel.get_editor_property('Narrow')
    assert panel.get_editor_property('GeneralBodySize').get_editor_property('width_override') == 711
    for name in ('ReserveHelp','ModeHelp','AutoHelp','HotkeyState'):
        assert panel.get_editor_property(name).get_editor_property('wrap_text_at') == 663
    scroll = panel.get_editor_property('ContentScroll')
    assert isinstance(scroll, unreal.ScrollBox), 'Short viewports must scroll without shrinking text'
    scrollbar = scroll.get_editor_property('widget_bar_style')
    for name in ('horizontal_background_image','vertical_background_image',
                 'horizontal_top_slot_image','vertical_top_slot_image',
                 'horizontal_bottom_slot_image','vertical_bottom_slot_image'):
        image_size = scrollbar.get_editor_property(name).get_editor_property('image_size')
        zero_size = type(image_size)()
        assert zero_size.import_text('(X=0,Y=0)')
        assert image_size.export_text() == zero_size.export_text(), 'Invisible scrollbar track must not reserve width: ' + name
    assert panel.get_editor_property('PrioritiesHost').get_class() == load('WBP_PrioritiesView')
    assert not panel.call_method("OpenTab", args=("invalid",))
    for name in ("GeneralTab", "PrioritiesTab", "LogbookTab", "ReserveInput", "ReserveMinus", "ReservePlus", "StrictChoice", "WeightedChoice", "AutoOff", "KeySelector", "PrioritiesHost", "HistoryHost"):
        assert panel.get_editor_property(name), name
    for tab in ("general", "priorities", "logbook"):
        assert panel.call_method("OpenTab", args=(tab,))
        assert str(panel.get_editor_property("ActiveTab")) == tab
        assert panel.get_editor_property("PanelOpen")
        active = {'general':'GeneralTab','priorities':'PrioritiesTab','logbook':'LogbookTab'}[tab]
        assert panel.get_editor_property('Views').get_active_widget_index() == {'general':0,'priorities':1,'logbook':2}[tab]
    assert panel.call_method("ClosePanel") and not panel.get_editor_property("PanelOpen")
    assert panel.get_visibility() == unreal.SlateVisibility.COLLAPSED
    assert len(panel.get_editor_property("AutoValues")) == 5
    assert str(panel.get_editor_property("HotkeySlot")) == "WorkerOptimizer_UI_v1"
    controller=unreal.new_object(load('BP_WorkerOptimizer'))
    inputs.call_method('Controller',args=(controller,))
    settings=controller.get_editor_property('Settings')
    model=unreal.new_object(load('BP_SettingsModel'))
    assert model.call_method('InitializeModel',args=(controller,settings,controller.get_editor_property('PolicyCatalog')))
    hotkey=unreal.new_object(load('BP_HotkeyConfig'))
    assert hotkey.call_method('ResetDefaults')
    assert panel.call_method('InitializePanel',args=(controller,model,hotkey,controller.get_editor_property('Logbook')))
    assert panel.call_method('OpenTab',args=('general',))
    reserve_input=panel.get_editor_property('ReserveInput')
    reserve_input.set_text('73')
    assert panel.call_method('RefreshPanel')
    assert str(reserve_input.get_text()) == '73', 'Unrelated presentation refresh must preserve uncommitted reserve text'
    invalid=unreal.InputChord()
    assert invalid.import_text('(Key=None,bShift=False,bCtrl=False,bAlt=False,bCmd=False)')
    assert not panel.call_method('KeyChanged',args=(invalid,))
    assert str(panel.get_editor_property('HotkeyState').get_text()) == str(settings.call_method('Text',args=('invalid_hotkey',)))
    assert panel.call_method('ClosePanel')
    unreal.log("WO_SETTINGS_PANEL_TESTS_PASS: native controls, three tab routes, close state, debounce, five schedules and unchanged hotkey slot; packaged roundtrip and visual acceptance pending")


run()
