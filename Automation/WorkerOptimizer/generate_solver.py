"""Build a native, incremental rectangular Hungarian assignment solver."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType


ROOT = "/Game/Mods/WorkerOptimizer"
NAME = "BP_AssignmentSolver"
bp = unreal.load_asset(ROOT + "/" + NAME)
if bp is None:
    bp = BP.create(ROOT, NAME, unreal.Object.static_class())

variables = {
    "Done": ("bool", False), "Succeeded": ("bool", False), "DummiesRestricted": ("bool", False),
    "SolverState": ("int", False), "Cursor": ("int", False),
    "StepWorkLimit": ("int", False), "LastStepWork": ("int", False),
    "Rows": ("int", False), "Cols": ("int", False), "Width": ("int", False),
    "ActiveRow": ("int", False), "J0": ("int", False), "J1": ("int", False),
    "I0": ("int", False), "Delta": ("float", False), "Cur": ("float", False),
    "ValidationIndex": ("int", False), "ValidationEnd": ("int", False),
    "Scores": ("float", True), "U": ("float", True), "V": ("float", True),
    "MinV": ("float", True), "P": ("int", True), "Way": ("int", True),
    "Used": ("bool", True), "Assignment": ("int", True), "DummyAllowed": ("bool", True),
}
existing = BP.list_variables(bp)
for name, (kind, array) in variables.items():
    if name not in existing:
        BP.add_variable(bp, name, kind, container_type=ContainerType.ARRAY if array else None)
BP.set_variable_instance_editable(bp, "StepWorkLimit", True)

graphs = {}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
for name in ("BeginRow", "Initialize", "RestrictDummies", "Advance"):
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
if "Initialize" not in existing_graphs:
    BP.add_function_param(graphs["Initialize"], "IncomingScores", "float", True, ContainerType.ARRAY)
    BP.add_function_param(graphs["Initialize"], "RowCount", "int", True)
    BP.add_function_param(graphs["Initialize"], "ColumnCount", "int", True)
if "RestrictDummies" not in existing_graphs:
    BP.add_function_param(graphs["RestrictDummies"], "Mask", "bool", True, ContainerType.ARRAY)
BP.compile_blueprint(bp)


def node(ending):
    matches = [n for n in BP.find_node_types(graphs["Advance"], ending, []) if n.endswith("|" + ending)]
    own_variable = "Variables|Default|" + ending
    if own_variable in matches:
        return own_variable
    if len(matches) != 1:
        raise RuntimeError(f"Ambiguous node {ending}: {matches}")
    return matches[0]


def get(name):
    return f"({node('Get' + name)})"


def put(name, value):
    return f"({node('Set' + name)} {value})"


def at(name, index):
    return f'(Utilities|Array|Get(acopy) :Array {get(name)} :"Dimension 1" {index})'


def set_at(name, index, value):
    return f"(Utilities|Array|SetArrayElem :TargetArray {get(name)} :Index {index} :Item {value})"


def reset(name, size):
    return f"(Utilities|Array|Clear {get(name)}) (Utilities|Array|Resize {get(name)} {size})"


def call(name):
    return f"({node(name)})"


begin = f"""
(fn BeginRow ()
  {set_at('P', '0', get('ActiveRow'))}
  {put('J0', '0')}
  {put('Cursor', '0')} {put('SolverState', '3')})
"""

initialize = f"""
(fn Initialize (IncomingScores RowCount ColumnCount)
  {put('Done', 'true')}
  {put('Succeeded', 'false')}
  {put('DummiesRestricted', 'false')}
  (Utilities|Array|Clear {get('Assignment')})
  (if (or (< RowCount 0) (< ColumnCount 0)) (return))
  ; Bound multiplication before validating matrix size.
  (if (or (> RowCount 10000) (> ColumnCount 10000)) (return))
  (if (!= (Utilities|Array|Length IncomingScores) (* RowCount ColumnCount)) (return))
  {put('Rows', 'RowCount')}
  {put('Cols', 'ColumnCount')}
  {put('Width', '(+ RowCount ColumnCount)')}
  {put('Scores', 'IncomingScores')}
  {reset('U', '(+ RowCount 1)')}
  {reset('V', f'(+ {get("Width")} 1)')}
  {reset('P', f'(+ {get("Width")} 1)')}
  {reset('Way', f'(+ {get("Width")} 1)')}
  {reset('Used', f'(+ {get("Width")} 1)')}
  {reset('MinV', f'(+ {get("Width")} 1)')}
  {reset('Assignment', 'RowCount')}
  {reset('DummyAllowed', 'RowCount')}
  {put('LastStepWork', '0')}
  {put('Succeeded', 'true')} (if (== RowCount 0) (return))
  {put('Succeeded', 'false')}
  {put('ValidationIndex', '0')}
  {put('Done', 'false')}
  {put('ActiveRow', '1')} {put('Cursor', '0')} {put('SolverState', '0')})
"""

restrict_dummies = f"""
(fn RestrictDummies (Mask)
  (if (!= (Utilities|Array|Length Mask) {get('Rows')})
    {put('Done', 'true')} {put('Succeeded', 'false')} (return))
  {put('DummyAllowed', 'Mask')} {put('DummiesRestricted', 'true')})
"""

score_index = f"(+ (* (- {get('I0')} 1) {get('Cols')}) (- j 1))"
negative_score = f"(- {at('Scores', score_index)})"
dummy_allowed = at('DummyAllowed', f'(- {get("I0")} 1)')
advance = f"""
(fn Advance ()
  {put('LastStepWork', '0')} (if {get('Done')} (return))
  (if (<= {get('StepWorkLimit')} 0) {put('Done', 'true')} {put('Succeeded', 'false')} (return))
  (for work (range (select (> {get('StepWorkLimit')} 0) {get('StepWorkLimit')} 1))
    (if {get('Done')} (break))
    {put('LastStepWork', f'(+ {get("LastStepWork")} 1)')}
    (switch int {get('SolverState')}
      (:0
        (if (< {get('ValidationIndex')} (Utilities|Array|Length {get('Scores')}))
          (bind score {at('Scores', get('ValidationIndex'))})
          (if (not (and (>= score -1e20) (<= score 1e20))) {put('Done', 'true')})
          {put('ValidationIndex', f'(+ {get("ValidationIndex")} 1)')}
          (else {put('SolverState', '1')} {put('Cursor', '0')})))
      (:1
        (if (< {get('Cursor')} {get('Rows')})
          {set_at('Assignment', get('Cursor'), '-1')}
          (if (not {get('DummiesRestricted')}) {set_at('DummyAllowed', get('Cursor'), 'true')})
          {put('Cursor', f'(+ {get("Cursor")} 1)')}
          (else {put('Succeeded', 'true')} {call('BeginRow')})))
      (:2 {put('Done', 'true')} {put('Succeeded', 'false')})
      (:3
        (if (<= {get('Cursor')} {get('Width')})
          {set_at('Used', get('Cursor'), 'false')} {set_at('MinV', get('Cursor'), '1e30')}
          {put('Cursor', f'(+ {get("Cursor")} 1)')}
          (else {put('SolverState', '4')})))
      (:4
        {set_at('Used', get('J0'), 'true')} {put('I0', at('P', get('J0')))}
        {put('Delta', '1e30')} {put('J1', '0')} {put('Cursor', '1')} {put('SolverState', '5')})
      (:5
        (if (<= {get('Cursor')} {get('Width')})
          (bind j {get('Cursor')})
          (if (not {at('Used', 'j')})
            {put('Cur', f'(select {dummy_allowed} 0.0 1e29)')}
            (if (<= j {get('Cols')}) {put('Cur', negative_score)})
            {put('Cur', f'(- (- {get("Cur")} {at("U", get("I0"))}) {at("V", "j")})')}
            (if (< {get('Cur')} {at('MinV', 'j')}) {set_at('MinV', 'j', get('Cur'))} {set_at('Way', 'j', get('J0'))})
            (if (or (< {at('MinV', 'j')} {get('Delta')})
              (and (== {at('MinV', 'j')} {get('Delta')}) (and (== {at('P', 'j')} 0) (!= {at('P', get('J1'))} 0))))
              {put('Delta', at('MinV', 'j'))} {put('J1', 'j')}))
          {put('Cursor', f'(+ {get("Cursor")} 1)')}
          (else {put('Cursor', '0')} {put('SolverState', '6')})))
      (:6
        (if (<= {get('Cursor')} {get('Width')})
          (bind j {get('Cursor')})
          (if {at('Used', 'j')}
            {set_at('U', at('P', 'j'), f'(+ {at("U", at("P", "j"))} {get("Delta")})')}
            {set_at('V', 'j', f'(- {at("V", "j")} {get("Delta")})')}
            (else {set_at('MinV', 'j', f'(- {at("MinV", "j")} {get("Delta")})')}))
          {put('Cursor', f'(+ {get("Cursor")} 1)')}
          (else {put('J0', get('J1'))} {put('SolverState', f'(select (== {at("P", get("J1"))} 0) 7 4)')})))
      (:7
        (if (!= {get('J0')} 0)
          {put('J1', at('Way', get('J0')))} {set_at('P', get('J0'), at('P', get('J1')))} {put('J0', get('J1'))}
          (else
            {put('ActiveRow', f'(+ {get("ActiveRow")} 1)')}
            (if (> {get('ActiveRow')} {get('Rows')}) {put('Cursor', '1')} {put('SolverState', '8')}
              (else {call('BeginRow')})))))
      (:8
        (if (<= {get('Cursor')} {get('Cols')})
          (bind j {get('Cursor')})
          (if (> {at('P', 'j')} 0) {set_at('Assignment', f'(- {at("P", "j")} 1)', '(- j 1)')})
          {put('Cursor', f'(+ {get("Cursor")} 1)')}
          (else {put('Cursor', '0')} {put('SolverState', '9')})))
      (:9
        (if (< {get('Cursor')} {get('Rows')})
          (bind r {get('Cursor')})
          (if (and (< {at('Assignment', 'r')} 0) (not {at('DummyAllowed', 'r')})) {put('Succeeded', 'false')})
          {put('Cursor', f'(+ {get("Cursor")} 1)')}
          (else {put('Done', 'true')})))
      (:Default {put('Done', 'true')} {put('Succeeded', 'false')}))))
"""

for name, code in (("BeginRow", begin), ("Initialize", initialize), ("RestrictDummies", restrict_dummies), ("Advance", advance)):
    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(graphs[name], code)
    Path(unreal.Paths.project_saved_dir(), f"WorkerOptimizer-{name}.dsl").write_text(code, encoding="utf-8")
with toolset_registry.tool_raising_exceptions():
    BP.compile_blueprint(bp, warnings_as_errors=True)
unreal.get_default_object(bp.generated_class()).set_editor_property("StepWorkLimit", 64)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
unreal.log("WO_SOLVER_GENERATED")
exec(Path(__file__).with_name("test_solver.py").read_text(encoding="utf-8"))
