"""Build a native, incremental rectangular Hungarian assignment solver."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from planner_cost_dsl import IMPLICIT_VARIABLES, implicit_row_setup, implicit_score
from solver_relaxation_bound_dsl import bound_setup, bounded_edge
from solver_integer_u_dsl import (
    INTEGER_U_VARIABLES, sources as integer_u_sources,
    initialize_reset as integer_u_initialize_reset,
    advance_dispatch as integer_u_advance_dispatch,
    state4_fence as integer_u_state4_fence, state4_complete as integer_u_state4_complete,
)
from solver_integer_minv_dsl import (
    INTEGER_MINV_VARIABLES, sources as integer_minv_sources,
    begin_scan as integer_minv_begin_scan, observe_scan as integer_minv_observe_scan,
    finish_scan as integer_minv_finish_scan, load_value as integer_minv_load_value,
    store_improvement as integer_minv_store_improvement,
    observe_dummy as integer_minv_observe_dummy,
    advance_dispatch as integer_minv_advance_dispatch,
    prefix_step as integer_minv_prefix_step,
)
from solver_native_relaxation_dsl import (
    NATIVE_VARIABLES, available as native_available, initialize_reset as native_initialize_reset,
    begin_row_reset as native_begin_row_reset, collect_free as native_collect_free,
    finish_free_cache as native_finish_free_cache, potential_begin as native_potential_begin,
    potential_batch_finish as native_potential_batch_finish,
    potential_finish as native_potential_finish, potential_item as native_potential_item,
    dummy_relax_item as native_dummy_relax_item, dummy_relax_finish as native_dummy_relax_finish,
    potential_dummy_begin as native_potential_dummy_begin,
    enable_dead_labels as native_enable_dead_labels, mark_dead_label as native_mark_dead_label,
    candidate_setup as native_candidate_setup, graph as native_graph,
)


ROOT = "/Game/Mods/WorkerOptimizer"
NAME = "BP_AssignmentSolver"
bp = unreal.load_asset(ROOT + "/" + NAME)
if bp is None:
    bp = BP.create(ROOT, NAME, unreal.Object.static_class())

variables = {
    "Done": ("bool", False), "Succeeded": ("bool", False), "DummiesRestricted": ("bool", False),
    "SolverState": ("int", False), "Cursor": ("int", False), "PotentialEnd": ("int", False),
    "StepWorkLimit": ("int", False), "LastStepWork": ("int", False),
    "Rows": ("int", False), "Cols": ("int", False), "Width": ("int", False),
    "DummyCount": ("int", False),
    "ActiveRow": ("int", False), "J0": ("int", False), "J1": ("int", False),
    "I0": ("int", False), "Delta": ("float", False), "Cur": ("float", False),
    "RowPotential": ("float", False),
    "RowScoreOffset": ("int", False), "BestColumnFree": ("bool", False),
    "NonpositiveV": ("bool", False), "ZeroLabelBound": ("bool", False), "FirstFreeColumn": ("int", False),
    "RelaxationBoundEnabled": ("bool", False), "RelaxationLowerBound": ("float", False),
    "ValidationIndex": ("int", False), "ValidationEnd": ("int", False), "RelaxationEnd": ("int", False),
    "Scores": ("float", True), "U": ("float", True), "V": ("float", True),
    "MinV": ("float", True), "P": ("int", True), "Way": ("int", True),
    "UsedColumns": ("int", True),
    "RowMinCost": ("float", True), "RowMinColumn": ("int", True), "RowSecondMinCost": ("float", True),
    "Used": ("bool", True), "Assignment": ("int", True), "DummyAllowed": ("bool", True),
}
variables.update(IMPLICIT_VARIABLES)
variables.update(NATIVE_VARIABLES)
variables.update(INTEGER_U_VARIABLES)
variables.update(INTEGER_MINV_VARIABLES)
existing = BP.list_variables(bp)
for name, (kind, array) in variables.items():
    if name not in existing:
        BP.add_variable(bp, name, kind, container_type=ContainerType.ARRAY if array else None)
BP.set_variable_instance_editable(bp, "StepWorkLimit", True)

graphs = {}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
for name in ("BeginRow", "Initialize", "InitializeImplicitFirstPass", "EnableNativeDeadLabels", "RestrictDummies", "AdvanceRelaxation", "AdvanceNativeRelaxation", "AdvancePotentials", "Advance",
             "IntegerUReset", "IntegerUCheckValue", "IntegerUPrepareRow", "IntegerUFlush", "IntegerUAdvancePotentials", "IntegerUDeferredPotentials",
             "IntegerMinReset", "IntegerMinPrepare", "IntegerMinFlush"):
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
if "Initialize" not in existing_graphs:
    BP.add_function_param(graphs["Initialize"], "IncomingScores", "float", True, ContainerType.ARRAY)
    BP.add_function_param(graphs["Initialize"], "RowCount", "int", True)
    BP.add_function_param(graphs["Initialize"], "ColumnCount", "int", True)
if "InitializeImplicitFirstPass" not in existing_graphs:
    BP.add_function_param(graphs["InitializeImplicitFirstPass"], "RowCount", "int", True)
    BP.add_function_param(graphs["InitializeImplicitFirstPass"], "ColumnCount", "int", True)
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
    return f'(Utilities|Array|Get(aref) :Array {get(name)} :"Dimension 1" {index})'


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
  {native_begin_row_reset(get, put)}
  {put('Cursor', '0')} {put('SolverState', '3')})
"""

enable_native_dead_labels = native_enable_dead_labels(get, put, node('Loge'))
integer_u_graphs = integer_u_sources(floor64_node=node('FloortoInteger64'), call_function=call, defer_v=True)
integer_u_reset = integer_u_graphs['IntegerUReset']
integer_u_check_value = integer_u_graphs['IntegerUCheckValue']
integer_u_prepare_row = integer_u_graphs['IntegerUPrepareRow']
integer_u_flush = integer_u_graphs['IntegerUFlush']
integer_u_advance_potentials = integer_u_graphs['IntegerUAdvancePotentials']
integer_minv_graphs = integer_minv_sources(get, put, at, set_at, node('FloortoInteger64'))
integer_minv_reset = integer_minv_graphs['IntegerMinReset']
integer_minv_prepare = integer_minv_graphs['IntegerMinPrepare']
integer_minv_flush = integer_minv_graphs['IntegerMinFlush']

initialize = f"""
(fn Initialize (IncomingScores RowCount ColumnCount)
  {call('IntegerMinReset')}
  {integer_u_initialize_reset(call)}
  {put('Done', 'true')}
  {put('Succeeded', 'false')}
  {put('DummiesRestricted', 'false')}
  {put('ImplicitFirstPass', 'false')}
  {native_initialize_reset(get, put)}
  {put('RelaxationBoundEnabled', 'false')} {put('RelaxationLowerBound', '0.0')}
  (Utilities|Array|Clear {get('Assignment')})
  (if (or (< RowCount 0) (< ColumnCount 0)) (return))
  ; Bound multiplication before validating matrix size.
  (if (or (> RowCount 10000) (> ColumnCount 10000)) (return))
  (if (!= (Utilities|Array|Length IncomingScores) (* RowCount ColumnCount)) (return))
  {put('Rows', 'RowCount')}
  {put('Cols', 'ColumnCount')}
  {put('Width', '(+ RowCount ColumnCount)')}
  {put('DummyCount', '0')}
  {put('Scores', 'IncomingScores')}
  {reset('U', '(+ RowCount 1)')}
  {reset('V', f'(+ {get("Width")} 1)')}
  {reset('P', f'(+ {get("Width")} 1)')}
  {reset('Way', f'(+ {get("Width")} 1)')}
  {reset('Used', f'(+ {get("Width")} 1)')}
  {reset('MinV', f'(+ {get("Width")} 1)')}
  {reset('Assignment', 'RowCount')}
  {reset('DummyAllowed', 'RowCount')}
  {reset('RowMinCost', 'RowCount')} {reset('RowMinColumn', 'RowCount')}
  {reset('RowSecondMinCost', 'RowCount')}
  {put('NonpositiveV', 'true')} {put('ZeroLabelBound', 'false')} {put('FirstFreeColumn', '1')}
  (Utilities|Array|Clear {get('UsedColumns')})
  {put('LastStepWork', '0')}
  {put('Succeeded', 'true')} (if (== RowCount 0) (return))
  {put('Succeeded', 'false')}
  {put('ValidationIndex', '0')}
  {put('Done', 'false')}
  {put('ActiveRow', '1')} {put('Cursor', '0')} {put('SolverState', '0')})
"""

implicit_row_arrays = (
    "ImplicitModes", "ImplicitMultipliers", "ImplicitMinimumRows", "ImplicitRealRows",
    "ImplicitDummyRows", "ImplicitFixedWorkers", "ImplicitDummyStarts", "ImplicitDummyEnds",
)
implicit_shape_checks = "\n".join(
    f"(if (!= (Utilities|Array|Length {get(name)}) RowCount) (return))"
    for name in implicit_row_arrays)
initialize_implicit = f"""
(fn InitializeImplicitFirstPass (RowCount ColumnCount)
  {call('IntegerMinReset')}
  {integer_u_initialize_reset(call)}
  {put('Done', 'true')} {put('Succeeded', 'false')}
  {put('ImplicitFirstPass', 'false')} {put('DummiesRestricted', 'true')}
  {native_initialize_reset(get, put)}
  {put('RelaxationBoundEnabled', 'false')} {put('RelaxationLowerBound', '0.0')}
  (Utilities|Array|Clear {get('Assignment')})
  (if (or (< RowCount 0) (< ColumnCount 0)) (return))
  (if (or (> RowCount 10000) (> ColumnCount 10000)) (return))
  (if (or (< {get('ImplicitWorkerCount')} 0) (> {get('ImplicitWorkerCount')} ColumnCount)) (return))
  (if (!= (Utilities|Array|Length {get('ImplicitScores')}) (* RowCount {get('ImplicitWorkerCount')})) (return))
  {implicit_shape_checks}
  {put('Rows', 'RowCount')} {put('Cols', 'ColumnCount')}
  {put('Width', '(+ RowCount ColumnCount)')} {put('DummyCount', '0')}
  (Utilities|Array|Clear {get('Scores')})
  {reset('U', '(+ RowCount 1)')}
  {reset('V', f'(+ {get("Width")} 1)')}
  {reset('P', f'(+ {get("Width")} 1)')}
  {reset('Way', f'(+ {get("Width")} 1)')}
  {reset('Used', f'(+ {get("Width")} 1)')}
  {reset('MinV', f'(+ {get("Width")} 1)')}
  {reset('Assignment', 'RowCount')} {reset('DummyAllowed', 'RowCount')}
  {reset('RowMinCost', 'RowCount')} {reset('RowMinColumn', 'RowCount')}
  {reset('RowSecondMinCost', 'RowCount')}
  {put('NonpositiveV', 'true')} {put('ZeroLabelBound', 'false')} {put('FirstFreeColumn', '1')}
  (Utilities|Array|Clear {get('UsedColumns')})
  {put('LastStepWork', '0')} {put('ValidationIndex', '0')}
  {put('ImplicitFirstPass', 'true')}
  {put('Succeeded', 'true')} (if (== RowCount 0) (return))
  {put('Succeeded', 'false')} {put('Done', 'false')}
  {put('ActiveRow', '1')} {put('Cursor', '0')} {put('SolverState', '1')})
"""

restrict_dummies = f"""
(fn RestrictDummies (Mask)
  (if (!= (Utilities|Array|Length Mask) {get('Rows')})
    {put('Done', 'true')} {put('Succeeded', 'false')} (return))
  {put('DummyAllowed', 'Mask')} {put('DummiesRestricted', 'true')})
"""

score_index = f"(+ {get('RowScoreOffset')} j)"
negative_score = f"(- {at('Scores', score_index)})"
dummy_allowed = at('DummyAllowed', f'(- {get("I0")} 1)')
row_min_cost = at('RowMinCost', f'(- {get("I0")} 1)')
zero_label_certificate = f"""(and (!= {get('J0')} 0)
  (and {get('NonpositiveV')} (and (>= {row_min_cost} {get('RowPotential')})
    (or (== {get('DummyCount')} 0) (>= (select {dummy_allowed} 0.0 1e29) {get('RowPotential')})))))"""
relax_cost = f"""
    (if (<= j {get('Cols')}) {put('Cur', negative_score)}
      (else {put('Cur', f'(select {dummy_allowed} 0.0 1e29)')}))
    {put('Cur', f'(- (- {get("Cur")} {get("RowPotential")}) {at("V", "j")})')}
    (if (== {get('J0')} 0)
      {set_at('MinV', 'j', get('Cur'))} {set_at('Way', 'j', get('J0'))}
      (elif (< {get('Cur')} {at('MinV', 'j')})
        {set_at('MinV', 'j', get('Cur'))} {set_at('Way', 'j', get('J0'))}
        (else {put('Cur', at('MinV', 'j'))})))
"""
implicit_load_cost = f"""
    (if (<= j {get('Cols')})
      {implicit_score(get, put, at, '(- j 1)')}
      {put('Cur', f'(- {get("Cur")})')}
      (else {put('Cur', f'(select {dummy_allowed} 0.0 1e29)')}))
"""
implicit_relax_cost = f"""
    {implicit_load_cost}
    {put('Cur', f'(- (- {get("Cur")} {get("RowPotential")}) {at("V", "j")})')}
    (if (== {get('J0')} 0)
      {set_at('MinV', 'j', get('Cur'))} {set_at('Way', 'j', get('J0'))}
      (elif (< {get('Cur')} {at('MinV', 'j')})
        {set_at('MinV', 'j', get('Cur'))} {set_at('Way', 'j', get('J0'))}
        (else {put('Cur', at('MinV', 'j'))})))
"""
relax_choose = f"""
    (if (< {get('Cur')} {get('Delta')})
      {put('Delta', get('Cur'))} {put('J1', 'j')} {put('BestColumnFree', f'(== {at("P", "j")} 0)')}
      (elif (== {get('Cur')} {get('Delta')})
        (if (not {get('BestColumnFree')})
          (if (== {at('P', 'j')} 0)
            {put('Delta', get('Cur'))} {put('J1', 'j')} {put('BestColumnFree', 'true')}))))
"""
relax_edge = f"""
  (bind j {get('Cursor')})
  (if (not {at('Used', 'j')}) {relax_cost} {relax_choose})
  {put('Cursor', f'(+ {get("Cursor")} 1)')}
"""
certified_relax_edge = f"""
  (bind j {get('Cursor')})
  (if (not {at('Used', 'j')})
    ; A nonnegative reduced cost cannot improve either sign of zero.
    (if (== {at('MinV', 'j')} 0.0) {put('Cur', at('MinV', 'j'))}
      (else {relax_cost}))
    {relax_choose})
  {put('Cursor', f'(+ {get("Cursor")} 1)')}
"""
implicit_relax_edge = f"""
  (bind j {get('Cursor')})
  (if (not {at('Used', 'j')}) {implicit_relax_cost} {relax_choose})
  {put('Cursor', f'(+ {get("Cursor")} 1)')}
"""
implicit_certified_relax_edge = f"""
  (bind j {get('Cursor')})
  (if (not {at('Used', 'j')})
    (if (== {at('MinV', 'j')} 0.0) {put('Cur', at('MinV', 'j'))}
      (else {implicit_relax_cost}))
    {relax_choose})
  {put('Cursor', f'(+ {get("Cursor")} 1)')}
"""
relaxation_bound_setup = bound_setup(get, put, at)
bounded_relax_edge = bounded_edge(get, put, at, relax_cost, relax_choose)
implicit_bounded_relax_edge = bounded_edge(get, put, at, implicit_relax_cost, relax_choose)
native_free_item = native_collect_free(get, put, at)
integer_minv_scan_item = integer_minv_observe_scan(get, put, at, set_at, node('FloortoInteger64'))


def cached_relaxation_edge(cost, scan_item=''):
    return f"""
  (bind j {get('Cursor')})
  (if (not {at('Used', 'j')}) {cost} {scan_item} {native_dummy_relax_item(get, put)} {native_free_item} {relax_choose})
  {put('Cursor', f'(+ {get("Cursor")} 1)')}
"""


cached_relax_edge = cached_relaxation_edge(relax_cost)
implicit_cached_relax_edge = cached_relaxation_edge(implicit_relax_cost)
cached_certified_relax_edge = cached_relaxation_edge(f"""
  (if (== {at('MinV', 'j')} 0.0) {put('Cur', at('MinV', 'j'))} (else {relax_cost}))
""")
implicit_cached_certified_relax_edge = cached_relaxation_edge(f"""
  (if (== {at('MinV', 'j')} 0.0) {put('Cur', at('MinV', 'j'))} (else {implicit_relax_cost}))
""")
cached_bounded_relax_edge = bounded_edge(get, put, at, relax_cost, native_dummy_relax_item(get, put) + native_free_item + relax_choose)
implicit_cached_bounded_relax_edge = bounded_edge(get, put, at, implicit_relax_cost, native_dummy_relax_item(get, put) + native_free_item + relax_choose)
update_potential = f"""
  (bind j {get('Cursor')})
  (if {at('Used', 'j')}
    {set_at('U', at('P', 'j'), f'(+ {at("U", at("P", "j"))} {get("Delta")})')}
    {set_at('V', 'j', f'(- {at("V", "j")} {get("Delta")})')}
    (else {set_at('MinV', 'j', f'(- {at("MinV", "j")} {get("Delta")})')}))
  {put('Cursor', f'(+ {get("Cursor")} 1)')}
"""
def potential_cell_dsl(include_u=True, defer_v=False):
    u_update = f"""(bind potential_row {at('P', 'j')})
      {set_at('U', 'potential_row', f'(+ {at("U", "potential_row")} {get("Delta")})')}""" if include_u else ''
    v_update = set_at('V', 'j', f'(- {at("V", "j")} {get("Delta")})')
    if defer_v:
        v_update = f'(if (== j 0) {v_update})'
    return f"""
  (if {at('Used', 'j')}
    {u_update}
    {v_update}
    (else {set_at('MinV', 'j', f'(- {at("MinV", "j")} {get("Delta")})')}))
"""
potential_cell = potential_cell_dsl()
relax_done = f"{put('Cursor', '0')} {put('SolverState', '6')}"
potentials_done = f"""{put('J0', get('J1'))} {put('SolverState', f'(select (== {at("P", get("J1"))} 0) 7 4)')}"""
invalidate_nonpositive = f"""
  (if (and (< {get('Delta')} 0.0) (> (Utilities|Array|Length {get('UsedColumns')}) 1))
    {put('NonpositiveV', 'false')})
"""
first_row_shortcut = f"""
  ; With zero row potential and nonpositive column potentials, a free
  ; global row minimum with zero column potential is the exact winner.
  (if (and (== {get('J0')} 0) (and {get('NonpositiveV')} (== {get('RowPotential')} 0.0)))
    (bind row (- {get('I0')} 1))
    (if (or (== {get('DummyCount')} 0) (<= {at('RowMinCost', 'row')} 0.0))
      (bind cached {at('RowMinColumn', 'row')})
      (if (and (> cached 0) (<= cached {get('Cols')}))
        {put('J1', 'cached')}
        (if (!= {at('P', get('J1'))} 0) {put('J1', get('FirstFreeColumn'))})
        (bind j {get('J1')})
        (if {get('ImplicitFirstPass')} {implicit_load_cost}
          (else
            (if (<= j {get('Cols')}) {put('Cur', negative_score)}
              (else {put('Cur', f'(select {dummy_allowed} 0.0 1e29)')}))))
        (if (and (== {get('Cur')} {at('RowMinCost', 'row')}) (== {at('V', 'j')} 0.0))
          {put('Cur', f'(- (- {get("Cur")} {get("RowPotential")}) {at("V", "j")})')}
          {put('Delta', get('Cur'))} {put('BestColumnFree', 'true')}
          {set_at('Way', 'j', '0')} {put('Cursor', '0')} {put('SolverState', '6')})
        (if (!= {get('SolverState')} 6) {put('J1', '0')}))))
"""
phase_work = f'(select (< (+ (- {get("Width")} {get("Cursor")}) 2) {get("StepWorkLimit")}) (+ (- {get("Width")} {get("Cursor")}) 2) {get("StepWorkLimit")})'
def relaxation_dispatch(regular, certified, bounded, implicit_regular, implicit_certified, implicit_bounded, finish):
    def loop(edge):
        source = edge.strip()
        prefix = f"(bind j {get('Cursor')})"
        suffix = put('Cursor', f'(+ {get("Cursor")} 1)')
        assert source.startswith(prefix) and source.endswith(suffix)
        body = source[len(prefix):-len(suffix)].strip()
        assert get('Cursor') not in body, 'Indexed edges must not depend on a mutating Cursor'
        return f"""
        (if (> {get('LastStepWork')} 0)
          {put('RelaxationEnd', f'(select (< (+ {get("Cursor")} {get("LastStepWork")}) (+ {get("Width")} 1)) (+ {get("Cursor")} {get("LastStepWork")}) (+ {get("Width")} 1))')}
          (for j (range {get('Cursor')} {get('RelaxationEnd')}) {body})
          (if (> {get('LastStepWork')} (- {get('RelaxationEnd')} {get('Cursor')}))
            {put('Cursor', get('RelaxationEnd'))} {finish}
            (else {put('Cursor', get('RelaxationEnd'))})))
        """

    def mode(plain, zero, lower):
        return f"""
        (if {get('RelaxationBoundEnabled')} {loop(lower)}
          (else (if {get('ZeroLabelBound')} {loop(zero)} (else {loop(plain)}))))
        """

    return f"""
      (if {get('ImplicitFirstPass')} {mode(implicit_regular, implicit_certified, implicit_bounded)}
        (else {mode(regular, certified, bounded)}))
    """


ordinary_relaxation = relaxation_dispatch(
    relax_edge, certified_relax_edge, bounded_relax_edge,
    implicit_relax_edge, implicit_certified_relax_edge, implicit_bounded_relax_edge, relax_done)
cached_relaxation_finish = native_dummy_relax_finish(get, put) + native_finish_free_cache(get, put) + integer_minv_finish_scan(get, put) + relax_done
cached_relaxation = relaxation_dispatch(
    cached_relax_edge, cached_certified_relax_edge, cached_bounded_relax_edge,
    implicit_cached_relax_edge, implicit_cached_certified_relax_edge, implicit_cached_bounded_relax_edge,
    cached_relaxation_finish)
gathering_relaxation = relaxation_dispatch(
    cached_relaxation_edge(relax_cost, integer_minv_scan_item),
    cached_relaxation_edge(f"(if (== {at('MinV', 'j')} 0.0) {put('Cur', at('MinV', 'j'))} (else {relax_cost}))", integer_minv_scan_item),
    bounded_edge(get, put, at, relax_cost, integer_minv_scan_item + native_dummy_relax_item(get, put) + native_free_item + relax_choose),
    cached_relaxation_edge(implicit_relax_cost, integer_minv_scan_item),
    cached_relaxation_edge(f"(if (== {at('MinV', 'j')} 0.0) {put('Cur', at('MinV', 'j'))} (else {implicit_relax_cost}))", integer_minv_scan_item),
    bounded_edge(get, put, at, implicit_relax_cost, integer_minv_scan_item + native_dummy_relax_item(get, put) + native_free_item + relax_choose),
    cached_relaxation_finish)
advance_relaxation = f"""
(fn AdvanceRelaxation ()
  ; Include the phase-exit step without dispatching every cell through SwitchInt.
  {integer_minv_begin_scan(get, put)}
  {put('LastStepWork', phase_work)}
  (if {native_available(get)}
    (if {get('IntegerMinGathering')} {gathering_relaxation} (else {cached_relaxation}))
    (else {ordinary_relaxation})))
"""
def integer_minv_cost(load):
    return f'''
      {load}
      {put('Cur', f'(- (- {get("Cur")} {get("RowPotential")}) {at("V", "j")})')}
      {integer_minv_load_value(get, put, at, 'j')}
      (if (< {get('Cur')} {get('IntegerMinValue')})
        {integer_minv_store_improvement(get, put, at, set_at, node('FloortoInteger64'))}
        (if (== {get('IntegerMinFlushCursor')} 0) {set_at('Way', 'j', get('J0'))})
        (else {put('Cur', get('IntegerMinValue'))}))
    '''


integer_minv_dense_cost = integer_minv_cost(f"{put('Cur', negative_score)}")
integer_minv_implicit_cost = integer_minv_cost(implicit_load_cost)
integer_minv_native_minimum = f'''
  (if {get('IntegerMinActive')}
    {put('IntegerMinRawMinimum', get('NativeMinimum'))}
    {put('IntegerMinIndex', f'({node("FindItem")} :TargetArray {get("MinV")} :ItemToFind {get("IntegerMinRawMinimum")})')}
    {integer_minv_load_value(get, put, at, get('IntegerMinIndex'), 'NativeMinimum')})
'''
advance_native_relaxation = native_graph(
    get, put, at, set_at,
    f"(if {get('IntegerMinActive')} {integer_minv_dense_cost} (else {relax_cost}))",
    f"(if {get('IntegerMinActive')} {integer_minv_implicit_cost} (else {implicit_relax_cost}))",
    relax_done, sort_node=node('SortFloatArray'), find_node=node('FindItem'),
    integer_minv={'load': lambda index, target='IntegerMinValue': integer_minv_load_value(get, put, at, index, target),
                  'observe_dummy': integer_minv_observe_dummy(get, put),
                  'minimum': integer_minv_native_minimum})
def potential_graph(name, include_u=True, defer_v=False):
    terminal_u = set_at('U', at('P', 'j'), f'(+ {at("U", at("P", "j"))} {get("Delta")})') if include_u else ''
    terminal_v = set_at('V', 'j', f'(- {at("V", "j")} {get("Delta")})')
    if defer_v:
        terminal_v = f'(if (== j 0) {terminal_v})'
    return f"""
(fn {name} ()
  (if (== {get('Delta')} 0.0)
    {put('PotentialDummySkip', 'false')}
    {put('PotentialFreeFixedColumn', '0')}
    {put('LastStepWork', '1')}
    (if {native_available(get)} {native_potential_finish(get, put, at, zero_delta=True)})
    {potentials_done} (return))
  {put('NativeMaskReady', 'false')}
  {invalidate_nonpositive}
  ; A final augmentation only consumes Way/P; the next row overwrites MinV.
  ; Used columns own distinct matched rows, including the active row at zero.
  (if (== {at('P', get('J1'))} 0)
    {put('PotentialDummySkip', 'false')}
    {put('PotentialFreeFixedColumn', '0')}
    {put('NativeFreeValid', 'false')}
    {put('UpperGlobalReady', 'false')} {put('UpperPrefixReady', 'false')}
    (bind count (Utilities|Array|Length {get('UsedColumns')}))
    (bind remaining (+ (- count {get('Cursor')}) 1))
    {put('LastStepWork', f'(select (< remaining {get("StepWorkLimit")}) remaining {get("StepWorkLimit")})')}
    (for work (range {get('LastStepWork')})
      (if (< {get('Cursor')} count)
        (bind j {at('UsedColumns', get('Cursor'))})
        {terminal_u}
        {terminal_v}
        {put('Cursor', f'(+ {get("Cursor")} 1)')}
        (else {potentials_done})))
    (return))
  {integer_minv_prefix_step(get, put, at, set_at, native_potential_begin(get, put), native_potential_dummy_begin(get, put)) if not include_u and defer_v else ''}
  {put('LastStepWork', phase_work)}
  ; Keep the loop bound stable while preserving the separate phase-exit item.
  {put('PotentialEnd', f'(select (< (+ {get("Cursor")} {get("LastStepWork")}) (+ {get("Width")} 1)) (+ {get("Cursor")} {get("LastStepWork")}) (+ {get("Width")} 1))')}
  (if {native_available(get)}
    {native_potential_begin(get, put)}
    {native_potential_dummy_begin(get, put)}
    ; A minimum already at the first free index stays first under subtraction.
    (if (> {get('PotentialFreeFixedColumn')} 0)
      (for j (range {get('Cursor')} {get('PotentialLoopEnd')})
        {native_potential_item(get, put, at, set_at, collect=False, include_u=include_u, defer_v=defer_v)})
      (else
        (for j (range {get('Cursor')} {get('PotentialLoopEnd')})
          {native_potential_item(get, put, at, set_at, include_u=include_u, defer_v=defer_v)})))
    (if (< {get('PotentialLoopEnd')} {get('PotentialEnd')})
      {put('NativeValue', at('MinV', f'(- {get("PotentialEnd")} 1)'))})
    {native_potential_batch_finish(get, put, at)}
    (else
      (if (== {get('Cursor')} 0)
        {put('PotentialFreeFixedColumn', '0')} {put('PotentialDummySkip', 'false')}
        {put('NativeDummyBoundReady', 'false')}
        {put('UpperGlobalReady', 'false')} {put('UpperPrefixReady', 'false')})
      (for j (range {get('Cursor')} {get('PotentialEnd')}) {potential_cell_dsl(include_u, defer_v)})))
  (if (< (- {get('PotentialEnd')} {get('Cursor')}) {get('LastStepWork')})
    {put('Cursor', get('PotentialEnd'))}
    (if {native_available(get)} {native_potential_finish(get, put, at)})
    {potentials_done}
    (else {put('Cursor', get('PotentialEnd'))})))
"""
advance_potentials = potential_graph('AdvancePotentials')
integer_u_deferred_potentials = potential_graph('IntegerUDeferredPotentials', include_u=False, defer_v=True)
validate_row_minima = f"""
  (if (== column 1)
    {set_at('RowMinCost', 'row', 'cost')} {set_at('RowMinColumn', 'row', 'column')}
    {set_at('RowSecondMinCost', 'row', '1e20')}
    (elif (< cost {at('RowMinCost', 'row')})
      {set_at('RowSecondMinCost', 'row', at('RowMinCost', 'row'))}
      {set_at('RowMinCost', 'row', 'cost')} {set_at('RowMinColumn', 'row', 'column')}
      (elif (< cost {at('RowSecondMinCost', 'row')})
        {set_at('RowSecondMinCost', 'row', 'cost')})))
"""
advance = f"""
(fn Advance ()
  {put('LastStepWork', '0')} (if {get('Done')} (return))
  (if (<= {get('StepWorkLimit')} 0) {put('Done', 'true')} {put('Succeeded', 'false')} (return))
  {integer_minv_advance_dispatch(get, put, at, call)}
  {integer_u_advance_dispatch(get, call)}
  (if (== {get('SolverState')} 5) {call('AdvanceRelaxation')} (return))
  (if (== {get('SolverState')} 6) {call('AdvancePotentials')} (return))
  (if (== {get('SolverState')} 11) {call('AdvanceNativeRelaxation')} (return))
  (for work (range (select (> {get('StepWorkLimit')} 0) {get('StepWorkLimit')} 1))
    (if {get('Done')} (break))
    (if (== {get('SolverState')} 4)
      (if {integer_u_state4_fence(get)} (break))
      (else (if (or (== {get('SolverState')} 11) (or (== {get('SolverState')} 5) (== {get('SolverState')} 6))) (break))))
    {put('LastStepWork', f'(+ {get("LastStepWork")} 1)')}
    (switch int {get('SolverState')}
      (:0
        (if (< {get('ValidationIndex')} (Utilities|Array|Length {get('Scores')}))
          (bind score {at('Scores', get('ValidationIndex'))})
          (if (not (and (>= score -1e20) (<= score 1e20))) {put('Done', 'true')})
          (bind row (/ {get('ValidationIndex')} {get('Cols')}))
          (bind column (+ (- {get('ValidationIndex')} (* row {get('Cols')})) 1))
          (bind cost (- score))
          {validate_row_minima}
          {put('ValidationIndex', f'(+ {get("ValidationIndex")} 1)')}
          (else {put('SolverState', '1')} {put('Cursor', '0')})))
      (:1
        (if (< {get('Cursor')} {get('Rows')})
          {set_at('Assignment', get('Cursor'), '-1')}
          (if (< {get('Cols')} 2) {set_at('RowSecondMinCost', get('Cursor'), '1e20')})
          (if (not {get('DummiesRestricted')}) {set_at('DummyAllowed', get('Cursor'), 'true')})
          (if {at('DummyAllowed', get('Cursor'))} {put('DummyCount', f'(+ {get("DummyCount")} 1)')})
          {put('Cursor', f'(+ {get("Cursor")} 1)')}
          (else
            {put('Width', f'(+ {get("Cols")} {get("DummyCount")})')}
            (if (< {get('Width')} {get('Rows')}) {put('Done', 'true')}
              (else {put('Succeeded', 'true')} {call('BeginRow')})))))
      (:2 {put('Done', 'true')} {put('Succeeded', 'false')})
      (:3
        ; Only the previous path's columns need resetting. The first relaxation
        ; initializes every distance label together with its real edge cost.
        (if (< {get('Cursor')} (Utilities|Array|Length {get('UsedColumns')}))
          {set_at('Used', at('UsedColumns', get('Cursor')), 'false')}
          {put('Cursor', f'(+ {get("Cursor")} 1)')}
          (else (Utilities|Array|Clear {get('UsedColumns')}) {put('SolverState', '10')})))
      (:4
        {native_mark_dead_label(get, put, at, set_at)}
        {set_at('Used', get('J0'), 'true')} {put('I0', at('P', get('J0')))}
        (Utilities|Array|Add {get('UsedColumns')} {get('J0')})
        (if (> {get('J0')} {get('ImplicitWorkerCount')}) {put('NativeUsedRealOnly', 'false')})
        {put('RowPotential', at('U', get('I0')))}
        {put('RowScoreOffset', f'(- (* (- {get("I0")} 1) {get("Cols")}) 1)')}
        (if {get('ImplicitFirstPass')} {implicit_row_setup(get, put, at, f'(- {get("I0")} 1)')})
        {put('ZeroLabelBound', zero_label_certificate)}
        {relaxation_bound_setup}
        {put('Delta', '1e30')} {put('J1', '0')} {put('BestColumnFree', 'false')}
        {put('Cursor', '1')} {put('SolverState', '5')}
        {first_row_shortcut}
        {put('IntegerMinPhasePrepared', 'false')}
        {native_candidate_setup(get, put)}
        {integer_u_state4_complete(put)})
      (:5
        (if (<= {get('Cursor')} {get('Width')})
          (if {get('ImplicitFirstPass')} {implicit_relax_edge} (else {relax_edge}))
          (else {relax_done})))
      (:6
        ; Keep residual subtraction eager: adding large shared offsets loses
        ; small score differences even when every array uses double precision.
        ; A zero delta leaves every potential and residual unchanged.
        {invalidate_nonpositive}
        (if (and (!= {get('Delta')} 0.0) (<= {get('Cursor')} {get('Width')}))
          {update_potential} (else {potentials_done})))
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
      (:10
        ; Augmentation only adds occupied columns, so this cursor never retreats.
        (if (<= {get('FirstFreeColumn')} {get('Width')})
          (if (!= {at('P', get('FirstFreeColumn'))} 0)
            {put('FirstFreeColumn', f'(+ {get("FirstFreeColumn")} 1)')}
            (else {put('SolverState', '4')}))
          (else {put('Done', 'true')} {put('Succeeded', 'false')})))
      (:Default {put('Done', 'true')} {put('Succeeded', 'false')}))))
"""

for name, code in (("BeginRow", begin), ("Initialize", initialize), ("InitializeImplicitFirstPass", initialize_implicit),
                   ("EnableNativeDeadLabels", enable_native_dead_labels), ("RestrictDummies", restrict_dummies),
                   ("AdvanceRelaxation", advance_relaxation), ("AdvanceNativeRelaxation", advance_native_relaxation),
                   ("AdvancePotentials", advance_potentials), ("Advance", advance),
                   *integer_u_graphs.items(), ("IntegerUDeferredPotentials", integer_u_deferred_potentials),
                   *integer_minv_graphs.items()):
    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(graphs[name], code)
    Path(unreal.Paths.project_saved_dir(), f"WorkerOptimizer-{name}.dsl").write_text(code, encoding="utf-8")
with toolset_registry.tool_raising_exceptions():
    BP.compile_blueprint(bp, warnings_as_errors=True)
unreal.get_default_object(bp.generated_class()).set_editor_property("StepWorkLimit", 64)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
unreal.log("WO_SOLVER_GENERATED")
exec(Path(__file__).with_name("test_solver.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_solver_work.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_solver_row_bound.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_solver_zero_label.py").read_text(encoding="utf-8"))
