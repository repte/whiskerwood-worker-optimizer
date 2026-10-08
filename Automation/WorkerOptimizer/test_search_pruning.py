"""Exercise compiled school enumeration against independent Cartesian oracles."""

import itertools
import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    fixture = BP.create("/Game/WorkerOptimizerEditorTests", "BP_SearchPruningInputs", unreal.Object.static_class())
    graphs = {name: BP.add_function_graph(fixture, name) for name in ("ConfigureChoices", "NextCandidate", "SaveCoverage")}
    for graph in graphs.values():
        BP.add_object_function_param(graph, "Search", load("BP_PlanSearch"), True)
    for name in ("ConfigureChoices", "NextCandidate"):
        BP.add_function_param(graphs[name], "Schools", "int", True)
    BP.add_function_param(graphs["ConfigureChoices"], "Values", "int", True, ContainerType.ARRAY)
    BP.add_function_param(graphs["ConfigureChoices"], "Grouped", "bool", True)
    BP.add_object_function_param(graphs["SaveCoverage"], "Planner", load("BP_StaffingPlanner"), True)
    BP.add_function_param(graphs["SaveCoverage"], "Coverage", "bool", True, ContainerType.ARRAY)
    BP.compile_blueprint(fixture)

    def set_value(name, value):
        return f"(Class|BPPlanSearch|Set{name} :self Search :{name} {value})"

    def get_value(name):
        return f"(Class|BPPlanSearch|Get{name} :self Search)"

    initial = {"SearchActive": "true", "SearchDone": "false", "HasBest": "true",
               "State": "1", "CandidateStage": "0", "CandidateIndex": "0", "CandidatesPruned": "0"}
    array_names = "SchoolBuildings ChoiceStarts ChoiceCounts ChoiceCursors Choices Teachers TeacherGroups UsedTeachers".split()
    school_arrays = {"SchoolBuildings": "n", "ChoiceStarts": "(* width n)", "ChoiceCounts": "width",
                     "ChoiceCursors": "0", "Teachers": "-1", "TeacherGroups": "Grouped"}
    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(graphs["ConfigureChoices"], f'''(fn ConfigureChoices (Search Schools Values Grouped)
          {' '.join(set_value(name, value) for name, value in initial.items())}
          {' '.join('(Utilities|Array|Clear ' + get_value(name) + ')' for name in array_names)}
          (bind width (Utilities|Array|Length Values))
          (for n (range Schools)
            {' '.join('(Utilities|Array|Add ' + get_value(name) + ' ' + value + ')' for name, value in school_arrays.items())}
            (for c (range width)
              (Utilities|Array|Add {get_value('Choices')} (Utilities|Array|Get(acopy) :Array Values :"Dimension 1" c))))
          {set_value('SelectionIndex', '(- Schools 1)')})''')
        BP.write_graph_dsl(graphs["NextCandidate"], f'''(fn NextCandidate (Search Schools)
          {set_value('SelectionIndex', '(- Schools 1)')} {set_value('State', '4')})''')
        BP.write_graph_dsl(graphs["SaveCoverage"], f'''(fn SaveCoverage (Search Planner Coverage)
          {set_value('Planner', 'Planner')} {set_value('SearchActive', 'true')} {set_value('SearchDone', 'false')}
          {set_value('StepWorkLimit', '1')} {set_value('State', '9')} {set_value('CandidateWins', 'true')}
          {set_value('CandidateCoverage', 'Coverage')}
          (Utilities|Array|Clear {get_value('SchoolBuildings')}))''')
        BP.compile_blueprint(fixture, warnings_as_errors=True)
    inputs = unreal.new_object(fixture.generated_class())

    def enumerate_choices(choices, schools, grouped=False, search=None):
        search = search or unreal.new_object(load("BP_PlanSearch"))
        inputs.call_method("ConfigureChoices", args=(search, schools, choices, grouped))
        accepted = []
        visits = 0
        for _ in range(100000):
            if search.get_editor_property("SearchDone"):
                break
            if search.get_editor_property("State") == 4:
                search.call_method("AdvanceSelection")
            elif search.get_editor_property("CandidateStage") == 2:
                # Observe the real candidate stream before matrix/scoring begins.
                accepted.append(tuple(search.get_editor_property("Teachers")))
                inputs.call_method("NextCandidate", args=(search, schools))
            else:
                if (search.get_editor_property("CandidateStage") == 0
                        and search.get_editor_property("CandidateIndex") == 0):
                    visits += 1
                search.call_method("BeginCandidate")
        assert search.get_editor_property("SearchDone"), "School enumeration did not terminate"
        assert search.get_editor_property("SearchSucceeded")
        return accepted, visits

    expected = list(itertools.permutations(range(5)))
    accepted, visits = enumerate_choices(list(range(5)), 5)
    assert accepted == expected, "Prefix pruning must retain every legal identity tuple in its original order"
    assert visits <= 825, f"Duplicate prefixes still visit their suffixes: {visits} candidate starts, old Cartesian total=3125"
    objective = lambda item: sum((school + 1) * teacher for school, teacher in enumerate(item))
    assert max(accepted, key=objective) == max(expected, key=objective) == (0, 1, 2, 3, 4)

    # Empty schools can repeat; only real teacher identities conflict.
    choices = [0, 1, -1]
    expected = [item for item in itertools.product(choices, repeat=4)
                if len([teacher for teacher in item if teacher >= 0])
                == len({teacher for teacher in item if teacher >= 0})]
    accepted, _ = enumerate_choices(choices, 4)
    assert accepted == expected, "Skipping duplicate prefixes must preserve teacherless alternatives"

    def save_coverage(coverage):
        search = unreal.new_object(load("BP_PlanSearch"))
        planner = unreal.new_object(load("BP_StaffingPlanner"))
        inputs.call_method("SaveCoverage", args=(search, planner, coverage))
        for _ in range(len(coverage) + 5):
            search.call_method("AdvanceSearch")
            assert search.get_editor_property("LastStepWork") <= 1
            if search.get_editor_property("State") == 4:
                break
        assert search.get_editor_property("HasBest")
        assert search.get_editor_property("BestFullCoverage") == all(coverage)
        return search

    full = save_coverage([True] * 6)
    accepted, full_visits = enumerate_choices(choices, 6, grouped=True, search=full)
    assert accepted == list(itertools.product([0, 1], repeat=6))
    assert full_visits == 64, f"Full coverage still enumerates teacherless choices: {full_visits}, old total=729"
    partial = save_coverage([True, True, False, True, True, True])
    accepted, partial_visits = enumerate_choices(choices, 6, grouped=True, search=partial)
    assert accepted == list(itertools.product(choices, repeat=6)), "Partial coverage may still be improved by teacherless alternatives"
    assert partial_visits == 729
    unreal.log(f"WO_SEARCH_PRUNING_TESTS_PASS: exact ordered identity oracle=120, duplicate-prefix candidate starts={visits}/3125, full-coverage starts={full_visits}/729, partial coverage retains {partial_visits} candidates")


run()
