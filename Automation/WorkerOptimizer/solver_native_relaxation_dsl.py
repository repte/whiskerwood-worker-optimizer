"""Exact native selection within the existing Hungarian solver.

Only the planner may enable trust after an initializer. Omitted CSR edges must
have score -1e20, indices must be sorted/unique, and universal dummies are absent.
The generic public solver defaults to its existing dense path. Integrators must
dispatch SolverState 11 with the same phase fence/cancellation as states 5/6.
"""

from solver_label_upper_bound_dsl import (
    UPPER_VARIABLES, begin_row as upper_begin_row, ensure_epoch as upper_ensure_epoch,
    guarded_max as upper_guarded_max, invalidate as upper_invalidate,
    potential_begin as upper_potential_begin, reset as upper_reset,
)


NATIVE_VARIABLES = {
    **UPPER_VARIABLES,
    "NativePlannerTrusted": ("bool", False), "NativeCsrReady": ("bool", False),
    "NativeDeadLabels": ("bool", False), "NativeDeadInfinity": ("float", False),
    "NativeDeadPrefixWidth": ("int", False), "NativeDeadPrefixUsed": ("int", False),
    "NativeFreeValid": ("bool", False), "NativeFreeRow": ("int", False),
    "NativeFreeColumn": ("int", False), "NativeFreeMinimum": ("float", False),
    "PotentialFreeFixedColumn": ("int", False),
    "NativeDummyBound": ("float", False), "NativeDummyBoundReady": ("bool", False),
    "NativeDummyBoundRow": ("int", False), "NativeDummyInitCount": ("int", False),
    "NativeUsedRealOnly": ("bool", False), "PotentialDummySkip": ("bool", False),
    "PotentialLoopEnd": ("int", False),
    "NativeMaskReady": ("bool", False), "NativeMaskRow": ("int", False),
    "NativePhase": ("int", False), "NativeCursor": ("int", False),
    "NativeMaskEnd": ("int", False),
    "NativeEnd": ("int", False), "NativeColumn": ("int", False),
    "NativeMinimum": ("float", False), "NativeValue": ("float", False),
    "NativeRowOffsets": ("int", True), "NativeColumns": ("int", True),
    "NativeMaxScratch": ("float", True), "NativeMasked": ("float", True),
    "NativeSorted": ("float", True),
}


def available(get):
    return f"(and {get('NativePlannerTrusted')} (and (== {get('DummyCount')} 0) (== {get('Width')} {get('Cols')})))"


def initialize_reset(get, put):
    arrays = (name for name, (_, array) in NATIVE_VARIABLES.items() if array)
    return "\n".join([
        upper_reset(get, put),
        put("NativePlannerTrusted", "false"), put("NativeCsrReady", "false"),
        put("NativeDeadLabels", "false"), put("NativeDeadInfinity", "0.0"),
        put("NativeDeadPrefixWidth", "0"), put("NativeDeadPrefixUsed", "0"),
        put("NativeFreeValid", "false"), put("NativeFreeRow", "0"),
        put("NativeMaskReady", "false"), put("NativeMaskRow", "0"),
        put("NativeFreeColumn", "0"), put("NativeFreeMinimum", "1e30"),
        put("PotentialFreeFixedColumn", "0"),
        put("NativeDummyBound", "1e30"), put("NativeDummyBoundReady", "false"),
        put("NativeDummyBoundRow", "0"), put("NativeDummyInitCount", "0"),
        put("NativeUsedRealOnly", "false"), put("PotentialDummySkip", "false"),
        put("NativePhase", "0"), put("NativeCursor", "0"), put("NativeEnd", "0"),
        *[f"(Utilities|Array|Clear {get(name)})" for name in arrays]])


def begin_row_reset(get, put):
    return f"""
      {upper_begin_row(get, put)}
      (if {get('NativeDeadLabels')}
        {put('NativeDeadPrefixUsed', '0')}
        {put('NativeDeadPrefixWidth', f'(select (and (> {get("ImplicitWorkerCount")} 0) (<= {get("ImplicitWorkerCount")} {get("Cols")})) {get("ImplicitWorkerCount")} 0)')})
      {put('NativeFreeValid', 'false')} {put('NativeFreeRow', get('ActiveRow'))}
      {put('NativeMaskReady', 'false')} {put('NativeMaskRow', get('ActiveRow'))}
      {put('NativeFreeColumn', '0')} {put('NativeFreeMinimum', '1e30')}
      {put('PotentialFreeFixedColumn', '0')}
      {put('NativeDummyBound', '1e30')} {put('NativeDummyBoundReady', 'false')}
      {put('NativeDummyBoundRow', get('ActiveRow'))} {put('NativeDummyInitCount', '0')}
      {put('NativeUsedRealOnly', 'true')} {put('PotentialDummySkip', 'false')}
      {put('NativePhase', '0')} {put('NativeCursor', '0')}
    """


def enable_dead_labels(get, put, log_node):
    """Private opt-in immediately after initialization and before solving."""
    return f"""
(fn EnableNativeDeadLabels ()
  (if {get('NativeDeadLabels')} (return))
  (if (or (not {get('NativePlannerTrusted')}) {get('Done')}) (return))
  (if (or (!= {get('Cursor')} 0) (and (!= {get('SolverState')} 0) (!= {get('SolverState')} 1))) (return))
  ; The reflected logarithm preserves IEEE +Inf; its zero input is a runtime property.
  {put('NativeDeadInfinity', '0.0')}
  {put('NativeDeadInfinity', f'(- 0.0 ({log_node} :A {get("NativeDeadInfinity")}))')}
  {put('NativeDeadLabels', 'true')})
    """


def mark_dead_label(get, put, at, set_at):
    """State 4, before setting Used; a visited label is never relaxed again."""
    return f"""
      (if {get('NativeDeadLabels')}
        (if {available(get)}
          (if (not {at('Used', get('J0'))})
            {set_at('MinV', get('J0'), get('NativeDeadInfinity'))}
            (if (<= {get('J0')} {get('NativeDeadPrefixWidth')})
              {put('NativeDeadPrefixUsed', f'(+ {get("NativeDeadPrefixUsed")} 1)')}))))
    """


def collect_free(get, put, at, column="j", value=None, ascending=False):
    value = get("Cur") if value is None else value
    if ascending:
        # A freshly reset, ascending scan already owns the first equal column.
        return f"""
      (if (== {at('P', column)} 0)
        (if (< {value} {get('NativeFreeMinimum')})
          {put('NativeFreeMinimum', value)} {put('NativeFreeColumn', column)}))
    """
    return f"""
      (if (== {at('P', column)} 0)
        (if (< {value} {get('NativeFreeMinimum')})
          {put('NativeFreeMinimum', value)} {put('NativeFreeColumn', column)}
          (elif (== {value} {get('NativeFreeMinimum')})
            (if (< {column} {get('NativeFreeColumn')})
              {put('NativeFreeMinimum', value)} {put('NativeFreeColumn', column)}))))
    """


def finish_free_cache(get, put):
    return f"""
      {put('NativeFreeRow', get('ActiveRow'))}
      {put('NativeFreeValid', f'(> {get("NativeFreeColumn")} 0)')}
    """


def potential_begin(get, put):
    """Only at Cursor=0 of the existing nonterminal, nonzero potential branch."""
    return f"""
      {upper_potential_begin(get, put)}
      (if (== {get('Cursor')} 0)
        {put('PotentialFreeFixedColumn', '0')}
        (if (and {get('NativeFreeValid')} (== {get('NativeFreeRow')} {get('ActiveRow')}))
          (if (and (> {get('NativeFreeColumn')} 0) (<= {get('NativeFreeColumn')} {get('Width')}))
            (if (== {get('NativeFreeColumn')} {get('FirstFreeColumn')})
              {put('PotentialFreeFixedColumn', get('NativeFreeColumn'))})))
        {put('NativeFreeValid', 'false')} {put('NativeFreeColumn', '0')}
        {put('NativeFreeMinimum', '1e30')})
    """


def dummy_relax_item(get, put):
    """Observe the final label from an already visited, unused column j."""
    return f"""
      (if (> j {get('ImplicitWorkerCount')})
        (if (and (> {get('ImplicitWorkerCount')} 0) (< {get('ImplicitWorkerCount')} {get('Width')}))
          (if (== {get('NativeDummyBoundRow')} {get('ActiveRow')})
            (if (< {get('Cur')} {get('NativeDummyBound')}) {put('NativeDummyBound', get('Cur'))})
            (if (== {get('J0')} 0)
              {put('NativeDummyInitCount', f'(+ {get("NativeDummyInitCount")} 1)')}))))
    """


def dummy_relax_finish(get, put):
    """Only a complete first scan witnesses every explicit suffix label."""
    return f"""
      (if (and (== {get('J0')} 0) (== {get('NativeDummyBoundRow')} {get('ActiveRow')}))
        (if (and (> {get('ImplicitWorkerCount')} 0) (< {get('ImplicitWorkerCount')} {get('Width')}))
          (if (== {get('NativeDummyInitCount')} (- {get('Width')} {get('ImplicitWorkerCount')}))
            {put('NativeDummyBoundReady', 'true')})))
    """


def potential_dummy_begin(get, put):
    """Maintain a lower bound once per nonterminal phase, not per chunk."""
    return f"""
      (if (== {get('Cursor')} 0)
        {put('PotentialDummySkip', 'false')}
        (if (and {get('NativeDummyBoundReady')} (== {get('NativeDummyBoundRow')} {get('ActiveRow')}))
          (if (and (> {get('ImplicitWorkerCount')} 0) (< {get('ImplicitWorkerCount')} {get('Width')}))
            (if (== {get('NativeDummyInitCount')} (- {get('Width')} {get('ImplicitWorkerCount')}))
              (if (and {get('NativeUsedRealOnly')} (> {get('PotentialFreeFixedColumn')} 0))
                ; At 2^66 the downward spacing is 8192, so strict Delta<4096
                ; rounds every suffix subtraction back to its original value.
                (if (and (>= {get('NativeDummyBound')} 73786976294838206464.0)
                         (and (>= {get('Delta')} 0.0) (< {get('Delta')} 4096.0)))
                  {put('PotentialDummySkip', 'true')}))
              (if (> {get('Delta')} 0.0)
                {put('NativeDummyBound', f'(- {get("NativeDummyBound")} {get("Delta")})')})))))
      {put('PotentialLoopEnd', get('PotentialEnd'))}
      (if {get('PotentialDummySkip')}
        (if (> {get('PotentialLoopEnd')} (+ {get('ImplicitWorkerCount')} 1))
          {put('PotentialLoopEnd', f'(select (> {get("Cursor")} (+ {get("ImplicitWorkerCount")} 1)) {get("Cursor")} (+ {get("ImplicitWorkerCount")} 1))')}))
    """


def potential_batch_finish(get, put, at):
    """Publish only after this batch reaches the same first free column."""
    return f"""
      (if (> {get('PotentialFreeFixedColumn')} 0)
        (if (and (<= {get('Cursor')} {get('PotentialFreeFixedColumn')})
                 (< {get('PotentialFreeFixedColumn')} {get('PotentialEnd')}))
          {put('NativeFreeMinimum', at('MinV', get('PotentialFreeFixedColumn')))}
          {put('NativeFreeColumn', get('PotentialFreeFixedColumn'))}))
    """


def potential_finish(get, put, at, zero_delta=False):
    """Before potentials_done; a zero delta retains the existing valid cache."""
    continued = "" if zero_delta else f"(else {finish_free_cache(get, put)})"
    return f"""
      (if (== {at('P', get('J1'))} 0)
        {upper_invalidate(get, put)}
        {put('NativeFreeValid', 'false')}
        {put('NativeMaskReady', 'false')}
        {continued})
    """


def potential_item(get, put, at, set_at, collect=True, include_u=True, defer_v=False):
    """One ascending loop-index j; the caller advances Cursor after the batch."""
    if not collect:
        # These arrays are already allocated and every visited index is valid.
        set_at = lambda name, index, value: f"(Variables|SetBy-RefVar :Target {at(name, index)} :Value {value})"
    updated_u = f"(+ {at('U', 'potential_row')} {get('Delta')})"
    update_u = f"(bind potential_row {at('P', 'j')}) {set_at('U', 'potential_row', updated_u)}" if include_u else ''
    update_v = set_at('V', 'j', f'(- {at("V", "j")} {get("Delta")})')
    if defer_v:
        update_v = f'(if (== j 0) {update_v})'
    return f"""
      (if {at('Used', 'j')}
        {update_u}
        {update_v}
        (else
          {put('NativeValue', f'(- {at("MinV", "j")} {get("Delta")})')}
          {set_at('MinV', 'j', get('NativeValue'))}
          {collect_free(get, put, at, value=get('NativeValue'), ascending=True) if collect else ''}))
    """


def candidate_setup(get, put):
    """After existing row setup/first shortcut; SolverState must still equal5."""
    return f"""
      (if (== {get('SolverState')} 5)
        (if {available(get)}
          (if (and (!= {get('J0')} 0) (and {get('NonpositiveV')} {get('RelaxationBoundEnabled')}))
            (if (and {get('NativeFreeValid')} (== {get('NativeFreeRow')} {get('ActiveRow')}))
              (if (or {get('ImplicitFirstPass')} {get('NativeCsrReady')})
                {put('NativePhase', '0')} {put('SolverState', '11')})))))
      (if (== {get('SolverState')} 5) {put('NativeMaskReady', 'false')} {upper_invalidate(get, put)})
    """


def graph(get, put, at, set_at, dense_cost, implicit_cost, relax_done,
          sort_node="Utilities|Array|Sort|SortFloatArray", find_node="Utilities|Array|FindItem",
          integer_minv=None):
    """Cost fragments are the unchanged emitted dense/implicit relax_cost bodies."""
    def length(name):
        return f"(Utilities|Array|Length {get(name)})"

    def sort(name):
        return f"({sort_node} :TargetArray {get(name)} :bStableSort false)"

    def resize(name, last):
        return f"(Utilities|Array|Resize {get(name)} (+ {last} 1))"

    def prefix_empty(index):
        return f'(and {get("NativeDeadLabels")} (== {get("NativeDeadPrefixUsed")} (+ {index} 1)))'

    def prefix_max(index):
        remaining = f'(- {index} {get("NativeDeadPrefixUsed")})'
        safe = f'(select (> {remaining} 0) {remaining} 0)'
        return at('NativeMaxScratch', f'(select {get("NativeDeadLabels")} {safe} {index})')

    global_max_index = f'(select {get("NativeDeadLabels")} (- {get("Width")} {length("UsedColumns")}) {get("Width")})'
    global_setup, global_max = upper_guarded_max(get, put, 'Global',
        f"{put('NativeMaxScratch', get('MinV'))} {resize('NativeMaxScratch', get('Width'))} {sort('NativeMaxScratch')}",
        at('NativeMaxScratch', global_max_index),
        lambda bound: f"(<= {bound} (- 1e20 {get('RowPotential')}))")

    def prefix_setup(index):
        read = prefix_max(index)
        decode = ''
        if integer_minv:
            decode = f'''{put('IntegerMinValue', read)}
              (if {get('IntegerMinActive')}
                (if (not {prefix_empty(index)})
                  {put('IntegerMinIndex', f'({find_node} :TargetArray {get("MinV")} :ItemToFind {get("IntegerMinValue")})')}
                  {integer_minv['load'](get('IntegerMinIndex'))}))'''
            read = get('IntegerMinValue')
        return upper_guarded_max(get, put, 'Prefix',
            f"{put('NativeMaxScratch', get('MinV'))} {resize('NativeMaxScratch', index)} {sort('NativeMaxScratch')} {decode}",
            read,
            lambda bound: f"(or {prefix_empty(index)} (<= {bound} {get('RelaxationLowerBound')}))")

    csr_prefix_setup, csr_prefix_max = prefix_setup('hint')
    implicit_prefix_setup, implicit_prefix_max = prefix_setup(get('ImplicitWorkerCount'))

    count = put("LastStepWork", f"(+ {get('LastStepWork')} 1)")
    increment = put("NativeCursor", f"(+ {get('NativeCursor')} 1)")
    fallback = f"""
      {put('Delta', '1e30')} {put('J1', '0')} {put('BestColumnFree', 'false')}
      {put('Cursor', '1')} {put('SolverState', '5')} {put('NativePhase', '0')}
      {put('NativeMaskReady', 'false')}
      {upper_invalidate(get, put)}
    """
    # The retained worker count is only a prefix-size hint. Sorted unique CSR
    # certifies every column in that prefix; unchanged labels need no visits.
    skip_csr_prefix = f"""
      (if (and {get('NativeCsrReady')} (and {get('NonpositiveV')} {get('RelaxationBoundEnabled')}))
        (bind hint {get('ImplicitWorkerCount')})
        (if (and (> hint 0) (<= hint {get('Cols')}))
          (if (>= (- {get('NativeEnd')} {get('NativeCursor')}) hint)
            (if (== {at('NativeColumns', f'(- (+ {get("NativeCursor")} hint) 1)')} (- hint 1))
              {csr_prefix_setup}
              (if (or {prefix_empty('hint')} (<= {csr_prefix_max} {get('RelaxationLowerBound')}))
                {put('NativeCursor', f'(+ {get("NativeCursor")} hint)')})))))
    """
    choose_range = f"""
      (if {get('ImplicitFirstPass')}
        {put('NativeCursor', get('ImplicitDummyStart'))}
        {put('NativeEnd', get('ImplicitDummyStart'))}
        (if {get('ImplicitDummyAllowed')} {put('NativeEnd', get('ImplicitDummyEnd'))})
        (else
          (if (== {length('NativeRowOffsets')} (+ {get('Rows')} 1))
            {put('NativeCursor', at('NativeRowOffsets', f'(- {get("I0")} 1)'))}
            {put('NativeEnd', at('NativeRowOffsets', get('I0')))}
            (if (or (< {get('NativeCursor')} 0)
                    (or (< {get('NativeEnd')} {get('NativeCursor')}) (> {get('NativeEnd')} {length('NativeColumns')})))
              {fallback}
              (else {skip_csr_prefix}))
            (else {fallback}))))
    """

    def sparse_loop(cost, index):
        return f"""
          (for work (range {get('StepWorkLimit')})
            (if (>= {get('NativeCursor')} {get('NativeEnd')}) (break))
            {put('NativeColumn', index)}
            (if (or (< {get('NativeColumn')} 1) (> {get('NativeColumn')} {get('Cols')}))
              {fallback} {count} (break))
            (bind j {get('NativeColumn')})
            (if (not {at('Used', 'j')})
              {cost}
              {f"(if (> {get('IntegerMinFlushCursor')} 0) {count} (break))" if integer_minv else ''}
              {integer_minv['observe_dummy'] if integer_minv else ''}
              {dummy_relax_item(get, put)}
              (if (and (not {get('NativeDeadLabels')}) {get('NativeMaskReady')}) {set_at('NativeMasked', 'j', at('MinV', 'j'))})
              {collect_free(get, put, at)})
            {increment} {count})
        """

    return f"""
(fn AdvanceNativeRelaxation ()
  {put('LastStepWork', '0')}
  (if {get('Done')} (return))
  (switch int {get('NativePhase')}
    (:0
      {upper_ensure_epoch(get, put)}
      {global_setup}
      (if (<= {global_max} (- 1e20 {get('RowPotential')}))
        {put('NativePhase', '1')}
        (if {get('ImplicitFirstPass')}
          (if (> {get('ImplicitWorkerCount')} 0)
            {implicit_prefix_setup}
            (if (and (not {prefix_empty(get('ImplicitWorkerCount'))})
                     (> {implicit_prefix_max} {get('RelaxationLowerBound')})) {fallback})))
        (if (== {get('SolverState')} 11)
          {choose_range}
          (if (and (not {get('NativeDeadLabels')}) {get('NativeMaskReady')})
            (if (and (== {get('NativeMaskRow')} {get('ActiveRow')})
                     (== {length('NativeMasked')} (+ {get('Width')} 1)))
              {set_at('NativeMasked', get('J0'), '1e30')}
              (else {put('NativeMaskReady', 'false')}))))
        (else {fallback}))
      {count})
    (:1
      (if {get('ImplicitFirstPass')}
        {sparse_loop(implicit_cost, f'(+ {get("NativeCursor")} 1)')}
        (else {sparse_loop(dense_cost, f'(+ {at("NativeColumns", get("NativeCursor"))} 1)')}))
      (if (== {get('SolverState')} 11)
        (if (>= {get('NativeCursor')} {get('NativeEnd')})
            (if {get('NativeDeadLabels')} {put('NativePhase', '4')}
              (else {put('NativePhase', f'(select {get("NativeMaskReady")} 4 2)')}))))
      (if (== {get('LastStepWork')} 0) {count}))
    (:2
      {put('NativeMasked', get('MinV'))} {resize('NativeMasked', get('Width'))}
      {put('NativeCursor', '0')} {put('NativePhase', '3')} {count})
    (:3
      (bind remaining (- {length('UsedColumns')} {get('NativeCursor')}))
      (if (> remaining 0)
        {put('LastStepWork', f'(select (< remaining {get("StepWorkLimit")}) remaining {get("StepWorkLimit")})')}
        {put('NativeMaskEnd', f'(+ {get("NativeCursor")} {get("LastStepWork")})')}
        (for j (range {get('NativeCursor')} {get('NativeMaskEnd')})
          {set_at('NativeMasked', at('UsedColumns', 'j'), '1e30')})
        {put('NativeCursor', get('NativeMaskEnd'))})
      (if (>= {get('NativeCursor')} {length('UsedColumns')}) {put('NativePhase', '4')})
      (if (== {get('LastStepWork')} 0) {count}))
    (:4
      (if {get('NativeDeadLabels')}
        {put('NativeSorted', get('MinV'))} {resize('NativeSorted', get('Width'))}
        (else {put('NativeSorted', get('NativeMasked'))}))
      {sort('NativeSorted')}
      {put('NativeMinimum', at('NativeSorted', '0'))}
      {integer_minv['minimum'] if integer_minv else ''}
      (if (< {get('NativeMinimum')} 1e30)
        (if (== {get('NativeFreeMinimum')} {get('NativeMinimum')})
          {put('J1', get('NativeFreeColumn'))}
          (else
            (if {get('NativeDeadLabels')}
              {put('J1', f'({find_node} :TargetArray {get("MinV")} :ItemToFind ' + (f'(select {get("IntegerMinActive")} {get("IntegerMinRawMinimum")} {get("NativeMinimum")})' if integer_minv else get('NativeMinimum')) + ')')}
              (else {put('J1', f'({find_node} :TargetArray {get("NativeMasked")} :ItemToFind {get("NativeMinimum")})')}))))
        (if (and (> {get('J1')} 0) (<= {get('J1')} {get('Width')}))
          {integer_minv['load'](get('J1'), 'Delta') if integer_minv else put('Delta', at('MinV', get('J1')))}
          {put('BestColumnFree', f'(== {at("P", get("J1"))} 0)')}
          {put('NativeCursor', get('Width'))} {put('NativePhase', '5')}
          (else {fallback}))
        (else {fallback}))
      {count})
    (:5
      (for work (range {get('StepWorkLimit')})
        {count}
        (if (< {get('NativeCursor')} 1) {fallback} (break))
        (if (not {at('Used', get('NativeCursor'))})
          {integer_minv['load'](get('NativeCursor'), 'Cur') if integer_minv else put('Cur', at('MinV', get('NativeCursor')))}
          {put('NativeMaskRow', get('ActiveRow'))} {put('NativeMaskReady', f'(not {get("NativeDeadLabels")})')}
          {finish_free_cache(get, put)} {relax_done} (break))
        {put('NativeCursor', f'(- {get("NativeCursor")} 1)')}))
    (:Default {fallback} {count})))
"""
