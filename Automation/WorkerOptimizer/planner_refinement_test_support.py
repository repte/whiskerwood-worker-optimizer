"""Independent work oracle for first-pass refinement reconstruction."""


def implicit_refinement_work(planner):
    get = planner.get_editor_property
    rows, workers = get("SlotCount"), get("WorkerCount")
    maximum = max(get("V")[1:workers + 1]) if workers else None
    base = list(get("ImplicitScores"))
    caches = {}
    visits = 0
    for row in range(rows):
        real, fixed = get("ImplicitRealRows")[row], get("ImplicitFixedWorkers")[row]
        values = base[row * workers:(row + 1) * workers]
        winner, second = get("RowMinColumn")[row], get("RowSecondMinCost")[row]
        potential = get("U")[row + 1]
        singleton = (real and workers > 0 and 1 <= winner <= workers
                     and ((second - potential) - maximum) > 0.00001)
        full = workers > 1 and real and fixed < 0 and all(value >= 0.0 for value in values)
        mode, minimum = get("ImplicitModes")[row], get("ImplicitMinimumRows")[row]
        constant = mode == 0 or (mode in (1, 2) and values and all(value == values[0] for value in values))
        cacheable = full and constant and not singleton
        hit = False
        if cacheable:
            score = 0.0
            if mode == 1:
                score = get("ImplicitFillBonus") + values[0]
            elif mode == 2:
                score = get("ImplicitFillBonus") + (values[0] * get("ImplicitMultipliers")[row])
            if minimum:
                score = score + get("ImplicitCoverageBonus")
            key = (score, potential)
            hit = caches.get(minimum) == key
            caches[minimum] = key
        if real and not hit:
            visits += 1 if singleton or fixed >= 0 else workers
        if get("ImplicitDummyRows")[row]:
            visits += get("ImplicitDummyEnds")[row] - get("ImplicitDummyStarts")[row]
    return 2 + workers + 2 * rows + visits


def refinement_work(planner):
    get = planner.get_editor_property
    if get("ImplicitFirstPass"):
        return implicit_refinement_work(planner)
    rows, workers, columns = get("SlotCount"), get("WorkerCount"), get("SolveColumns")
    retained, offsets = list(get("RetainedColumns")), list(get("RetainedRowOffsets"))
    if not get("RetainedReady"):
        return rows * max(columns, 1) + 2
    if len(get("SentinelRow")) != columns:
        return len(retained) + sum(a == b for a, b in zip(offsets, offsets[1:])) + 2
    maximum = max(get("V")[1:workers + 1]) if workers else None
    base, caches, visits = list(get("BaseScores")), {}, 0
    for row in range(rows):
        edges = retained[offsets[row]:offsets[row + 1]]
        real = [column for column in edges if column < workers]
        full = workers > 1 and real == list(range(workers))
        potential = get("U")[row + 1]
        winner = get("RowMinColumn")[row]
        singleton = (full and 1 <= winner <= workers
                     and ((get("RowSecondMinCost")[row] - potential) - maximum) > 0.00001)
        priority = get("Priorities")[get("SlotBuildings")[row]]
        tier = get("Tier")
        mode = ((2 if not get("StrictMode") else int(priority == tier))
                if priority >= 0 and tier >= 0 else int(priority < 0 and tier < 0) * 3)
        values = base[row * workers:(row + 1) * workers]
        uniform = bool(values) and all(value == values[0] for value in values)
        cacheable = full and not singleton and (mode == 0 or (mode in (1, 2) and uniform))
        hit = False
        if cacheable:
            score = 0.0
            if mode == 1:
                score = get("FillBonus") + values[0]
            elif mode == 2:
                score = get("FillBonus") + (values[0] * (priority + 1))
            minimum = get("Minimum")[row]
            if minimum:
                score = score + get("CoverageBonus")
            key = (score, potential)
            hit = caches.get(minimum) == key
            caches[minimum] = key
        visits += len(edges) - len(real)
        if not hit:
            visits += 1 if singleton else len(real)
    return 2 + workers + 2 * rows + visits
