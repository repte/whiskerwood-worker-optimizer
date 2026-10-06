"""Four bounded native UMG frames with transient, unsaved UI fixtures."""
from pathlib import Path
import json
import sys
import unreal

# Blueprint authoring node names are culture-sensitive; switch to German after setup.
assert unreal.InternationalizationLibrary.get_current_culture().split('-')[0] == 'en', 'Launch this render probe with -culture=en'
sys.path.insert(0, str(Path(__file__).parent))
from ui_render_fixture import create_inputs, create_host, SAMPLE_NAMES, TYPE_COUNT
from ui_test_fixture import inputs as common_inputs

ROOT = '/Game/Mods/WorkerOptimizer/'
load = lambda name: unreal.load_class(None, ROOT + name + '.' + name + '_C')
helper = unreal.WorkerOptimizerTestSupport
output = Path(unreal.Paths.project_saved_dir()) / 'WorkerOptimizerUI'
output.mkdir(parents=True, exist_ok=True)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
controller = actors.spawn_actor_from_class(load('BP_WorkerOptimizer'), unreal.Vector(0, 0, -100000))
controller.set_actor_tick_enabled(False)
host = create_host(world)
widget = host.get_editor_property('Optimizer')
settings, fixture = create_inputs()
catalog, book, store = (unreal.new_object(load(name)) for name in ('BP_DefinitionCatalog', 'BP_Logbook', 'BP_LogbookStore'))
config = unreal.new_object(load('BP_HotkeyConfig'))
config.call_method('ResetDefaults')
previous_culture = unreal.InternationalizationLibrary.get_current_culture()
manifest = {'synthetic_editor_fixture': True, 'shipping_game_verified': False, 'frames': []}


def bounds(name, obj):
    rect = helper.measure_widget_artifact(obj)
    assert rect.z > 0 and rect.w > 0, 'Unarranged native widget: ' + name
    return {'name': name, 'x': float(rect.x), 'y': float(rect.y), 'width': float(rect.z), 'height': float(rect.w)}


def finish_filter(model):
    for _ in range(TYPE_COUNT * 4 + 64):
        if not model.get_editor_property('Filtering'):
            return
        assert model.call_method('AdvanceFilter')
    raise AssertionError('Synthetic priority filter exceeded its bound')


def render(tab, width, height, dpi):
    filename = f'uifix-{tab}-{width}x{height}-dpi{dpi}.png'
    host.get_editor_property('DpiScale').set_user_specified_scale(dpi)
    logical_size = host.get_editor_property('LogicalSize')
    logical_size.set_width_override(width / dpi)
    logical_size.set_height_override(height / dpi)
    panel = widget.get_editor_property('PanelHost')
    assert panel.call_method('OpenTab', args=(tab,))
    assert widget.call_method('ApplyViewportLayout', args=(float(width), float(height), dpi))
    if tab == 'priorities':
        model = widget.get_editor_property('SettingsModel')
        assert model.call_method('BeginFilter', args=('Grosses',))
        finish_filter(model)
        assert panel.get_editor_property('PrioritiesHost').call_method('RefreshPriorities')
    assert helper.render_widget_artifact(host, width, height, filename)
    panel.force_layout_prepass()
    assert panel.call_method('ApplyPanelLayout', args=(panel.get_editor_property('LayoutWidth'), panel.get_editor_property('LayoutHeight')))
    history = panel.get_editor_property('HistoryHost')
    priorities = panel.get_editor_property('PrioritiesHost')
    if tab == 'logbook':
        runs = history.get_editor_property('RunRows')
        items = list(history.get_editor_property('RunItems'))
        assert helper.broadcast_list_item_event(runs, 'BP_OnItemClicked', items[0], True)
        assert str(history.get_editor_property('SelectedRunId')) == 'run-49'
        assert history.get_editor_property('DetailItems'), 'Native history click did not populate details'
        assert helper.broadcast_list_item_event(runs, 'BP_OnItemSelectionChanged', items[1], True)
        assert str(history.get_editor_property('SelectedRunId')) == 'run-48'
        assert helper.broadcast_list_item_event(runs, 'BP_OnItemClicked', items[0], True)
    elif tab == 'priorities':
        tree = priorities.get_editor_property('PriorityTree')
        entries = list(tree.call_method('GetDisplayedEntryWidgets'))
        category = next(entry for entry in entries if entry.get_editor_property('IsCategory'))
        assert category.get_editor_property('CategoryExpander').get_visibility() == unreal.SlateVisibility.VISIBLE
        item = category.get_editor_property('Item')
        assert unreal.UserListEntryLibrary.is_list_item_expanded(category), 'Search must expose matching buildings'
        assert str(category.get_editor_property('CategoryExpanderText').get_text()) == '\u25bc'
        tree.call_method('SetItemExpansion', args=(item, False))
        assert not unreal.UserListEntryLibrary.is_list_item_expanded(category)
        assert not model.get_editor_property('Filtering'), 'Native collapse must not start an unchanged expansion filter'
        assert str(category.get_editor_property('CategoryExpanderText').get_text()) == '\u25b6', 'Native category collapse must update its visible glyph'
        assert category.call_method('ExpandClicked')
        finish_filter(model)
        assert priorities.call_method('RefreshPriorities')
    assert helper.render_widget_artifact(host, width, height, filename)
    panel_rect = bounds('panel', panel.get_editor_property('PanelRoot'))
    assert panel_rect['x'] >= -1 and panel_rect['y'] >= -1
    assert panel_rect['x'] + panel_rect['width'] <= width + 1, 'Panel exceeds physical viewport width'
    assert panel_rect['y'] + panel_rect['height'] <= height + 1, 'Panel exceeds physical viewport height'
    effective_scale = dpi * float(widget.get_editor_property('LayoutPopupScale'))
    title_layout_scale = float(helper.measure_widget_layout_scale(panel.get_editor_property('PanelTitle')))
    assert abs(title_layout_scale - max(1.0, dpi)) < 0.001, ('Native title glyphs must rasterize at the compensated layout scale', tab, dpi, title_layout_scale)
    record = {'file': filename, 'tab': tab, 'width': width, 'height': height, 'dpi': dpi, 'effective_popup_scale': effective_scale, 'title_layout_scale': title_layout_scale, 'regions': [panel_rect]}
    if tab == 'logbook':
        runs = history.get_editor_property('RunRows')
        details = history.get_editor_property('DetailRows')
        list_rect, detail_rect = bounds('history-list', runs), bounds('history-details', details)
        separator_rect = bounds('history-separator', history.get_editor_property('HistorySeparator'))
        record['regions'].extend([list_rect, detail_rect, separator_rect])
        if width == 1920:
            assert detail_rect['x'] >= list_rect['x'] + list_rect['width'] - 1, 'Wide history details must sit beside the list'
            assert abs(separator_rect['width'] - effective_scale) < 1
        else:
            assert detail_rect['y'] >= list_rect['y'] + list_rect['height'] - 1, 'Narrow history details must sit below the list'
            assert abs(separator_rect['height'] - effective_scale) < 1
        entries = list(runs.call_method('GetDisplayedEntryWidgets'))
        cancelled = next(entry for entry in entries if str(entry.get_editor_property('RunId')) == 'run-49')
        title = cancelled.get_editor_property('TitleText')
        assert str(title.get_text()) == 'Abgebrochen'
        title_rect = bounds('cancelled-status', title)
        time_header = bounds('timestamp-header', history.get_editor_property('TimestampHeaderCell'))
        time_cell = bounds('timestamp-cell', cancelled.get_editor_property('SubtitleTextCell'))
        count_header = bounds('changes-header', history.get_editor_property('ChangesHeaderCell'))
        count_cell = bounds('changes-cell', cancelled.get_editor_property('CountTextCell'))
        unreal.log('WO_UI_FIX_COLUMNS ' + json.dumps({'header': count_header, 'row': count_cell, 'right_padding': history.get_editor_property('RunHeaderBackground').get_editor_property('padding').right}))
        assert abs(time_header['x'] - time_cell['x']) <= 1, 'Timestamp header does not align with history rows'
        assert abs(count_header['x'] - count_cell['x']) <= 1, 'Changes header does not align with history rows'
        assert abs(count_header['x'] + count_header['width'] - count_cell['x'] - count_cell['width']) <= 1, 'Changes column right edge does not align with history rows'
        measured = helper.measure_text_width(title, 'Abgebrochen')
        assert title_rect['width'] / effective_scale + 1 >= measured, 'Abgebrochen does not fit its native text area'
        assert list(details.call_method('GetDisplayedEntryWidgets')), 'Selected run has no native detail entries'
        record['cancelled_status'] = {'measured_width_su': measured, 'available_width_su': title_rect['width'] / effective_scale}
        record['regions'].extend([title_rect, time_header, time_cell, count_header, count_cell])
    elif tab == 'priorities':
        tree = priorities.get_editor_property('PriorityTree')
        entries = list(tree.call_method('GetDisplayedEntryWidgets'))
        assert any(not entry.get_editor_property('IsCategory') for entry in entries), 'Category expander did not display building rows'
        category = next(entry for entry in entries if entry.get_editor_property('IsCategory'))
        record['regions'].extend([bounds('priority-tree', tree), bounds('category-expander', category.get_editor_property('CategoryExpander'))])
        record['displayed_entries'] = len(entries)
    else:
        record['regions'].append(bounds('general-body', panel.get_editor_property('ContentScroll')))
        right_limit = panel_rect['x'] + panel_rect['width'] - 6 * effective_scale
        for name in ('ReserveHelp', 'ModeHelp', 'AutoHelp', 'StrictChoiceSurface'):
            content_rect = bounds(name, panel.get_editor_property(name))
            assert content_rect['x'] + content_rect['width'] <= right_limit + 1, 'General content overlaps scrollbar gutter: ' + name
            record['regions'].append(content_rect)
    manifest['frames'].append(record)
    (output / 'uifix-evidence.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    unreal.log('WO_UI_FIX_RENDER_FRAME ' + filename)


try:
    assert unreal.InternationalizationLibrary.set_current_culture('de', False)
    settings.call_method('SetRenderCulture', args=('de', SAMPLE_NAMES['de']))
    common_inputs.call_method('History', args=(book, store))
    fixture.call_method('EnrichHistory', args=(store,))
    fixture.call_method('SeedCatalog', args=(catalog, SAMPLE_NAMES['de']))
    fixture.call_method('SeedController', args=(controller, widget, settings, catalog, book))
    assert widget.call_method('InitializeUI', args=(controller, config))
    fixture.call_method('SeedController', args=(controller, widget, settings, catalog, book))
    assert widget.call_method('ToggleSettings')
    panel = widget.get_editor_property('PanelHost')
    assert panel.get_editor_property('HistoryHost').get_editor_property('RunHeaderBackground').get_editor_property('padding').right == 22, 'Embedded history template is stale'
    assert panel.get_editor_property('PrioritiesHost').get_editor_property('PriorityTree').get_editor_property('selection_mode') == unreal.SelectionMode.SINGLE, 'Embedded priority template is stale'
    model = widget.get_editor_property('SettingsModel')
    assert model.call_method('BeginFilter', args=('',))
    finish_filter(model)
    assert panel.call_method('RebuildLabels')
    assert panel.call_method('RefreshGeneral')
    history = panel.get_editor_property('HistoryHost')
    fixture.call_method('HistoryCulture', args=(history,))
    assert history.call_method('InitializeHistory', args=(book, settings))
    for tab, width, height, dpi in [('logbook', 1920, 1080, .7), ('logbook', 1280, 720, .45), ('priorities', 1280, 720, .45), ('general', 1280, 720, .45)]:
        render(tab, width, height, dpi)
    assert len(store.get_editor_property('RunId')) == 50
    assert len(manifest['frames']) == 4
    unreal.log('WO_UI_FIX_RENDER_PASS: four native frames, native title layout scale, aligned history columns, native history click and selection, category expansion, measured panel bounds')
finally:
    helper.release_widget_artifact()
    widget.call_method('ShutdownUI')
    host.remove_from_parent()
    actors.destroy_actor(controller)
    assert unreal.InternationalizationLibrary.set_current_culture(previous_culture, False)
