"""Unsaved editor-only native UI fixtures; never run the optimizer or write options."""
from pathlib import Path
import json
import sys
import unreal
sys.path.insert(0, str(Path(__file__).parent))
from ui_authoring import *

TEST_ROOT = '/Game/WorkerOptimizerEditorTests'
CATEGORIES = ('food_process','industry_materials','science','logistics')
TYPE_COUNT = 400
SAMPLE_NAMES = {
    'de':'Grosses Gebaeude der Holzverarbeitung',
    'ja':'\u68ee\u306e\u88fd\u6750\u6240\u3068\u6728\u6750\u52a0\u5de5\u5834',
    'zh':'\u68ee\u6797\u952f\u6728\u5382\u4e0e\u6728\u6750\u52a0\u5de5\u8f66\u95f4',
    'ko':'\uc232\uc18d \uc81c\uc7ac\uc18c\uc640 \ubaa9\uc7ac \uac00\uacf5 \uc791\uc5c5\uc7a5',
    'ru':'\u0411\u043e\u043b\u044c\u0448\u0430\u044f \u043c\u0430\u0441\u0442\u0435\u0440\u0441\u043a\u0430\u044f \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0438 \u0434\u0440\u0435\u0432\u0435\u0441\u0438\u043d\u044b',
}


def create_inputs():
    strings = BP.create(TEST_ROOT, 'BP_RenderPrioritySettings', load('BP_PrioritySettings'))
    BP.add_variable(strings,'RenderLanguage','string')
    BP.add_variable(strings,'SampleTitle','string')
    graphs = {n:BP.add_function_graph(strings,n) for n in ('Text','ResolveLabel','ReadOption','SetRenderCulture')}
    BP.add_function_param(graphs['SetRenderCulture'],'Language','string',True)
    BP.add_function_param(graphs['SetRenderCulture'],'Title','string',True)
    BP.compile_blueprint(strings)
    lang = '(Variables|Default|GetRenderLanguage)'
    localized = lambda key: '(CallFunction|Localize :Key '+key+' :Language '+lang+')'
    code = {
        'Text':'(fn Text (Key) (bind translated '+localized('Key')+') (return translated))',
        'SetRenderCulture':'(fn SetRenderCulture (Language Title) (Variables|Default|SetRenderLanguage Language) (Variables|Default|SetSampleTitle Title))',
        'ResolveLabel':'(fn ResolveLabel (Key StringKey) '+''.join('(if (== Key "'+category+'") (bind translated '+localized('"category.'+category+'"')+') (return translated)) ' for category in CATEGORIES)+' (return StringKey))',
        'ReadOption':'''(fn ReadOption (Context OptionId Fallback)
            (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.reserve") (return "3"))
            (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.category.food_process") (return "4"))
            (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.category.industry_materials") (return "3"))
            (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.type.fixture_0") (return "WorkerOptimizer.ui.priority.4"))
            (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.type.fixture_4") (return "WorkerOptimizer.ui.priority.0"))
            (return Fallback))''',
    }
    with toolset_registry.tool_raising_exceptions():
        for name,source in code.items(): BP.write_graph_dsl(graphs[name],source)
        BP.compile_blueprint(strings,warnings_as_errors=True)
    settings = unreal.new_object(strings.generated_class())
    helper = BP.create(TEST_ROOT,'BP_RenderUIInputs',unreal.Object.static_class())
    declarations = {
        'SeedController': [('Controller',load('BP_WorkerOptimizer')),('Widget',load('WBP_WorkerOptimizer')),('Settings',load('BP_PrioritySettings')),('Catalog',load('BP_DefinitionCatalog')),('Book',load('BP_Logbook'))],
        'SeedCatalog': [('Catalog',load('BP_DefinitionCatalog')),('Title','string')],
        'ExpandCategories': [('Model',load('BP_SettingsModel'))],
        'EnrichHistory': [('Store',load('BP_LogbookStore'))],
        'Busy': [('Controller',load('BP_WorkerOptimizer')),('Enabled','bool')],
        'Storage': [('Book',load('BP_Logbook')),('State','name')],
        'HistoryCulture': [('View',load('WBP_LogbookView'))],
        'HistoryStress': [('View',load('WBP_LogbookView')),('Title','string')],
        'HudOutcome': [('Controller',load('BP_WorkerOptimizer')),('State','name')],
    }
    graphs = {}
    for name,params in declarations.items():
        graph = graphs[name] = BP.add_function_graph(helper,name)
        for param,kind in params:
            if isinstance(kind,str): BP.add_function_param(graph,param,kind,True)
            else: BP.add_object_function_param(graph,param,kind,True)
    BP.compile_blueprint(helper)
    modulo_nodes=[node for node in BP.find_node_types(graphs['SeedCatalog'],'%',[]) if node.startswith('Math|Integer|')]
    assert len(modulo_nodes)==1, modulo_nodes
    mod=lambda divisor:'('+modulo_nodes[0]+' :A i :B '+str(divisor)+')'
    category = f'(select (== {mod(4)} 0) "food_process" (select (== {mod(4)} 1) "industry_materials" (select (== {mod(4)} 2) "science" "logistics")))'
    code = {
        'SeedController':'''(fn SeedController (Controller Widget Settings Catalog Book)
          (Class|BPWorkerOptimizer|SetContext :self Controller :Context Controller)
          (Class|BPWorkerOptimizer|SetInitialized :self Controller :Initialized true)
          (Class|BPWorkerOptimizer|SetSettings :self Controller :Settings Settings)
          (Class|BPWorkerOptimizer|SetPolicyCatalog :self Controller :PolicyCatalog Catalog)
          (Class|BPWorkerOptimizer|SetLogbook :self Controller :Logbook Book)
          (Class|BPPrioritySettings|SetPolicyKeysReady :self Settings :PolicyKeysReady true)
          (Class|WBPWorkerOptimizer|SetTexts :self Widget :Texts Settings))''',
        'SeedCatalog':'(fn SeedCatalog (Catalog Title) '+''.join('(Utilities|Array|Clear (Class|BPDefinitionCatalog|Get'+name+' :self Catalog)) ' for name in ('Types','Categories','StringKeys'))+f'''(for i (range {TYPE_COUNT})
          (Utilities|Array|Add (Class|BPDefinitionCatalog|GetTypes :self Catalog) (Utilities|String|Append :A "fixture_" :B (Utilities|String|ToString(Integer) i)))
          (Utilities|Array|Add (Class|BPDefinitionCatalog|GetCategories :self Catalog) {category})
          (Utilities|Array|Add (Class|BPDefinitionCatalog|GetStringKeys :self Catalog) (Utilities|String|Append :A Title :B (Utilities|String|Append :A " " :B (Utilities|String|ToString(Integer) i)))))
          (Class|BPDefinitionCatalog|SetCatalogDone :self Catalog :CatalogDone true))''',
        'ExpandCategories':'(fn ExpandCategories (Model) '+''.join('(Utilities|Array|AddUnique (Class|BPSettingsModel|GetExpandedCategories :self Model) "'+category+'") ' for category in CATEGORIES)+')',
        'Busy':'(fn Busy (Controller Enabled) (Class|BPWorkerOptimizer|SetRunActive :self Controller :RunActive Enabled))',
        'Storage':'(fn Storage (Book State) (Class|BPLogbook|SetPersistenceStatus :self Book :PersistenceStatus State))',
        'HistoryCulture':'(fn HistoryCulture (View) (Class|WBPLogbookView|SetHasStatusCache :self View :HasStatusCache false))',
    }
    # The actual history remains 50 stored rows. Only synthetic known fields are filled.
    numbers = {'Reserve':'3','ConfirmedFires':mod(3),'ConfirmedHires':mod(5), 'ActiveSupportedBuildings':'120','PausedBuildings':'2','UnsupportedBuildings':'1','ConfirmedMinimumCrews':'16','FreeEligibleResidents':'7', 'StartedYear':'2026','StartedMonth':'10','StartedDay':'5','StartedHour':mod(24),'StartedMinute':mod(60),'StartedSecond':'0','StartedMillisecond':'0'}
    known = ('CountsKnown','StaffingKnown','WorkersKnown','ReserveKnown','ReserveSatisfied','StrictMode','ConfirmationWindowKnown')
    code['EnrichHistory'] = '(fn EnrichHistory (Store) (for i (range 50) '+''.join('(Utilities|Array|Add (Class|BPLogbookStore|Get'+name+' :self Store) '+value+') ' for name,value in numbers.items())+''.join('(Utilities|Array|Add (Class|BPLogbookStore|Get'+name+' :self Store) true) ' for name in known)+'))'
    items = '(Class|WBPLogbookView|GetRunItems :self View)'
    rows = '(Class|WBPLogbookView|GetRunRows :self View)'
    set_items = native(graphs['HistoryStress'],'SetListItems','ListView')
    item_set = lambda field,value: '(Class|BPUIListItem|Set'+field+' :self item :'+field+' '+value+')'
    code['HistoryStress'] = f'''(fn HistoryStress (View Title)
      (Utilities|Array|Clear {items})
      (for i (range 500)
        (bind item (Game|ConstructObjectfromClass :Class "{ROOT}/BP_UIListItem.BP_UIListItem_C" :self View))
        {item_set('Owner','View')} {item_set('Kind','"run"')}
        {item_set('RunId','(Utilities|String|Append :A "render-stress-" :B (Utilities|String|ToString(Integer) i))')}
        {item_set('Revision','(Class|WBPLogbookView|GetCachedRevision :self View)')}
        {item_set('Index','i')} {item_set('Status','"completed"')}
        {item_set('Title',text('Title'))}
        {item_set('Subtitle',text('"05.10.2026 12:30"'))}
        {item_set('Detail',text('(Utilities|String|Append :A "Synthetic " :B (Utilities|String|ToString(Integer) i))'))}
        {item_set('Count',mod(17))} {item_set('Known','true')}
        (Utilities|Array|Add {items} item))
      ({set_items} :self {rows} :InListItems {items}))'''
    code['HudOutcome'] = f'''(fn HudOutcome (Controller State)
      (bind report (Game|ConstructObjectfromClass :Class "{ROOT}/BP_RunReport.BP_RunReport_C" :self Controller))
      (Class|BPRunReport|SetEndedAt :self report :EndedAt (Math|DateTime|MakeDateTime :Year 2026 :Month 10 :Day 6 :Hour 12 :Minute 30 :Second 0 :Millisecond 0))
      (Class|BPRunReport|SetCountsKnown :self report :CountsKnown true)
      (Class|BPRunReport|SetConfirmedChanges :self report :ConfirmedChanges 17)
      (Class|BPRunReport|SetReportDone :self report :ReportDone true)
      (if (== State "problems")
        (Utilities|Array|Add (Class|BPRunReport|GetGroupReasons :self report) "observation_unavailable")
        (Utilities|Array|Add (Class|BPRunReport|GetGroupTypes :self report) "fixture_0")
        (Utilities|Array|Add (Class|BPRunReport|GetGroupCounts :self report) 1))
      (Class|BPWorkerOptimizer|SetCompletedReport :self Controller :CompletedReport report)
      (Class|BPWorkerOptimizer|SetRunActive :self Controller :RunActive false)
      (Class|BPWorkerOptimizer|SetReportPending :self Controller :ReportPending false)
      (Class|BPWorkerOptimizer|SetRunDone :self Controller :RunDone true)
      (Class|BPWorkerOptimizer|SetRunSucceeded :self Controller :RunSucceeded (or (== State "completed") (== State "problems")))
      (Class|BPWorkerOptimizer|SetFailureCode :self Controller :FailureCode (select (== State "error") "invalid_plan" (select (== State "aborted") "cancelled" "None"))))'''
    with toolset_registry.tool_raising_exceptions():
        for name,source in code.items(): BP.write_graph_dsl(graphs[name],source)
        BP.compile_blueprint(helper,warnings_as_errors=True)
    return settings, unreal.new_object(helper.generated_class())


def create_host(world):
    tools = unreal.get_default_object(unreal.UMGToolSet)
    call = lambda name,*args:tools.call_method(name,args=args)
    bp = call('CreateWidgetBlueprint',TEST_ROOT,'WBP_RenderHost',unreal.UserWidget.static_class())
    assert bp
    for item in call('GetWidgets',bp).widgets:
        if not item.parent: call('RemoveWidget',bp,item.widget)
    def add(kind,name,parent=None):
        item = call('AddWidget',bp,kind.static_class() if not isinstance(kind,unreal.Class) else kind,name,parent,-1)
        assert item.widget
        call('ToggleWidgetAsVariable',bp,item.widget,True)
        return item.widget
    scale = add(unreal.ScaleBox,'DpiScale')
    scale.set_stretch(unreal.Stretch.USER_SPECIFIED)
    scale.set_user_specified_scale(1.25)
    size = add(unreal.SizeBox,'LogicalSize',scale)
    child = add(load('WBP_WorkerOptimizer'),'Optimizer',size)
    BP.compile_blueprint(bp,warnings_as_errors=True)
    factory = unreal.get_default_object(unreal.load_class(None,'/Script/UMG.WidgetBlueprintLibrary'))
    return factory.call_method('Create',args=(world,bp.generated_class(),None))
