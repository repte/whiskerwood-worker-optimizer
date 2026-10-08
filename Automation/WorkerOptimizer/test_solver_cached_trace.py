"""Offline opportunity counts for faithful uniform1000 reserve-pass matrices."""

import hashlib
import json
import struct


def solve(matrix, enable_cache, enable_second_root=False, row_order=None, scan_probe=None):
    rows, width = len(matrix), len(matrix[0])
    row_order = list(range(rows)) if row_order is None else list(row_order)
    assert sorted(row_order) == list(range(rows)), "Row order must preserve every original row ID"
    allocated = rows + width + 1
    u, v, p = [0.0] * (rows + 1), [0.0] * allocated, [0] * allocated
    way, minv = [0] * allocated, [0.0] * allocated
    minima, second, winner = [], [], []
    for row in matrix:
        costs = [0.0 - score for score in row]
        ordered = sorted(costs)
        minima.append(ordered[0])
        second.append(ordered[1] if width > 1 else 1e20)
        winner.append(costs.index(ordered[0]) + 1)
    first_free, nonpositive = 1, True
    counts = dict(relax_scans=0, relax_columns=0, potential_columns=0, candidate_cells=0,
                  cache_bypasses=0, bypassed_columns=0, first_shortcuts=0, nonzero_phases=0,
                  costs_skipped_by_bound=0, free_cache_winners=0, second_root_shortcuts=0)
    cur = 0.0
    for row_id in row_order:
        active = row_id + 1
        p[0], j0 = active, 0
        used = [False] * allocated
        used_columns = []
        cached = None
        while p[first_free] != 0:
            first_free += 1
        while True:
            used[j0] = True
            used_columns.append(j0)
            i0 = p[j0]
            row = matrix[i0 - 1]
            row_potential = u[i0]
            delta, j1, best_free = 1e30, 0, False
            lower = None
            if j0 != 0 and nonpositive:
                cost = second[i0 - 1] if used[winner[i0 - 1]] else minima[i0 - 1]
                lower = cost - row_potential
            bypass = (enable_cache and cached is not None and cached[0] == j0
                      and lower is not None and lower >= cached[1])
            if bypass:
                _, _, delta, j1, best_free, cur = cached
                counts["cache_bypasses"] += 1
                counts["bypassed_columns"] += width
                counts["free_cache_winners"] += best_free
            elif j0 == 0 and nonpositive and row_potential == 0.0:
                candidate = winner[i0 - 1]
                if p[candidate] != 0:
                    candidate = first_free
                cur = 0.0 - row[candidate - 1]
                if cur == minima[i0 - 1] and v[candidate] == 0.0:
                    delta = (cur - row_potential) - v[candidate]
                    cur, j1, best_free, way[candidate] = delta, candidate, True, 0
                    counts["first_shortcuts"] += 1
            if j1 == 0 and enable_second_root and j0 == 0 and nonpositive and row_potential == 0.0:
                candidate_cost = (0.0 - row[first_free - 1])
                candidate_reduced = (candidate_cost - row_potential) - v[first_free]
                minimum_column = winner[i0 - 1]
                minimum_reduced = ((0.0 - row[minimum_column - 1]) - row_potential) - v[minimum_column]
                if (v[first_free] == 0.0 and candidate_reduced <= second[i0 - 1] - row_potential
                        and minimum_reduced >= candidate_reduced):
                    delta, cur, j1, best_free = candidate_reduced, candidate_reduced, first_free, True
                    way[first_free] = 0
                    counts["second_root_shortcuts"] += 1
            if j1 == 0:
                counts["relax_scans"] += 1
                counts["relax_columns"] += width
                check_scan = (scan_probe(row, row_potential, v, p, used, used_columns, minv,
                                        lower, j0, first_free, way) if scan_probe is not None else None)
                for j in range(1, width + 1):
                    if used[j]:
                        continue
                    if lower is not None and minv[j] <= lower:
                        cur = minv[j]
                        counts["costs_skipped_by_bound"] += 1
                    else:
                        cur = ((0.0 - row[j - 1]) - row_potential) - v[j]
                        if j0 == 0 or cur < minv[j]:
                            minv[j], way[j] = cur, j0
                        else:
                            cur = minv[j]
                    if cur < delta or (cur == delta and not best_free and p[j] == 0):
                        delta, j1, best_free = cur, j, p[j] == 0
                if check_scan is not None:
                    check_scan(delta, j1, best_free, cur, minv, way)
            cached = None
            terminal = p[j1] == 0
            if delta != 0.0:
                if delta < 0.0 and len(used_columns) > 1:
                    nonpositive = False
                if terminal:
                    for j in used_columns:
                        u[p[j]] = u[p[j]] + delta
                        v[j] = v[j] - delta
                else:
                    counts["nonzero_phases"] += 1
                    maximum, next_delta, next_j, next_free, last = -1e30, 1e30, 0, False, 0.0
                    for j in range(width + 1):
                        counts["potential_columns"] += 1
                        if used[j]:
                            u[p[j]] = u[p[j]] + delta
                            v[j] = v[j] - delta
                        else:
                            minv[j] = minv[j] - delta
                            if enable_cache and j != j1:
                                counts["candidate_cells"] += 1
                                value = minv[j]
                                last = value
                                if value > maximum:
                                    maximum = value
                                if value < next_delta or (value == next_delta and not next_free and p[j] == 0):
                                    next_delta, next_j, next_free = value, j, p[j] == 0
                    if enable_cache and next_j:
                        cached = (j1, maximum, next_delta, next_j, next_free, last)
            j0 = j1
            if terminal:
                while j0 != 0:
                    j1 = way[j0]
                    p[j0], j0 = p[j1], j1
                break
    assignment = [-1] * rows
    for j in range(1, width + 1):
        if p[j]:
            assignment[p[j] - 1] = j - 1
    packed = lambda data: b"".join(struct.pack("!d", value) for value in data)
    return dict(assignment=assignment, p=p, u=u, v=v, minv=minv, way=way,
                dual_bits=(packed(u), packed(v)), nonpositive_v=nonpositive,
                float_bits=(packed(u), packed(v), packed(minv), struct.pack("!d", cur)), counts=counts)


def benchmark_matrices(size):
    rows, columns, reserve = size + 3, size + size // 2, 3
    quality = [0.0] * size
    for row in range(size):
        quality[(row + 17) % size] = float(10000 + row if row % 2 == 0 else row // 2 + 1)
    maximum = max(100.0, max(quality))
    capacity = rows + 1
    fill = (((maximum * 5.0) + 1.0) * capacity) + 1.0
    coverage = (((fill + (maximum * 5.0)) + 1.0) * capacity) + 1.0
    column_bonus = ((((coverage + fill) + (maximum * 5.0)) + 1.0) * capacity) + 1.0
    matrix = []
    for row in range(rows):
        scores = [-1e20] * columns
        for worker in range(size):
            score = fill + (100.0 if worker == (row + 17) % size else 1.0) if row < size else 0.0
            if row >= size or row % 2 == 0:
                score = score + coverage
            scores[worker] = score
        if row < size and row % 2:
            scores[size + row // 2] = 0.0
        matrix.append(scores)
    return matrix, quality, coverage, column_bonus


def compare(matrix):
    reference, candidate = solve(matrix, False), solve(matrix, True)
    for name in ("assignment", "p", "way", "float_bits"):
        assert reference[name] == candidate[name], name
    root_candidate = solve(matrix, False, True)
    for name in ("assignment", "p", "dual_bits"):
        assert reference[name] == root_candidate[name], ("second root", name)
    reference["counts"]["second_root_candidate_hits"] = root_candidate["counts"]["second_root_shortcuts"]
    return reference, candidate["counts"]


def run(size=1000):
    matrix, quality, coverage, column_bonus = benchmark_matrices(size)
    first, candidate = compare(matrix)
    report = {"workers": size, "reserve": 3,
              "first": {"reference": first["counts"], "candidate": candidate}}
    required = [value < -0.00001 for value in first["v"][1:len(matrix[0]) + 1]]
    retained = 0
    for row, scores in enumerate(matrix):
        for column, score in enumerate(scores):
            reduced = ((0.0 - score) - first["u"][row + 1]) - first["v"][column + 1]
            if score >= 0.0 and -0.00001 <= reduced <= 0.00001:
                retained += 1
                score = quality[column] if row >= size and column < size else 0.0
                if column < size and (row >= size or row % 2 == 0):
                    score = score + coverage
                if required[column]:
                    score = score + column_bonus
                scores[column] = score
            else:
                scores[column] = -1e20
    second, candidate = compare(matrix)
    productive = [worker if worker < size else -1 for worker in second["assignment"][:size]]
    idle = set(range(size)) - {worker for worker in productive if worker >= 0}
    expected_builder = sum(sorted(quality[(row + 17) % size] for row in range(1, size, 2))[-3:])
    assert len(idle) == 3 and sum(quality[worker] for worker in idle) == expected_builder
    assert all(productive[row] == (row + 17) % size for row in range(size) if productive[row] >= 0)
    report.update(second={"reference": second["counts"], "candidate": candidate},
                  retained_edges=retained, builder=expected_builder,
                  assignment_sha256=hashlib.sha256(json.dumps(productive).encode("ascii")).hexdigest())
    print("WO_SOLVER_CACHED_TRACE_PASS " + json.dumps(report, sort_keys=True))
    return report


if __name__ == "__main__":
    run()
