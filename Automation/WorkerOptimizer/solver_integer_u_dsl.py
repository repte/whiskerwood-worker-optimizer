"""Exact, opt-in integer potential deferral shared by the production generator.

The opt-in and native trust are immutable between initialization and completion.
The default certificate accepts finite integers within +/-2^50. The optional
eighths certificate accepts multiples of 1/8 within +/-2^48; stored values and
arithmetic remain in their original units. With defer_v, certified nonzero
Used-V entries share the offset.
V[0] and MinV remain eager; all pending potentials flush before P mutation.
This module imports no Unreal, parser, model, or test support.
"""

LIMIT = 2 ** 50
EIGHTHS_LIMIT = 2 ** 48
INTEGER_U_TYPES = {
    'bool': 'IntegerUEnabled IntegerUActive IntegerURowPrepared IntegerUPhasePrepared IntegerUPhaseTerminal IntegerUPhaseNonzero IntegerUCertified DyadicEighthsEnabled',
    'int': 'IntegerURoot IntegerUEpoch IntegerUFlushMode IntegerUFlushCursor',
    'float': 'IntegerUTotal IntegerUProbe',
    'float[]': 'IntegerUOffsets',
    'int[]': 'IntegerUEpochs',
}


def sources(floor64_node='Math|Float|FloortoInteger64', call_function=None, defer_v=False):
    g = lambda name: f'(Variables|Default|Get{name})'
    s = lambda name, value: f'(Variables|Default|Set{name} {value})'
    a = lambda name, index: f'(Utilities|Array|Get(aref) :Array {g(name)} :"Dimension 1" {index})'
    put = lambda name, index, value: f'(Utilities|Array|SetArrayElem :TargetArray {g(name)} :Index {index} :Item {value})'
    call = call_function or (lambda name: f'(Variables|Default|{name})')
    available = f'(and {g("NativePlannerTrusted")} (and (== {g("DummyCount")} 0) (== {g("Width")} {g("Cols")})))'
    check_v = f'''(if (> {g('J0')} 0)
      {s('IntegerUProbe', a('V', g('J0')))} {call('IntegerUCheckValue')}
      (if (not {g('IntegerUCertified')})
        {s('IntegerUFlushMode', '3')} {s('IntegerUFlushCursor', '0')} (return)))''' if defer_v else ''
    flush_v = f'''(if (> column 0)
      {put('V', 'column', f'(- {a("V", "column")} (- {g("IntegerUTotal")} {a("IntegerUOffsets", "column")}))')}
      ; At least one nonzero exact subtraction occurred in this epoch.
      (if (== {a('V', 'column')} 0.0) {put('V', 'column', '0.0')}))''' if defer_v else ''
    reset = '\n'.join([
        *(s(name, 'false') for name in INTEGER_U_TYPES['bool'].split()),
        *(s(name, '0') for name in INTEGER_U_TYPES['int'].split()),
        s('IntegerURoot', '-1'), s('IntegerUTotal', '0.0'), s('IntegerUProbe', '0.0'),
        f'(Utilities|Array|Clear {g("IntegerUOffsets")})',
        f'(Utilities|Array|Clear {g("IntegerUEpochs")})'])
    return {
        'IntegerUReset': f'(fn IntegerUReset () {reset})',
        'IntegerUCheckValue': f'''(fn IntegerUCheckValue ()
          {s('IntegerUCertified', 'false')}
          (if {g('DyadicEighthsEnabled')}
            (if (and (>= {g('IntegerUProbe')} {-EIGHTHS_LIMIT}.0) (<= {g('IntegerUProbe')} {EIGHTHS_LIMIT}.0))
              {s('IntegerUCertified', f'(== (* {g("IntegerUProbe")} 8.0) ({floor64_node} :A (* {g("IntegerUProbe")} 8.0)))')})
            (else
              (if (and (>= {g('IntegerUProbe')} {-LIMIT}.0) (<= {g('IntegerUProbe')} {LIMIT}.0))
                {s('IntegerUCertified', f'(== {g("IntegerUProbe")} ({floor64_node} :A {g("IntegerUProbe")}))')}))))''',
        'IntegerUPrepareRow': f'''(fn IntegerUPrepareRow ()
          {s('LastStepWork', '1')}
          (if (!= {g('IntegerURoot')} {g('ActiveRow')})
            {s('IntegerURoot', g('ActiveRow'))} {s('IntegerUTotal', '0.0')} {s('IntegerUEpoch', '0')}
            {s('IntegerUActive', f'(and {available} (and (== {g("J0")} 0) (== (Utilities|Array|Length {g("UsedColumns")}) 0)))')}
            {s('IntegerUPhasePrepared', 'false')}
            (Utilities|Array|Resize {g('IntegerUOffsets')} (+ {g('Width')} 1))
            (Utilities|Array|Resize {g('IntegerUEpochs')} (+ {g('Width')} 1)))
          (if {g('IntegerUActive')}
            {s('IntegerUProbe', a('U', a('P', g('J0'))))} {call('IntegerUCheckValue')}
            (if (not {g('IntegerUCertified')})
              {s('IntegerUFlushMode', '3')} {s('IntegerUFlushCursor', '0')} (return))
            {check_v}
            {put('IntegerUOffsets', g('J0'), g('IntegerUTotal'))}
            {put('IntegerUEpochs', g('J0'), g('IntegerUEpoch'))})
          {s('IntegerURowPrepared', 'true')})''',
        'IntegerUFlush': f'''(fn IntegerUFlush ()
          (for work (range {g('StepWorkLimit')})
            {s('LastStepWork', '(+ work 1)')}
            (if (< {g('IntegerUFlushCursor')} (Utilities|Array|Length {g('UsedColumns')}))
              (bind column {a('UsedColumns', g('IntegerUFlushCursor'))})
              (if (!= {a('IntegerUEpochs', 'column')} {g('IntegerUEpoch')})
                (bind row {a('P', 'column')})
                {put('U', 'row', f'(+ {a("U", "row")} (- {g("IntegerUTotal")} {a("IntegerUOffsets", "column")}))')}
                {flush_v}
                {put('IntegerUOffsets', 'column', g('IntegerUTotal'))}
                {put('IntegerUEpochs', 'column', g('IntegerUEpoch'))})
              {s('IntegerUFlushCursor', f'(+ {g("IntegerUFlushCursor")} 1)')}
              (else
                (if (== {g('IntegerUFlushMode')} 2) {s('SolverState', '7')}
                  (else {s('IntegerUActive', 'false')}))
                {s('IntegerUFlushMode', '0')} {s('IntegerUPhasePrepared', 'false')}
                {s('IntegerUPhaseNonzero', 'false')} (break)))))''',
        'IntegerUAdvancePotentials': f'''(fn IntegerUAdvancePotentials ()
          (if (not {g('IntegerUActive')}) {call('AdvancePotentials')} (return))
          (if (not {g('IntegerUPhasePrepared')})
            {s('IntegerUPhaseTerminal', f'(== {a("P", g("J1"))} 0)')}
            {s('IntegerUPhaseNonzero', f'(!= {g("Delta")} 0.0)')}
            (if {g('IntegerUPhaseNonzero')}
              {s('IntegerUProbe', g('Delta'))} {call('IntegerUCheckValue')}
              (if {g('IntegerUCertified')}
                {s('IntegerUProbe', f'(+ {g("IntegerUTotal")} {g("Delta")})')} {call('IntegerUCheckValue')})
              (if (not {g('IntegerUCertified')})
                {s('IntegerUFlushMode', '1')} {s('IntegerUFlushCursor', '0')}
                {s('LastStepWork', '1')} (return))
              {s('IntegerUTotal', g('IntegerUProbe'))} {s('IntegerUEpoch', f'(+ {g("IntegerUEpoch")} 1)')})
            {s('IntegerUPhasePrepared', 'true')})
          {call('IntegerUDeferredPotentials')}
          (if (!= {g('SolverState')} 6)
            {s('IntegerUPhasePrepared', 'false')} {s('IntegerUPhaseNonzero', 'false')}
            (if (and (== {g('SolverState')} 7) (> {g('IntegerUEpoch')} 0))
              {s('IntegerUFlushMode', '2')} {s('IntegerUFlushCursor', '0')}
              {s('SolverState', '6')})))''',
    }


INTEGER_U_VARIABLES = {
    name: (kind.removesuffix('[]'), kind.endswith('[]'))
    for kind, names in INTEGER_U_TYPES.items() for name in names.split()
}
INTEGER_U_DEFAULTS = {
    name: ([] if array else False if kind == 'bool' else 0.0 if kind == 'float' else 0)
    for name, (kind, array) in INTEGER_U_VARIABLES.items()
}
INTEGER_U_DEFAULTS['IntegerURoot'] = -1


def enabled(get):
    return f'(and {get("IntegerUEnabled")} (and {get("NativePlannerTrusted")} (and (== {get("DummyCount")} 0) (== {get("Width")} {get("Cols")}))))'


def advance_dispatch(get, call):
    """Insert after Done/invalid-budget guards, before ordinary state dispatch."""
    return f'''
      (if {enabled(get)}
        (if (> {get('IntegerUFlushMode')} 0) {call('IntegerUFlush')} (return))
        (if (and (== {get('SolverState')} 4) (not {get('IntegerURowPrepared')}))
          {call('IntegerUPrepareRow')}
          ; Keep pending-label and failed preparations at their original fence.
          (if (not (and (>= {get('StepWorkLimit')} 2)
            (and {get('IntegerURowPrepared')}
              (and (== {get('IntegerUFlushMode')} 0) (not {get('IntegerMinActive')})))))
            (return)))
        (if (== {get('SolverState')} 6) {call('IntegerUAdvancePotentials')} (return)))
    '''


def state4_fence(get):
    """OR into the existing loop-entry fence for phases5/6/11."""
    return f'(and {enabled(get)} (and (== {get("SolverState")} 4) (not {get("IntegerURowPrepared")})))'


def state4_complete(put):
    """Append to the existing state4 body after its unchanged row setup."""
    return put('IntegerURowPrepared', 'false')


def initialize_reset(call):
    return call('IntegerUReset')
