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
    "Done": ("bool", False), "Succeeded": ("bool", False),
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
  (for j (range (+ {get('Width')} 1))
    {set_at('Used', 'j', 'false')}
    {set_at('MinV', 'j', '1e30')}))
"""

initialize = f"""
(fn Initialize (IncomingScores RowCount ColumnCount)
  {put('Done', 'true')}
  {put('Succeeded', 'false')}
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
  (for i (range RowCount) {set_at('Assignment', 'i', '-1')} {set_at('DummyAllowed', 'i', 'true')})
  {put('Succeeded', 'true')}
  (if (== RowCount 0) (return))
  {put('Succeeded', 'false')}
  {put('ValidationIndex', '0')}
  {put('Done', 'false')}
  {put('ActiveRow', '1')}
  {call('BeginRow')})
"""

restrict_dummies = f"""
(fn RestrictDummies (Mask)
  (if (!= (Utilities|Array|Length Mask) {get('Rows')})
    {put('Done', 'true')} {put('Succeeded', 'false')} (return))
  {put('DummyAllowed', 'Mask')})
"""

score_index = f"(+ (* (- {get('I0')} 1) {get('Cols')}) (- j 1))"
negative_score = f"(- {at('Scores', score_index)})"
advance = f"""
(fn Advance ()
  (if {get('Done')} (return))
  (bind scoreCount (Utilities|Array|Length {get('Scores')}))
  (if (< {get('ValidationIndex')} scoreCount)
    {put('ValidationEnd', f'(select (< (+ {get("ValidationIndex")} 512) scoreCount) (+ {get("ValidationIndex")} 512) scoreCount)')}
    (for n (range {get('ValidationIndex')} {get('ValidationEnd')})
      (bind score {at('Scores', 'n')})
      (if (not (and (>= score -1e20) (<= score 1e20)))
        {put('Done', 'true')}
        {put('Succeeded', 'false')}
        (break)))
    (if {get('Done')} (return))
    {put('ValidationIndex', get('ValidationEnd'))}
    (if (< {get('ValidationIndex')} scoreCount) (return)))
  {put('Succeeded', 'true')}
  {set_at('Used', get('J0'), 'true')}
  {put('I0', at('P', get('J0')))}
  {put('Delta', '1e30')}
  {put('J1', '0')}
  (for j (range 1 (+ {get('Width')} 1))
    (if (not {at('Used', 'j')})
      {put('Cur', '0.0')}
      (if (not {at('DummyAllowed', f'(- {get("I0")} 1)')}) {put('Cur', '1e29')})
      (if (<= j {get('Cols')})
        {put('Cur', negative_score)})
      {put('Cur', f'(- (- {get("Cur")} {at("U", get("I0"))}) {at("V", "j")})')}
      (if (< {get('Cur')} {at('MinV', 'j')})
        {set_at('MinV', 'j', get('Cur'))}
        {set_at('Way', 'j', get('J0'))})
      ; A free column at equal distance ends the search without displacing ties.
      (if (or (< {at('MinV', 'j')} {get('Delta')})
              (and (== {at('MinV', 'j')} {get('Delta')})
                   (and (== {at('P', 'j')} 0) (!= {at('P', get('J1'))} 0))))
        {put('Delta', at('MinV', 'j'))}
        {put('J1', 'j')})))
  (for j (range (+ {get('Width')} 1))
    (if {at('Used', 'j')}
      {set_at('U', at('P', 'j'), f'(+ {at("U", at("P", "j"))} {get("Delta")})')}
      {set_at('V', 'j', f'(- {at("V", "j")} {get("Delta")})')}
      (else
        {set_at('MinV', 'j', f'(- {at("MinV", "j")} {get("Delta")})')})))
  {put('J0', get('J1'))}
  (if (== {at('P', get('J0'))} 0)
    (while (!= {get('J0')} 0)
      {put('J1', at('Way', get('J0')))}
      {set_at('P', get('J0'), at('P', get('J1')))}
      {put('J0', get('J1'))})
    {put('ActiveRow', f'(+ {get("ActiveRow")} 1)')}
    (if (> {get('ActiveRow')} {get('Rows')})
      (for j (range 1 (+ {get('Cols')} 1))
        (if (> {at('P', 'j')} 0)
          {set_at('Assignment', f'(- {at("P", "j")} 1)', '(- j 1)')}))
      (for r (range {get('Rows')})
        (if (and (< {at('Assignment', 'r')} 0) (not {at('DummyAllowed', 'r')}))
          {put('Succeeded', 'false')}))
      {put('Done', 'true')}
      (else {call('BeginRow')}))))
"""

for name, code in (("BeginRow", begin), ("Initialize", initialize), ("RestrictDummies", restrict_dummies), ("Advance", advance)):
    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(graphs[name], code)
    Path(unreal.Paths.project_saved_dir(), f"WorkerOptimizer-{name}.dsl").write_text(code, encoding="utf-8")
with toolset_registry.tool_raising_exceptions():
    BP.compile_blueprint(bp, warnings_as_errors=True)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
unreal.log("WO_SOLVER_GENERATED")
exec(Path(__file__).with_name("test_solver.py").read_text(encoding="utf-8"))
