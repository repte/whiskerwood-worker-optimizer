"""Unsaved test-only subclass for observing emitted implicit score expressions."""

import uuid

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from planner_cost_dsl import implicit_row_setup, implicit_score


PROBE_CLASSES = {}


def supports_implicit(cls):
    try:
        unreal.get_default_object(cls).get_editor_property("ImplicitFirstPass")
        return True
    except Exception:
        return False


def probe_class(parent):
    if not supports_implicit(parent):
        return parent
    key = parent.get_path_name()
    if key not in PROBE_CLASSES:
        fixture = BP.create("/Game/WorkerOptimizerEditorTests",
                            "BP_ImplicitCostProbe_" + uuid.uuid4().hex, parent)
        BP.add_variable(fixture, "TestProbeScores", "float", container_type=ContainerType.ARRAY)
        graph = BP.add_function_graph(fixture, "ProbeImplicitScores")
        BP.compile_blueprint(fixture)

        def node(ending):
            matches = [value for value in BP.find_node_types(graph, ending, [])
                       if value.endswith("|" + ending)]
            preferred = "Variables|Default|" + ending
            assert preferred in matches or len(matches) == 1, (ending, matches)
            return preferred if preferred in matches else matches[0]

        def get(name):
            return "(" + node("Get" + name) + ")"

        def put(name, value):
            return "(" + node("Set" + name) + " " + value + ")"

        def at(name, index):
            return f'(Utilities|Array|Get(aref) :Array {get(name)} :"Dimension 1" {index})'

        source = f"""(fn ProbeImplicitScores ()
          (Utilities|Array|Clear {get('TestProbeScores')})
          (for row (range {get('Rows')})
            {implicit_row_setup(get, put, at, 'row')}
            (for worker (range {get('Cols')})
              {implicit_score(get, put, at, 'worker')}
              (Utilities|Array|Add {get('TestProbeScores')} {get('Cur')}))))"""
        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(graph, source)
            seed = BP.add_function_graph(fixture, "SeedTestBonuses")
            for name in ("Fill", "Coverage", "Column"):
                BP.add_function_param(seed, name, "float", True)
            BP.compile_blueprint(fixture)
            source = "(fn SeedTestBonuses (Fill Coverage Column) " + " ".join(
                put(prefix + name + "Bonus", name)
                for prefix in ("", "Implicit") for name in ("Fill", "Coverage", "Column")) + ")"
            BP.write_graph_dsl(seed, source)
            BP.compile_blueprint(fixture, warnings_as_errors=True)
        PROBE_CLASSES[key] = fixture.generated_class()
    return PROBE_CLASSES[key]


def read_scores(planner):
    assert planner.get_editor_property("ImplicitFirstPass"), "Implicit probe cannot read a later dense pass"
    planner.call_method("ProbeImplicitScores")
    return list(planner.get_editor_property("TestProbeScores"))
