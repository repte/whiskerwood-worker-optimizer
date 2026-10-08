"""Exact native selection within the existing Hungarian solver.

Only the planner may enable trust after an initializer. Omitted CSR edges must
have score -1e20, indices must be sorted/unique, and universal dummies are absent.
The generic public solver defaults to its existing dense path. Integrators must
dispatch SolverState 11 with the same phase fence/cancellation as states 5/6.
"""


NATIVE_VARIABLES = {
    "NativePlannerTrusted": ("bool", False), "NativeCsrReady": ("bool", False),
    "NativeFreeValid": ("bool", False), "NativeFreeRow": ("int", False),
    "NativeFreeColumn": ("int", False), "NativeFreeMinimum": ("float", False),
    "NativeMaskReady": ("bool", False), "NativeMaskRow": ("int", False),
    "NativePhase": ("int", False), "NativeCursor": ("int", False),
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
        put("NativePlannerTrusted", "false"), put("NativeCsrReady", "false"),
        put("NativeFreeValid", "false"), put("NativeFreeRow", "0"),
        put("NativeMaskReady", "false"), put("NativeMaskRow", "0"),
        put("NativeFreeColumn", "0"), put("NativeFreeMinimum", "1e30"),
        put("NativePhase", "0"), put("NativeCursor", "0"), put("NativeEnd", "0"),
        *[f"(Utilities|Array|Clear {get(name)})" for name in arrays]])


def begin_row_reset(get, put):
    return f"""
      {put('NativeFreeValid', 'false')} {put('NativeFreeRow', get('ActiveRow'))}
      {put('NativeMaskReady', 'false')} {put('NativeMaskRow', get('ActiveRow'))}
      {put('NativeFreeColumn', '0')} {put('NativeFreeMinimum', '1e30')}
      {put('NativePhase', '0')} {put('NativeCursor', '0')}
    """


def collect_free(get, put, at, column="j", value=None):
    value = get("Cur") if value is None else value
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
      (if (== {get('Cursor')} 0)
        {put('NativeFreeValid', 'false')} {put('NativeFreeColumn', '0')}
        {put('NativeFreeMinimum', '1e30')})
    """


def potential_finish(get, put, at, zero_delta=False):
    """Before potentials_done; a zero delta retains the existing valid cache."""
    continued = "" if zero_delta else f"(else {finish_free_cache(get, put)})"
    return f"""
      (if (== {at('P', get('J1'))} 0)
        {put('NativeFreeValid', 'false')}
        {put('NativeMaskReady', 'false')}
        {continued})
    """


def potential_item(get, put, at, set_at):
    """Choose this variant once per batch when available(); otherwise unchanged."""
    matched_row = at("P", "j")
    updated_u = f"(+ {at('U', matched_row)} {get('Delta')})"
    return f"""
      (bind j {get('Cursor')})
      (if {at('Used', 'j')}
        {set_at('U', matched_row, updated_u)}
        {set_at('V', 'j', f'(- {at("V", "j")} {get("Delta")})')}
        (else
          {put('NativeValue', f'(- {at("MinV", "j")} {get("Delta")})')}
          {set_at('MinV', 'j', get('NativeValue'))}
          {collect_free(get, put, at, value=get('NativeValue'))}))
      {put('Cursor', f'(+ {get("Cursor")} 1)')}
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
      (if (== {get('SolverState')} 5) {put('NativeMaskReady', 'false')})
    """


def graph(get, put, at, set_at, dense_cost, implicit_cost, relax_done,
          sort_node="Utilities|Array|Sort|SortFloatArray", find_node="Utilities|Array|FindItem"):
    """Cost fragments are the unchanged emitted dense/implicit relax_cost bodies."""
    def length(name):
        return f"(Utilities|Array|Length {get(name)})"

    def sort(name):
        return f"({sort_node} :TargetArray {get(name)} :bStableSort false)"

    def resize(name, last):
        return f"(Utilities|Array|Resize {get(name)} (+ {last} 1))"

    count = put("LastStepWork", f"(+ {get('LastStepWork')} 1)")
    increment = put("NativeCursor", f"(+ {get('NativeCursor')} 1)")
    fallback = f"""
      {put('Delta', '1e30')} {put('J1', '0')} {put('BestColumnFree', 'false')}
      {put('Cursor', '1')} {put('SolverState', '5')} {put('NativePhase', '0')}
      {put('NativeMaskReady', 'false')}
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
              {fallback})
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
              (if {get('NativeMaskReady')} {set_at('NativeMasked', 'j', at('MinV', 'j'))})
              {collect_free(get, put, at)})
            {increment} {count})
        """

    return f"""
(fn AdvanceNativeRelaxation ()
  {put('LastStepWork', '0')}
  (if {get('Done')} (return))
  (switch int {get('NativePhase')}
    (:0
      {put('NativeMaxScratch', get('MinV'))} {resize('NativeMaxScratch', get('Width'))}
      {sort('NativeMaxScratch')}
      (if (<= {at('NativeMaxScratch', get('Width'))} (- 1e20 {get('RowPotential')}))
        {put('NativePhase', '1')}
        (if {get('ImplicitFirstPass')}
          (if (> {get('ImplicitWorkerCount')} 0)
            {put('NativeMaxScratch', get('MinV'))}
            {resize('NativeMaxScratch', get('ImplicitWorkerCount'))}
            {sort('NativeMaxScratch')}
            (if (> {at('NativeMaxScratch', get('ImplicitWorkerCount'))} {get('RelaxationLowerBound')}) {fallback})))
        (if (== {get('SolverState')} 11)
          {choose_range}
          (if {get('NativeMaskReady')}
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
          {put('NativePhase', f'(select {get("NativeMaskReady")} 4 2)')}))
      (if (== {get('LastStepWork')} 0) {count}))
    (:2
      {put('NativeMasked', get('MinV'))} {resize('NativeMasked', get('Width'))}
      {put('NativeCursor', '0')} {put('NativePhase', '3')} {count})
    (:3
      (for work (range {get('StepWorkLimit')})
        (if (>= {get('NativeCursor')} {length('UsedColumns')}) (break))
        {set_at('NativeMasked', at('UsedColumns', get('NativeCursor')), '1e30')}
        {increment} {count})
      (if (>= {get('NativeCursor')} {length('UsedColumns')}) {put('NativePhase', '4')})
      (if (== {get('LastStepWork')} 0) {count}))
    (:4
      {put('NativeSorted', get('NativeMasked'))} {sort('NativeSorted')}
      {put('NativeMinimum', at('NativeSorted', '0'))}
      (if (< {get('NativeMinimum')} 1e30)
        (if (== {get('NativeFreeMinimum')} {get('NativeMinimum')})
          {put('J1', get('NativeFreeColumn'))}
          (else {put('J1', f'({find_node} :TargetArray {get("NativeMasked")} :ItemToFind {get("NativeMinimum")})')}))
        (if (and (> {get('J1')} 0) (<= {get('J1')} {get('Width')}))
          {put('Delta', at('MinV', get('J1')))}
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
          {put('Cur', at('MinV', get('NativeCursor')))}
          {put('NativeMaskRow', get('ActiveRow'))} {put('NativeMaskReady', 'true')}
          {finish_free_cache(get, put)} {relax_done} (break))
        {put('NativeCursor', f'(- {get("NativeCursor")} 1)')}))
    (:Default {fallback} {count})))
"""
