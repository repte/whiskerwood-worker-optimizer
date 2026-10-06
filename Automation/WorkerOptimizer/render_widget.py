"""Bounded native UMG render matrix using synthetic, unsaved editor fixtures."""
from pathlib import Path
import json
import sys
import time
import unreal
sys.path.insert(0,str(Path(__file__).parent))
from ui_render_fixture import create_inputs, create_host, SAMPLE_NAMES, TYPE_COUNT
from ui_test_fixture import inputs as common_inputs

ROOT = '/Game/Mods/WorkerOptimizer/'
load = lambda name:unreal.load_class(None,ROOT+name+'.'+name+'_C')
OUTPUT = Path(unreal.Paths.project_saved_dir())/'WorkerOptimizerUI'
OUTPUT.mkdir(parents=True,exist_ok=True)
SCALE = 1.25
SIZES = ((1280,720),(1920,1080),(2560,1080))
LANGUAGES = ('de','ja','zh','ko','ru')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
controller = actors.spawn_actor_from_class(load('BP_WorkerOptimizer'),unreal.Vector(0,0,-100000))
controller.set_actor_tick_enabled(False)
host = create_host(world)
widget = host.get_editor_property('Optimizer')
logical_size = host.get_editor_property('LogicalSize')
settings, fixture = create_inputs()
catalog, book, store = (unreal.new_object(load(name)) for name in ('BP_DefinitionCatalog','BP_Logbook','BP_LogbookStore'))
config = unreal.new_object(load('BP_HotkeyConfig'))
config.call_method('ResetDefaults')
manifest = {
    'synthetic_editor_fixture':True,
    'simulated_slate_scale':SCALE,
    'shipping_game_scale_verified':False,
    'native_hud_geometry_verified':False,
    'native_editor_culture_per_frame':True,
    'language_routing':'Transient Text override calls the shipped Localize implementation; native game language switching is not tested.',
    'priority_types':TYPE_COUNT,
    'stored_runs':50,
    'frames':[],
}


def bounds(name, obj):
    # The Python FGeometry query returns zero in this editor despite native paint.
    # Read the retained Slate tree directly and return ordinary reflected scalars.
    rect = unreal.WorkerOptimizerTestSupport.measure_widget_artifact(obj)
    assert rect.z > 0 and rect.w > 0, 'Native widget has no arranged geometry: '+name
    return {'name':name,'x':float(rect.x),'y':float(rect.y),'width':float(rect.z),'height':float(rect.w)}


def font_evidence(name, obj):
    font = obj.get_editor_property('font')
    points = float(font.get_editor_property('size'))
    size_su = points * 4.0 / 3.0
    assert size_su >= 13, 'Font below13 SU: '+name
    resource = font.get_editor_property('font_object')
    return {'name':name,'size_points':points,'size_su':size_su,'font':resource.get_path_name() if resource else 'Slate default/fallback'}


def finish_filter(model):
    for _ in range(TYPE_COUNT*4+64):
        if not model.get_editor_property('Filtering'):
            return
        assert model.call_method('AdvanceFilter')
    raise AssertionError('Bounded synthetic priority filter did not finish')


def render(language,tab,width,height,suffix='',history_stress=False,hud_state=''):
    filename=f'{language}-{tab}-{width}x{height}{suffix}.png'
    native_culture=unreal.InternationalizationLibrary.get_current_culture()
    assert native_culture.split('-')[0]==language, 'Native font/number/date culture differs from fixture language'
    logical_width,logical_height=width/SCALE,height/SCALE
    logical_size.set_width_override(logical_width)
    logical_size.set_height_override(logical_height)
    panel = widget.get_editor_property('PanelHost')
    assert panel.call_method('OpenTab',args=(tab,))
    assert widget.call_method('ApplyLayout',args=(logical_width,logical_height))
    if history_stress:
        fixture.call_method('HistoryStress',args=(panel.get_editor_property('HistoryHost'),'Abgeschlossen'))
    render_started=time.perf_counter()
    # First pass instantiates native virtualized entries; the second captures their layout.
    assert unreal.WorkerOptimizerTestSupport.render_widget_artifact(host,width,height,filename)
    panel.force_layout_prepass()
    assert panel.call_method('ApplyPanelLayout',args=(panel.get_editor_property('LayoutWidth'),panel.get_editor_property('LayoutHeight')))
    priorities = panel.get_editor_property('PrioritiesHost')
    history = panel.get_editor_property('HistoryHost')
    if tab == 'priorities':
        model = widget.get_editor_property('SettingsModel')
        finish_filter(model)
        assert priorities.call_method('RefreshPriorities')
        assert priorities.call_method('ApplyLayout',args=(panel.get_editor_property('LayoutWidth')-48.0,panel.get_editor_property('LayoutHeight')-panel.get_editor_property('HeaderHeight')))
        # UTreeView ignores expansion before its Slate tree exists. The first
        # pass above constructs it; replay the fixture's expanded presentation.
        priorities.get_editor_property('PriorityTree').call_method('ExpandAll')
    assert unreal.WorkerOptimizerTestSupport.render_widget_artifact(host,width,height,filename)
    render_elapsed_ms=(time.perf_counter()-render_started)*1000.0
    regions=[bounds('panel',panel.get_editor_property('PanelRoot')),bounds('title',panel.get_editor_property('PanelTitle'))]
    fonts=[font_evidence('panel-title',panel.get_editor_property('PanelTitle'))]
    virtualization=[]
    badge_text=''
    badge_resource=''
    if hud_state:
        badge=widget.get_editor_property('OutcomeIcon')
        assert badge.get_visibility()==unreal.SlateVisibility.HIT_TEST_INVISIBLE
        resource=badge.get_editor_property('brush').get_editor_property('resource_object')
        badge_resource=resource.get_path_name() if resource else ''
        expected=ROOT+'T_WorkerOptimizerStatus'+hud_state.title()
        assert badge_resource==expected+'.'+expected.rsplit('/',1)[-1], 'Wrong native outcome badge resource'
        regions.extend((bounds('hud-action',widget.get_editor_property('ActionButton')),bounds('hud-badge',badge)))
    if tab == 'general':
        regions.append(bounds('general-body',panel.get_editor_property('ContentScroll')))
        fonts.append(font_evidence('reserve-label',panel.get_editor_property('ReserveLabel')))
    elif tab == 'priorities':
        tree=priorities.get_editor_property('PriorityTree')
        entries=list(tree.call_method('GetDisplayedEntryWidgets'))
        total=len(priorities.get_editor_property('AllItems'))
        assert entries and len(entries)<total, 'TreeView did not instantiate a bounded visible entry set'
        assert any(not entry.get_editor_property('IsCategory') for entry in entries), 'TreeView children delegate did not instantiate a building type'
        regions.append(bounds('priority-tree',tree))
        fonts.extend(font_evidence('priority-'+name,entries[0].get_editor_property(name)) for name in ('Title','Effective'))
        virtualization.append({'widget':'PriorityTree','source_items':total,'displayed_entries':len(entries)})
    else:
        rows=history.get_editor_property('RunRows')
        entries=list(rows.call_method('GetDisplayedEntryWidgets'))
        total=len(history.get_editor_property('RunItems'))
        assert entries and len(entries)<total, 'ListView did not instantiate a bounded visible entry set'
        regions.append(bounds('history-list',rows))
        details=history.get_editor_property('DetailRows')
        detail_entries=list(details.call_method('GetDisplayedEntryWidgets'))
        assert detail_entries, 'Native detail ListView did not instantiate selected-run entries'
        regions.append(bounds('history-details',details))
        virtualization.append({'widget':'RunRows','source_items':total,'displayed_entries':len(entries)})
        virtualization.append({'widget':'DetailRows','source_items':len(history.get_editor_property('DetailItems')),'displayed_entries':len(detail_entries)})
    if history_stress:
        assert len(history.get_editor_property('RunItems'))==500
        assert len({str(item.get_editor_property('RunId')) for item in history.get_editor_property('RunItems')})==500
    record={'file':filename,'language':language,'native_editor_culture':native_culture,'tab':tab,'width':width,'height':height,'regions':regions,'fonts':fonts,'virtualization':virtualization,'elapsed_render_ms':render_elapsed_ms,'history_stress':history_stress,'hud_state':hud_state,'badge_text':badge_text,'badge_resource':badge_resource}
    manifest['frames'].append(record)
    (OUTPUT/'render-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    unreal.log('WO_WIDGET_RENDER_FRAME '+filename+' '+json.dumps(virtualization)+' elapsed_render_ms='+str(round(render_elapsed_ms,2)))


previous_culture=unreal.InternationalizationLibrary.get_current_culture()
try:
    common_inputs.call_method('History',args=(book,store))
    fixture.call_method('EnrichHistory',args=(store,))
    fixture.call_method('SeedController',args=(controller,widget,settings,catalog,book))
    assert widget.call_method('InitializeUI',args=(controller,config))
    fixture.call_method('SeedController',args=(controller,widget,settings,catalog,book))
    assert widget.call_method('ToggleSettings')
    panel=widget.get_editor_property('PanelHost')
    model=widget.get_editor_property('SettingsModel')
    fixture.call_method('ExpandCategories',args=(model,))
    for language in LANGUAGES:
        assert unreal.InternationalizationLibrary.set_current_culture(language,False)
        settings.call_method('SetRenderCulture',args=(language,SAMPLE_NAMES[language]))
        fixture.call_method('SeedCatalog',args=(catalog,SAMPLE_NAMES[language]))
        assert model.call_method('BeginFilter',args=('',))
        finish_filter(model)
        assert panel.call_method('RebuildLabels')
        assert panel.call_method('RefreshGeneral')
        history=panel.get_editor_property('HistoryHost')
        fixture.call_method('HistoryCulture',args=(history,))
        assert history.call_method('InitializeHistory',args=(book,settings))
        assert history.call_method('SelectRun',args=('run-49',))
        for width,height in SIZES:
            for tab in ('general','priorities','logbook'):
                render(language,tab,width,height)
    # Busy is a synthetic presentation state; there is no start/cancel action.
    settings.call_method('SetRenderCulture',args=('de',SAMPLE_NAMES['de']))
    assert unreal.InternationalizationLibrary.set_current_culture('de',False)
    assert panel.call_method('RebuildLabels')
    fixture.call_method('Busy',args=(controller,True))
    assert widget.call_method('RefreshUI')
    render('de','general',1280,720,'-busy')
    fixture.call_method('Busy',args=(controller,False))
    fixture.call_method('Storage',args=(book,'failed'))
    assert widget.call_method('RefreshUI')
    assert history.call_method('InitializeHistory',args=(book,settings))
    assert history.call_method('SelectRun',args=('run-49',))
    render('de','logbook',2560,1080,'-storage-failed')
    render('de','logbook',1920,1080,'-stress-500',history_stress=True)
    for hud_state in ('completed','problems','error','aborted'):
        fixture.call_method('HudOutcome',args=(controller,hud_state))
        assert widget.call_method('RefreshUI')
        render('de','general',1920,1080,'-hud-'+hud_state,hud_state=hud_state)
    assert len(store.get_editor_property('RunId'))==50, 'Rendering changed production retention'
    assert len(manifest['frames'])==52
    unreal.log('WO_WIDGET_RENDER_PASS:52 native Slate frames, three tabs,1280/1920/2560, de/ja/zh/ko/ru, four HUD results, simulated1.25 scale, history500 stress and measured virtualized entry counts; gameplay/culture routing remain separate acceptance')
finally:
    unreal.WorkerOptimizerTestSupport.release_widget_artifact()
    widget.call_method('ShutdownUI')
    host.remove_from_parent()
    actors.destroy_actor(controller)
    assert unreal.InternationalizationLibrary.set_current_culture(previous_culture,False)
