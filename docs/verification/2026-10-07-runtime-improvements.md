# Runtime improvements: 0.3.2 candidate

## API selection

The installed 0.7.209.0 reflection map exposes `ConstructionSite`, `House` and
`Bathhouse` components. Unreal's `Actor.GetComponentByClass` distinguishes them,
including subclasses, without a prefab-name list. There is no reflected universal
`GridActor.IsWorkplace` classifier in that inspected version.

`House` exposes beds, resident capacity and housing tier; tier zero is valid.
`Bathhouse` exposes bathing/queueing capacity rather than a `WorkerAssignment`.
`ConstructionSite` identifies construction state through its component.

The warning filter excludes contextual-only capacity. A readable nonempty
workforce takes precedence, so a mixed actor cannot hide a genuine unsupported
workplace. Worker admission, preservation and the native ResourceBuilding
compatibility boundary remain unchanged.

Sources: the matching local `Content/DynamicClasses/Whiskerwood-0.7.209.0.jmap.gz`
and compiled component-query tests. The [modkit documentation](https://github.com/Whiskerwood-Modding/Whiskerwood-Project#faq)
explains that reflected headers are signatures, not shipping game implementations.
Editor tests therefore do not establish every shipping-game behavior.

## Slot stability

The chosen team is unchanged. Within ordinary buildings, selected incumbents are
restored to their original slots only when education requirements, required-crew
status and bonus status match. Schools and protected crews are excluded.

Protection discovery checks one slot per advance, once per building. Swaps store
the displaced index before either array write; a pure DSL binding would otherwise
be reevaluated after mutation. Full plan validation still follows normalization.

## Search cost

The solver caches the unchanged row potential during a column scan and avoids
computing a dummy cost for real columns. Arithmetic order, comparisons, matching
objective, work accounting and the controller's 2 ms / 64-advance limits stay the
same. Necessary school/world-change replanning remains unchanged.

Four compiled planner fixtures (90 slots, 79 workers, 45 buildings, reserve 3,
two score distributions and both policy modes) produced identical assignments,
objective values and primitive-work counts before and after the change.

Timings were mixed with the game running concurrently. A warmed, alternating
same-process solver comparison produced optimized/baseline ratios of
1.386, 0.967, 0.979 and 0.981, 0.792, 0.837 across six pairs. All pairs had identical
assignments and work counts. These small synthetic samples do not establish a
reliable end-to-end game speedup. No such percentage or latency guarantee is made.

## Verification boundary

The original suite passed before changes. Both new behavioral regressions failed
against the original assets. The updated snapshot and action-plan tests pass,
including equivalent slots, different roles, protected crews, schools and a
24-worker incremental-discovery case. Solver and planner oracle suites pass.
Focused review findings were addressed and the re-review has no open findings.

Both candidates passed the full editor suite, cook and package integrity checks.
Each contains 46 runtime assets / 92 cooked entries. A hash comparison of cooked
entries confirms that only the instrumented controller differs between flavors.
The public source assets match the restored public authoring assets. Existing
installed mod files remain unchanged.

Final packaged checks are recorded in the local delivery manifest. In-game
acceptance and deployment require separate approval. The private instrumented
controller and real gameplay logs are not part of the public source or public
package. No reliable end-to-end speedup is claimed.
