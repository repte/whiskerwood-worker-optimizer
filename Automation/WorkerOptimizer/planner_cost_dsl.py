"""Inline score expressions shared by dense planning and implicit first passes.

These helpers return DSL statements, not Blueprint function calls. Addition order
is part of the exact planner contract and must not be algebraically regrouped.
"""


IMPLICIT_VARIABLES = {
    "ImplicitFirstPass": ("bool", False), "ImplicitWorkerCount": ("int", False),
    "ImplicitFillBonus": ("float", False), "ImplicitCoverageBonus": ("float", False),
    "ImplicitColumnBonus": ("float", False), "ImplicitScores": ("float", True),
    "ImplicitModes": ("int", True), "ImplicitMultipliers": ("int", True),
    "ImplicitMinimumRows": ("bool", True), "ImplicitRealRows": ("bool", True),
    "ImplicitDummyRows": ("bool", True), "ImplicitFixedWorkers": ("int", True),
    "ImplicitDummyStarts": ("int", True), "ImplicitDummyEnds": ("int", True),
    "ImplicitRowOffset": ("int", False), "ImplicitMode": ("int", False),
    "ImplicitMultiplier": ("int", False), "ImplicitMinimum": ("bool", False),
    "ImplicitRealAllowed": ("bool", False), "ImplicitDummyAllowed": ("bool", False),
    "ImplicitFixedWorker": ("int", False), "ImplicitDummyStart": ("int", False),
    "ImplicitDummyEnd": ("int", False), "ImplicitBaseValue": ("float", False),
}


def implicit_row_setup(get, put, at, row):
    """Cache one row's metadata once, outside its relaxation/refinement loop."""
    fields = {
        "ImplicitMode": "ImplicitModes", "ImplicitMultiplier": "ImplicitMultipliers",
        "ImplicitMinimum": "ImplicitMinimumRows", "ImplicitRealAllowed": "ImplicitRealRows",
        "ImplicitDummyAllowed": "ImplicitDummyRows", "ImplicitFixedWorker": "ImplicitFixedWorkers",
        "ImplicitDummyStart": "ImplicitDummyStarts", "ImplicitDummyEnd": "ImplicitDummyEnds",
    }
    return put("ImplicitRowOffset", f'(* {row} {get("ImplicitWorkerCount")})') + "\n" + "\n".join(
        put(target, at(source, row)) for target, source in fields.items())


def implicit_score(get, put, at, worker, output="Cur"):
    """Emit the planner's exact score for a zero-based explicit column."""
    return first_pass_score(
        get, put, output=output, base_output="ImplicitBaseValue",
        base=at("ImplicitScores", f'(+ {get("ImplicitRowOffset")} {worker})'),
        worker=worker, workers=get("ImplicitWorkerCount"), mode=get("ImplicitMode"),
        multiplier=get("ImplicitMultiplier"), minimum=get("ImplicitMinimum"),
        fixed=get("ImplicitFixedWorker"), real_allowed=get("ImplicitRealAllowed"),
        dummy_allowed=get("ImplicitDummyAllowed"), dummy_start=get("ImplicitDummyStart"),
        dummy_end=get("ImplicitDummyEnd"), fill=get("ImplicitFillBonus"),
        coverage=get("ImplicitCoverageBonus"), column=get("ImplicitColumnBonus"))


def allowed_score(get, put, *, output, base, mode, multiplier, minimum,
                  required, fill, coverage, column, real=None):
    """Emit an already-eligible edge's score in its original operation order."""
    real_score = f"""
      (if (== {mode} 1) {put(output, f'(+ {fill} {base})')}
        (elif (== {mode} 2) {put(output, f'(+ {fill} (* {base} {multiplier}))')}
          (elif (== {mode} 3) {put(output, base)})))
      (if {minimum} {put(output, f'(+ {get(output)} {coverage})')})
    """
    if real is not None:
        real_score = f"(if {real} {real_score})"
    return f"""
      {put(output, '0.0')}
      {real_score}
      (if {required} {put(output, f'(+ {get(output)} {column})')})
    """


def first_pass_score(get, put, *, output, base_output, base, worker, workers,
                     mode, multiplier, minimum, fixed, real_allowed,
                     dummy_allowed, dummy_start, dummy_end, fill, coverage,
                     column):
    """Emit a first-pass score using a zero-based explicit column index.

    Real source scores have already been fixed-owner masked and validated.
    Dummy intervals are half-open in the explicit column domain. RequiredWorker
    initially contains only fixed workers, so no explicit dummy has that bonus.
    """
    real_score = allowed_score(
        get, put, output=output, base=get(base_output), mode=mode,
        multiplier=multiplier, minimum=minimum, required=f'(== {worker} {fixed})',
        fill=fill, coverage=coverage, column=column)
    return f"""
      {put(output, '-1e20')}
      (if (< {worker} {workers})
        (if {real_allowed}
          {put(base_output, base)}
          (if (>= {get(base_output)} 0.0) {real_score}))
        (else
          (if (and {dummy_allowed} (and (>= {worker} {dummy_start}) (< {worker} {dummy_end})))
            {put(output, '0.0')})))
    """


def accumulate_row_statistics(get, put, *, value, column, first_column,
                              first_score, maximum_column, maximum_score,
                              prefix_score, second_score=None):
    """Accumulate eligible values; score accumulators start at -1e20."""
    promote_second = put(second_score, get(maximum_score)) if second_score else ""
    update_second = (f'(elif (> {value} {get(second_score)}) {put(second_score, value)})'
                     if second_score else "")
    return f"""
      (if (>= {value} 0.0)
        (if (== {get(first_column)} 0)
          {put(first_column, column)} {put(first_score, value)})
        (if (> {value} {get(maximum_score)})
          {put(prefix_score, get(maximum_score))}
          {promote_second}
          {put(maximum_score, value)} {put(maximum_column, column)}
          {update_second}))
    """


def first_pass_row_minimum(get, put, *, score_output, column_output,
                          scratch_output, first_column, first_score,
                          maximum_column, maximum_score, prefix_score, mode,
                          multiplier, minimum, fixed, real_allowed,
                          dummy_allowed, dummy_start, dummy_end, fill,
                          coverage, column, second_score=None, second_output=None):
    """Emit an exact maximum score with a certified first winning column.

    Zero denotes an unknown first column, not an unknown minimum value. Rounding
    can merge unequal raw scores, so a prefix tie deliberately disables only the
    shortcut; the ordinary Hungarian scan still chooses the original winner.
    """
    def transformed(value, output):
        return allowed_score(
            get, put, output=output, base=value, mode=mode,
            multiplier=multiplier, minimum=minimum, required=f'(>= {fixed} 0)',
            fill=fill, coverage=coverage, column=column)

    second_minimum = ""
    if second_output is not None:
        assert second_score is not None
        # Two sentinel candidates also cover a missing second explicit column.
        # One legal dummy joins a real candidate; two dummies suffice alone.
        second_minimum = f"""
          {put(second_output, '-1e20')}
          (if (and {real_allowed} (>= {second_score} 0.0))
            {transformed(second_score, second_output)})
          (if (and {dummy_allowed} (< {dummy_start} {dummy_end}))
            (if (or (> (- {dummy_end} {dummy_start}) 1) (and {real_allowed} (> {first_column} 0)))
              (if (> 0.0 {get(second_output)}) {put(second_output, '0.0')})))
        """
    return f"""
      {put(score_output, '-1e20')} {put(column_output, '1')}
      (if (and {real_allowed} (> {first_column} 0))
        {transformed(maximum_score, score_output)}
        {transformed(first_score, scratch_output)}
        (if (== {get(scratch_output)} {get(score_output)})
          {put(column_output, first_column)}
          (else
            {transformed(prefix_score, scratch_output)}
            (if (< {get(scratch_output)} {get(score_output)})
              {put(column_output, maximum_column)}
              (else {put(column_output, '0')})))))
      (if (and {dummy_allowed} (< {dummy_start} {dummy_end}))
        (if (> 0.0 {get(score_output)})
          {put(score_output, '0.0')} {put(column_output, f'(+ {dummy_start} 1)')}))
      {second_minimum}
    """
