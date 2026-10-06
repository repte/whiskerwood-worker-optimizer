"""Focused immutable logbook projection and bounded detail-page checks."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import sys

assert "unreal" in sys.modules or (Path(__file__).resolve().parents[2] / "Content/Mods/WorkerOptimizer/WBP_LogbookView.uasset").exists(), "Logbook view has not been authored"
import unreal
from ui_authoring import font_points
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
sys.path.insert(0, str(Path(__file__).parent))
from ui_test_fixture import inputs


def native_history_events(factory, world, load):
    """Exercise the delegates emitted by ListView, rather than handler functions."""
    book, store, texts = (unreal.new_object(load(name)) for name in ('BP_Logbook', 'BP_LogbookStore', 'BP_PrioritySettings'))
    inputs.call_method('History', args=(book, store))
    probe = factory.call_method('Create', args=(world, load('WBP_LogbookView'), None))
    helper = unreal.get_default_object(unreal.load_class(None, '/Script/WorkerOptimizerEditor.WorkerOptimizerTestSupport'))
    assert helper.call_method('RealizeWidgetArtifact', args=(probe,))
    assert probe.call_method('InitializeHistory', args=(book, texts))
    runs = probe.get_editor_property('RunRows')
    first, second = list(probe.get_editor_property('RunItems'))[:2]
    assert helper.call_method('BroadcastListItemEvent', args=(runs, 'BP_OnItemClicked', first, True))
    assert str(probe.get_editor_property('SelectedRunId')) == 'run-49', 'Native row click must open historical details'
    assert probe.get_editor_property('DetailItems'), 'Native row click must populate the details list'
    assert helper.call_method('BroadcastListItemEvent', args=(runs, 'BP_OnItemSelectionChanged', second, True))
    assert str(probe.get_editor_property('SelectedRunId')) == 'run-48', 'Native keyboard selection must replace historical details'
    assert all(str(item.get_editor_property('RunId')) == 'run-48' for item in probe.get_editor_property('DetailItems'))
    assert helper.call_method('BroadcastListItemEvent', args=(runs, 'BP_OnItemClicked', first, True))
    fixture = BP.create('/Game/WorkerOptimizerEditorTests', 'BP_HistoryGroupInputs', unreal.Object.static_class())
    graph = BP.add_function_graph(fixture, 'FillGroup')
    BP.add_object_function_param(graph, 'Store', load('BP_LogbookStore'), True)
    timeout_graph = BP.add_function_graph(fixture, 'SetTimeout')
    BP.add_object_function_param(timeout_graph, 'Store', load('BP_LogbookStore'), True)
    BP.add_object_function_param(timeout_graph, 'Book', load('BP_Logbook'), True)
    BP.compile_blueprint(fixture)
    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(graph, '''(fn FillGroup (Store)
          (for i (range 50) (Utilities|Array|Add (Class|BPLogbookStore|GetGroupReasonsLengths :self Store) (select (== i 49) 1 0)))
          (Utilities|Array|Add (Class|BPLogbookStore|GetGroupReasons :self Store) "no_workers")
          (Utilities|Array|Add (Class|BPLogbookStore|GetGroupTypes :self Store) "None")
          (Utilities|Array|Add (Class|BPLogbookStore|GetGroupCounts :self Store) 3)
          (Utilities|Array|Add (Class|BPLogbookStore|GetGroupStarts :self Store) 0)
          (Utilities|Array|Add (Class|BPLogbookStore|GetGroupIdCounts :self Store) 0))''')
        BP.write_graph_dsl(timeout_graph, '''(fn SetTimeout (Store Book)
          (Utilities|Array|SetArrayElem :TargetArray (Class|BPLogbookStore|GetOutcome :self Store) :Index 49 :Item "failed")
          (Utilities|Array|SetArrayElem :TargetArray (Class|BPLogbookStore|GetFailure :self Store) :Index 49 :Item "action_timeout")
          (Class|BPLogbook|SetHistoryRevision :self Book :HistoryRevision 2))''')
        BP.compile_blueprint(fixture, warnings_as_errors=True)
    group_inputs = unreal.new_object(fixture.generated_class())
    group_inputs.call_method('FillGroup', args=(store,))
    assert probe.call_method('BuildDetails')
    group = next(item for item in probe.get_editor_property('DetailItems') if str(item.get_editor_property('Kind')) == 'group')
    assert helper.call_method('BroadcastListItemEvent', args=(probe.get_editor_property('DetailRows'), 'BP_OnItemClicked', group, True))
    assert probe.get_editor_property('SelectedGroup') == group.get_editor_property('Index'), 'Native detail click must open its historical group'
    group_inputs.call_method('SetTimeout', args=(store, book))
    assert probe.call_method('RefreshHistory')
    timed_out = probe.get_editor_property('RunItems')[0]
    assert str(timed_out.get_editor_property('Status')) == 'error', 'A terminal native timeout must be a failure, not a partial-result warning'
    timeout_row = factory.call_method('Create', args=(world, load('WBP_HistoryRow'), None))
    assert timeout_row.call_method('SetItem', args=(timed_out,))
    assert str(timeout_row.get_editor_property('TitleText').get_text()) == str(texts.call_method('Text', args=('history.failed',)))
    assert timeout_row.get_editor_property('StatusIcon').get_editor_property('brush').get_editor_property('resource_object') == unreal.load_asset('/Game/Mods/WorkerOptimizer/T_WorkerOptimizerStatusError')
    assert probe.call_method('ShutdownView')
    helper.call_method('ReleaseWidgetArtifact')


def history_column_layout(view, row):
    row_padding = row.get_editor_property('RowSurface').get_editor_property('padding')
    header_padding = view.get_editor_property('RunHeaderBackground').get_editor_property('padding')
    assert header_padding.left == row_padding.left, 'History headers must share the row left inset'
    assert header_padding.right == row_padding.right + 10, 'History header must include the native scrollbar gutter'
    assert view.get_editor_property('ResultHeaderCell').get_editor_property('width_override') == (
        row.get_editor_property('StatusIconCell').get_editor_property('width_override')
        + row.get_editor_property('TitleTextCell').get_editor_property('width_override')
    ), 'Result header and run result must end at the same column boundary'
    helper = unreal.get_default_object(unreal.load_class(None, '/Script/WorkerOptimizerEditor.WorkerOptimizerTestSupport'))
    title = row.get_editor_property('TitleText')
    measured = helper.call_method('MeasureTextWidth', args=(title, 'Abgebrochen'))
    available = row.get_editor_property('TitleTextCell').get_editor_property('width_override') - title.slot.get_editor_property('padding').right
    assert available >= measured, 'German cancelled status must fit without a final single-letter line'
    assert title.get_editor_property('font').get_editor_property('size') == font_points(15), 'Status text must retain its body font size'
    assert view.call_method('ApplyLayout', args=(1000.0, 600.0))
    separator = view.get_editor_property('HistorySeparatorSize')
    assert separator.get_editor_property('width_override') == 1
    assert separator.get_editor_property('height_override') == 548
    assert separator.slot.get_position().x == 560
    assert view.get_editor_property('DetailSize').slot.get_position().x == 561
    assert view.get_editor_property('DetailSize').get_editor_property('width_override') == 439
    assert view.call_method('ApplyLayout', args=(800.0, 600.0))
    assert separator.get_editor_property('width_override') == 800
    assert separator.get_editor_property('height_override') == 1
    assert separator.slot.get_position().y == 192
    assert view.get_editor_property('DetailSize').slot.get_position().y == 193


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda n: unreal.load_class(None, root + n + "." + n + "_C")
    put = lambda obj, name, value: obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    factory = unreal.get_default_object(unreal.load_class(None, "/Script/UMG.WidgetBlueprintLibrary"))
    view = factory.call_method("Create", args=(world, load("WBP_LogbookView"), None))
    list_size = view.get_editor_property('ListSize')
    assert isinstance(view.get_editor_property('RunRows'), unreal.ListView)
    assert isinstance(view.get_editor_property('DetailRows'), unreal.ListView)
    assert view.call_method('ApplyLayout', args=(1000.0, 600.0))
    assert list_size.get_editor_property('width_override') == 560
    assert list_size.get_editor_property('height_override') == 548
    assert view.call_method('ApplyLayout', args=(800.0, 600.0))
    assert list_size.get_editor_property('height_override') == 192
    book, store, texts = (unreal.new_object(load(n)) for n in ("BP_Logbook", "BP_LogbookStore", "BP_PrioritySettings"))
    inputs.call_method("History", args=(book,store))
    assert view.call_method("InitializeHistory", args=(book, texts))
    assert view.call_method("RefreshHistory")
    assert list(view.get_editor_property("VisibleRuns")) == list(range(49, -1, -1))
    assert not view.get_editor_property("SelectedRunId"), "No automatic detail opening"
    native_history_events(factory, world, load)
    revision = view.get_editor_property("ViewBuildCount")
    assert view.call_method("RefreshHistory")
    assert view.get_editor_property("ViewBuildCount") == revision
    assert view.call_method("SetProblemsOnly", args=(True,))
    assert view.get_editor_property('ProblemsFilter').get_editor_property('background_color').r > view.get_editor_property('AllFilter').get_editor_property('background_color').r
    assert list(view.get_editor_property("VisibleRuns")) == [49]
    assert view.call_method("SelectRun", args=("run-49",))
    assert view.get_editor_property("SelectedRunIndex") == 49
    assert view.call_method('SelectRun',args=('run-48',)) is False, 'Filtered-out runs cannot retain selected details'
    assert not view.get_editor_property('SelectedRunId')
    assert not view.get_editor_property('DetailItems')
    assert view.call_method('SelectRun',args=('run-49',))
    assert not view.call_method('RunSelectionChanged',args=(None,True))
    assert not view.call_method('RunSelectionChanged',args=(view.get_editor_property('RunItems')[0],False))
    assert not view.call_method('RunSelectionChanged',args=(view.get_editor_property('RunItems')[0],True)), 'Repeated stable ID must not rebuild details'
    assert view.call_method('SetProblemsOnly',args=(False,))
    selected_item=view.get_editor_property('RunItems')[1]
    assert str(selected_item.get_editor_property('RunId')) == 'run-48'
    assert view.call_method('RunSelectionChanged',args=(selected_item,True)), 'Keyboard selection must update details'
    assert str(view.get_editor_property('SelectedRunId')) == 'run-48'
    assert not view.call_method('RunSelectionChanged',args=(selected_item,False))
    assert str(view.get_editor_property('SelectedRunId')) == 'run-48'
    assert view.call_method('SetProblemsOnly',args=(True,))
    assert view.call_method('SelectRun',args=('run-49',))
    rows = list(view.get_editor_property('DetailItems'))
    assert rows and any(str(row.get_editor_property('Detail')) for row in rows)
    assert len(view.get_editor_property('RunItems')) == 1
    # Timestamp wording is based on local calendar dates, not elapsed UTC hours.
    saved_dates = {}
    components = ('Year','Month','Day','Hour','Minute','Second','Millisecond')
    date_fixture = BP.create('/Game/WorkerOptimizerEditorTests','BP_HistoryDateInputs',unreal.Object.static_class())
    date_graphs = {}
    for component in components:
        graph = date_graphs[component] = BP.add_function_graph(date_fixture,'Set'+component)
        BP.add_object_function_param(graph,'Store',load('BP_LogbookStore'),True)
        BP.add_function_param(graph,'Values','int',True,container_type=ContainerType.ARRAY)
    ready_graph = BP.add_function_graph(date_fixture,'SetReady')
    BP.add_object_function_param(ready_graph,'Book',load('BP_Logbook'),True)
    BP.add_function_param(ready_graph,'Ready','bool',True)
    BP.compile_blueprint(date_fixture)
    with toolset_registry.tool_raising_exceptions():
        for component,graph in date_graphs.items():
            BP.write_graph_dsl(graph,f'(fn Set{component} (Store Values) (Class|BPLogbookStore|SetStarted{component} :self Store :Started{component} Values))')
        BP.write_graph_dsl(ready_graph,'(fn SetReady (Book Ready) (Class|BPLogbook|SetReady :self Book :Ready Ready))')
        BP.compile_blueprint(date_fixture,warnings_as_errors=True)
    date_inputs = unreal.new_object(date_fixture.generated_class())
    for component in components:
        saved_dates[component] = list(store.get_editor_property('Started'+component))
    for local_date, key in [(datetime.now(),'history.today'), (datetime.now()-timedelta(days=1),'history.yesterday')]:
        local_noon = local_date.replace(hour=12,minute=0,second=0,microsecond=0)
        utc = local_noon.astimezone(timezone.utc)
        values = (utc.year,utc.month,utc.day,utc.hour,utc.minute,utc.second,0)
        for component,value in zip(components,values):
            array = list(saved_dates[component])
            array.extend([0] * max(0,50-len(array)))
            array[49] = value
            date_inputs.call_method('Set'+component,args=(store,array))
        rendered = str(view.call_method('Timestamp',args=(49,)))
        assert rendered.startswith(str(texts.call_method('Text',args=(key,)))+', '), rendered
    for component,array in saved_dates.items():
        date_inputs.call_method('Set'+component,args=(store,array))
    # The real append announces Ready=false before committing its revision.
    # Projection rows disappear, while selection survives by immutable RunId.
    date_inputs.call_method('SetReady',args=(book,False))
    revision = view.get_editor_property('ViewBuildCount')
    assert not view.call_method('RefreshHistory')
    assert not view.call_method('CanReadStore')
    assert not view.get_editor_property('RunItems')
    assert not view.get_editor_property('DetailItems')
    assert str(view.get_editor_property('SelectedRunId')) == 'run-49'
    assert view.get_editor_property('ViewBuildCount') == revision
    date_inputs.call_method('SetReady',args=(book,True))
    assert view.call_method('RefreshHistory')
    assert str(view.get_editor_property('SelectedRunId')) == 'run-49'
    assert view.get_editor_property('SelectedRunIndex') == 49
    projected = view.get_editor_property('RunItems')[0]
    row = factory.call_method('Create', args=(world,load('WBP_HistoryRow'),None))
    history_column_layout(view, row)
    assert row.get_editor_property('StatusIconSize').get_editor_property('width_override') == 16
    assert row.get_editor_property('StatusIconSize').get_editor_property('height_override') == 16
    for name,width in [('TitleText',128),('SubtitleText',132)]:
        label=row.get_editor_property(name)
        assert label.get_editor_property('wrap_text_at') == width
        assert label.get_editor_property('wrapping_policy') == unreal.TextWrappingPolicy.ALLOW_PER_CHARACTER_WRAPPING
    assert str(view.get_editor_property('TimestampHeader').get_text()) == str(texts.call_method('Text',args=('history.time',)))
    assert row.call_method('SetItem',args=(projected,))
    assert str(row.get_editor_property('RunId')) == 'run-49'
    assert row.call_method('SelectionChanged',args=(True,))
    assert row.get_editor_property('Selected')
    assert not row.call_method('SetItem',args=(texts,))
    assert not row.get_editor_property('Selected'), 'A recycled row must clear its former selection brush'
    assert not str(row.get_editor_property('RunId'))
    assert not str(row.get_editor_property('TitleText').get_text()), 'A recycled row must clear old text before casting'
    detail_row = factory.call_method('Create',args=(world,load('WBP_HistoryDetailRow'),None))
    metric = next(item for item in view.get_editor_property('DetailItems') if str(item.get_editor_property('Kind')) == 'metrics')
    unavailable = next(item for item in view.get_editor_property('DetailItems') if str(item.get_editor_property('Kind')) == 'unavailable')
    assert detail_row.call_method('SetItem',args=(metric,))
    assert len(metric.get_editor_property('Children')) == 3
    assert detail_row.get_editor_property('Metrics').get_visibility() == unreal.SlateVisibility.VISIBLE
    assert detail_row.get_editor_property('MetricValue0').get_editor_property('font').get_editor_property('size') == font_points(13), 'Unknown metric text must not become a headline'
    assert detail_row.call_method('SetItem',args=(unavailable,))
    assert detail_row.get_editor_property('DetailText').get_editor_property('font').get_editor_property('size') == font_points(13)
    assert not detail_row.call_method('SetItem',args=(texts,))
    assert detail_row.get_editor_property('DetailText').get_editor_property('font').get_editor_property('size') == font_points(15)
    assert not str(detail_row.get_editor_property('TitleText').get_text())
    assert detail_row.get_editor_property('Metrics').get_visibility() == unreal.SlateVisibility.COLLAPSED
    # A UI-only stress population does not change the persisted last-50 policy.
    stress = [unreal.new_object(load('BP_UIListItem')) for _ in range(350)]
    view.get_editor_property('RunRows').call_method('BP_SetListItems',args=(stress,))
    assert len(store.get_editor_property('RunId')) == 50
    view.get_editor_property('RunRows').call_method('BP_SetListItems',args=(list(view.get_editor_property('RunItems')),))
    inputs.call_method("Detail", args=(view,0,63))
    assert view.call_method("RefreshDetailPage")
    assert view.get_editor_property("DetailVisibleCount") == 25
    inputs.call_method("Detail", args=(view,2,63))
    assert view.call_method("RefreshDetailPage")
    assert view.get_editor_property("DetailVisibleCount") == 13
    assert len(store.get_editor_property("RunId")) == 50, "Rendering must not append records"
    # Append/oldest eviction owns the arrays until its terminal revision commit.
    inputs.call_method("Mutation", args=(book,store,True))
    revision = view.get_editor_property("ViewBuildCount")
    assert not view.call_method("RefreshHistory")
    assert view.get_editor_property("ViewBuildCount") == revision
    assert not view.call_method("SelectRun", args=("partial",))
    assert not view.call_method("SelectVisible", args=(0,))
    assert not view.call_method("ExpandGroup", args=(0,))
    assert not view.call_method("RefreshDetailPage")
    assert str(view.get_editor_property("SelectedRunId")) == "run-49"
    first_open = factory.call_method("Create", args=(world, load("WBP_LogbookView"), None))
    assert not first_open.call_method("InitializeHistory", args=(book, texts))
    assert not first_open.get_editor_property("VisibleRuns"), "First-open must not read a partial record"
    inputs.call_method("Mutation", args=(book,store,False))
    assert view.call_method("RefreshHistory")
    assert view.get_editor_property("ViewBuildCount") == revision + 1
    assert first_open.call_method("RefreshHistory")
    assert len(first_open.get_editor_property("VisibleRuns")) == 50
    # A completed 51st append shifts indices before the next display refresh.
    inputs.call_method("Evict", args=(book,store))
    assert not view.call_method("SelectVisible", args=(0,)), "Stale row indices must refuse actions after committed eviction"
    assert not view.call_method("CanReadStore")
    assert not view.call_method("SelectRun", args=("run-49",))
    assert not view.call_method("ExpandGroup", args=(0,))
    assert not view.call_method("RefreshDetailPage")
    assert not view.call_method("NextPage")
    assert not view.call_method("PreviousPage")
    assert str(view.get_editor_property("SelectedRunId")) == "run-49"
    assert view.call_method("RefreshHistory"), "Revision guard must not prevent refresh"
    assert view.get_editor_property("SelectedRunIndex") == 48
    assert view.call_method("SelectVisible", args=(0,))
    assert str(view.get_editor_property("SelectedRunId")) == "run-49"
    assert view.call_method('ShutdownView')
    assert not view.get_editor_property('RunItems')
    assert not view.get_editor_property('DetailItems')
    unreal.log("WO_LOGBOOK_VIEW_TESTS_PASS: newest-first 50 runs, problems filter, explicit stable selection, cached refresh,25-row detail limit and read-only store projection")


run()
