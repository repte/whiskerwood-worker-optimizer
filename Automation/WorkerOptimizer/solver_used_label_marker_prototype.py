"""Isolated, unwired used-label marker experiment for editor tests only."""

import copy
import json


MARKER_VARIABLES = {
    "MarkerEnabled": ("bool", False),
    "MarkerInfinity": ("float", False),
    "MarkerRow": ("int", False),
    "MarkerSeenUsed": ("int", False),
    "MarkerPrefixWidth": ("int", False),
    "MarkerPrefixUsed": ("int", False),
    "MarkerMarks": ("int", False),
    "MarkerProbeValues": ("float", True),
    "MarkerProbeSorted": ("float", True),
    "MarkerProbeFound": ("int", False),
}


def step_source():
    """Intercept only a completed state-4 entry and the native phase dispatch.

    Advance fences state 5/6/11, so it cannot consume a freshly used label before
    this wrapper marks it. This deliberately costs extra work versus wiring the
    marker directly at state 4, but keeps the production graph untouched.
    """
    return """
(fn MarkerAdvance ()
  (Variables|Default|SetLastStepWork 0)
  (if (Variables|Default|GetDone) (return))
  (if (<= (Variables|Default|GetStepWorkLimit) 0)
    (Variables|Default|SetDone true) (Variables|Default|SetSucceeded false) (return))
  (if (and (Variables|Default|GetMarkerEnabled)
           (== (Variables|Default|GetSolverState) 11))
    (Variables|Default|SetNativeMaskReady false)
    (Variables|Default|MarkerAdvanceNativeRelaxation)
    (else (Variables|Default|Advance)))
  (if (and (Variables|Default|GetMarkerEnabled)
           (and (Variables|Default|GetNativePlannerTrusted)
                (and (== (Variables|Default|GetDummyCount) 0)
                     (== (Variables|Default|GetWidth) (Variables|Default|GetCols)))))
    (if (or (== (Variables|Default|GetSolverState) 5)
            (or (== (Variables|Default|GetSolverState) 6)
                (== (Variables|Default|GetSolverState) 11)))
      (if (!= (Variables|Default|GetMarkerRow) (Variables|Default|GetActiveRow))
        (Variables|Default|SetMarkerRow (Variables|Default|GetActiveRow))
        (Variables|Default|SetMarkerSeenUsed 0)
        (Variables|Default|SetMarkerPrefixUsed 0)
        (Variables|Default|SetMarkerPrefixWidth
          (select (and (> (Variables|Default|GetImplicitWorkerCount) 0)
                       (<= (Variables|Default|GetImplicitWorkerCount) (Variables|Default|GetCols)))
                  (Variables|Default|GetImplicitWorkerCount) 0)))
      (if (> (Utilities|Array|Length (Variables|Default|GetUsedColumns))
             (Variables|Default|GetMarkerSeenUsed))
        (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetMinV)
          :Index (Variables|Default|GetJ0) :Item (Variables|Default|GetMarkerInfinity))
        (Variables|Default|SetMarkerSeenUsed
          (Utilities|Array|Length (Variables|Default|GetUsedColumns)))
        (Variables|Default|SetMarkerMarks (+ (Variables|Default|GetMarkerMarks) 1))
        (if (<= (Variables|Default|GetJ0) (Variables|Default|GetMarkerPrefixWidth))
          (Variables|Default|SetMarkerPrefixUsed (+ (Variables|Default|GetMarkerPrefixUsed) 1)))))))
"""


def prototype_graphs(graphs, symbol):
    """Derive isolated graphs structurally from the actual emitted reference.

    Used labels are never operands of Hungarian relaxation or subtraction again
    during this augmentation. Infinity sorts after all finite live labels, so
    dropping exactly the known used count yields the true live maximum. The
    separate prefix count includes synthetic column zero. An exhausted prefix
    satisfies the no-improvement certificate vacuously.
    """
    from test_solver_native_relaxation_model import parser, check_structure
    from solver_used_label_marker_legacy_dsl import LEGACY_NATIVE_DSL

    parse, parsed_symbol = parser()

    def convert(value):
        if isinstance(value, parsed_symbol):
            return symbol(str(value))
        return [convert(item) for item in value] if isinstance(value, list) else value

    def get(name):
        return [symbol("Variables|Default|Get" + name)]

    def put(name, value):
        return [symbol("Variables|Default|Set" + name), value]

    def head(value, name):
        return isinstance(value, list) and bool(value) and str(value[0]) == name

    changes = dict(whole_max=0, prefix_max=0, phase_jump=0, mask_get=0, publish=0)

    def rewrite(form):
        if not isinstance(form, list):
            return form
        if head(form, "Variables|Default|GetNativeMasked"):
            changes["mask_get"] += 1
            return get("MinV")
        if head(form, "Variables|Default|SetNativePhase") and head(form[1], "select"):
            assert form[1][1] == get("NativeMaskReady") and form[1][2:] == [4, 2]
            changes["phase_jump"] += 1
            return put("NativePhase", 4)
        if head(form, "Variables|Default|SetNativeMaskReady") and form[1] is True:
            changes["publish"] += 1
            return put("NativeMaskReady", False)
        if len(form) == 3 and str(form[0]) in ("<=", ">"):
            read = form[1]
            if (head(read, "Utilities|Array|Get(aref)") and len(read) == 5
                    and read[2] == get("NativeMaxScratch")):
                index = read[4]
                if index == get("Width"):
                    changed = copy.deepcopy(read)
                    changed[4] = [symbol("-"), index,
                                  [symbol("Utilities|Array|Length"), get("UsedColumns")]]
                    changes["whole_max"] += 1
                    return [form[0], changed, rewrite(form[2])]
                assert index == get("ImplicitWorkerCount") or str(index) == "hint", index
                remaining = [symbol("-"), copy.deepcopy(index), get("MarkerPrefixUsed")]
                changed = copy.deepcopy(read)
                changed[4] = [symbol("select"), [symbol(">"), remaining, 0], remaining, 0]
                empty = [symbol("=="), get("MarkerPrefixUsed"), [symbol("+"), index, 1]]
                comparison = [form[0], changed, rewrite(form[2])]
                changes["prefix_max"] += 1
                if str(form[0]) == "<=":
                    return [symbol("or"), empty, comparison]
                return [symbol("and"), [symbol("not"), empty], comparison]
        return [rewrite(item) for item in form]

    result = copy.deepcopy(graphs)
    # Keep this experiment independent after the production native graph changes.
    native = rewrite(convert(parse(LEGACY_NATIVE_DSL)))
    native[0][1] = symbol("MarkerAdvanceNativeRelaxation")
    # Keep switch cases contiguous, but make formerly budgeted masking phases
    # explicitly unreachable. No production phase is renumbered.
    switch = next(item for item in native[0] if head(item, "switch"))
    for i, case in enumerate(switch):
        if isinstance(case, list) and str(case[0]) in (":2", ":3"):
            switch[i] = [case[0], put("Done", True), put("Succeeded", False), put("LastStepWork", 1)]
        if isinstance(case, list) and str(case[0]) == ":4":
            assert head(case[1], "Variables|Default|SetNativeSorted")
            # Initialize reserves storage for private dummies even when they
            # are later disabled. Never sort that inactive zero-filled tail.
            case.insert(2, [symbol("Utilities|Array|Resize"), get("NativeSorted"),
                            [symbol("+"), get("Width"), 1]])
    result["MarkerAdvanceNativeRelaxation"] = native
    result["MarkerAdvance"] = convert(parse(step_source()))
    assert changes["whole_max"] == 1 and changes["prefix_max"] == 2, changes
    assert changes["phase_jump"] == 1 and changes["mask_get"] >= 2 and changes["publish"] == 1, changes
    check_structure(result)
    return result


def render(forms, symbol):
    """Serialize the parsed prototype for the real editor transpiler."""
    def value(item):
        if isinstance(item, list):
            return "(" + " ".join(value(child) for child in item) + ")"
        if isinstance(item, symbol):
            name = str(item)
            return ":" + json.dumps(name[1:]) if name.startswith(":") and " " in name else name
        if isinstance(item, bool):
            return "true" if item else "false"
        if isinstance(item, str):
            return json.dumps(item)
        return repr(item)
    return "\n".join(value(form) for form in forms)
