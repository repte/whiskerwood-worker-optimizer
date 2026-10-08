"""Unwired integer-only U deferral, emitted as private prototype graphs.

Opt in only after an IntegerUInitialize* call and keep the flag/native trust
immutable until completion or reinitialization. Generic/disabled calls delegate
to the unchanged solver. V and MinV arithmetic is never rewritten. A pending
phase uses the ordinary Cursor to distinguish processed and unprocessed rows.
"""

import copy


from solver_integer_u_dsl import LIMIT, INTEGER_U_TYPES as INTEGER_U_VARIABLES, sources


def prototype_graphs(reference, symbol):
    from test_solver_native_relaxation_model import parser, check_structure
    parse, parsed_symbol = parser()

    def convert(value):
        if isinstance(value, list):
            return [convert(item) for item in value]
        return symbol(str(value)) if isinstance(value, parsed_symbol) else value

    def forms(source):
        return convert(parse(source))

    def head(value, name):
        return isinstance(value, list) and bool(value) and str(value[0]) == name

    def get(name):
        return [symbol('Variables|Default|Get' + name)]

    result = copy.deepcopy(reference)
    result.update({name: forms(source) for name, source in sources().items()})
    for original in ('Initialize', 'InitializeImplicitFirstPass'):
        graph = copy.deepcopy(reference[original])
        graph[0][1] = symbol('IntegerU' + original)
        graph[0].insert(3, [symbol('Variables|Default|IntegerUReset')])
        result['IntegerU' + original] = graph
    removed = 0

    def omit_u(value):
        nonlocal removed
        if not isinstance(value, list):
            return value
        output = []
        for item in value:
            array_u = head(item, 'Utilities|Array|SetArrayElem') and item[2] == get('U')
            ref_u = (head(item, 'Variables|SetBy-RefVar')
                     and head(item[2], 'Utilities|Array|Get(aref)') and item[2][2] == get('U'))
            if array_u or ref_u:
                removed += 1
            else:
                output.append(omit_u(item))
        return output

    graph = omit_u(copy.deepcopy(reference['AdvancePotentials']))
    graph[0][1] = symbol('IntegerUDeferredPotentials')
    result['IntegerUDeferredPotentials'] = graph
    assert removed == 4, ('Only the four eager U-update sites may be omitted', removed)

    graph = copy.deepcopy(reference['Advance'])
    graph[0][1] = symbol('IntegerUAdvance')
    guard = forms('''(if (or (not (Variables|Default|GetIntegerUEnabled))
      (not (and (Variables|Default|GetNativePlannerTrusted)
        (and (== (Variables|Default|GetDummyCount) 0)
             (== (Variables|Default|GetWidth) (Variables|Default|GetCols))))))
      (Variables|Default|Advance) (return))''')[0]
    graph[0].insert(3, guard)
    # Place private dispatch after the unchanged Done and invalid-budget guards.
    insertion = next(i for i, item in enumerate(graph[0])
                     if head(item, 'if') and head(item[1], '==')
                     and item[1][1] == get('SolverState') and item[1][2] == 5)
    graph[0][insertion:insertion] = forms('''
      (if (> (Variables|Default|GetIntegerUFlushMode) 0)
        (Variables|Default|IntegerUFlush) (return))
      (if (and (== (Variables|Default|GetSolverState) 4)
               (not (Variables|Default|GetIntegerURowPrepared)))
        (Variables|Default|IntegerUPrepareRow) (return))''')

    def replace_calls(value):
        if not isinstance(value, list):
            return value
        if head(value, 'Variables|Default|AdvancePotentials'):
            return [symbol('Variables|Default|IntegerUAdvancePotentials')]
        return [replace_calls(item) for item in value]

    graph = replace_calls(graph)
    loop = next(item for item in graph[0] if head(item, 'for'))
    fence = loop[4]
    assert head(fence, 'if') and fence[-1] == [symbol('break')]
    fence[1] = [symbol('or'), fence[1], forms('''(and
      (== (Variables|Default|GetSolverState) 4)
      (not (Variables|Default|GetIntegerURowPrepared)))''')[0]]
    switch = next(item for item in loop if head(item, 'switch'))
    row_case = next(item for item in switch if head(item, ':4'))
    row_case.append([symbol('Variables|Default|SetIntegerURowPrepared'), False])
    result['IntegerUAdvance'] = graph
    check_structure(result)
    return result


def projected_u(state):
    """Expose the eager per-call U view without mutating deferred storage."""
    result = list(state['U'])
    if not state.get('IntegerUEnabled') or not state.get('IntegerUActive'):
        return result
    for position, column in enumerate(state.get('UsedColumns', [])):
        row = state['P'][column]
        prefix, epoch = state['IntegerUTotal'], state['IntegerUEpoch']
        if state.get('IntegerUPhasePrepared') and state.get('IntegerUPhaseNonzero'):
            processed = position < state['Cursor'] if state['IntegerUPhaseTerminal'] else column < state['Cursor']
            if not processed:
                prefix = prefix - state['Delta']
                epoch -= 1
        if state['IntegerUEpochs'][column] != epoch:
            result[row] = result[row] + (prefix - state['IntegerUOffsets'][column])
    return result
