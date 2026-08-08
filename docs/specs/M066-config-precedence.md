# M066: configuration merge and precedence

## Goal

Turn a resolved include graph into one deterministic definition set with explicit
shadowing rules and auditable provenance.

## Module and test layout

- Expansion policy and immutable results live in `pylcl/config/result.py`.
- Tests live in `tests/config/test_merge.py` and consume M065 resolver fixtures.
- All private/public production callables and value classes use full English rST
  docstrings; modules stay below 200 lines.

## Contract

- Declarations apply from left to right. A using declaration contributes its fully expanded
  definitions at its declaration position; a later using declaration or local definition
  therefore has higher precedence than an earlier contribution.
- Duplicate definitions are valid inside and across physical documents.
- `MergedConfig` exposes the winning definition order by first appearance, a
  name lookup, and an immutable chronological history for every shadowed name.
  Overriding a name replaces its value without moving its display position.
- Repeated use of the same canonical identity contributes at every using
  position; source retrieval/parsing may be cached but merge application is not
  silently deduplicated.
- Expansion results never mutate source documents and do not evaluate ASTs.
  Runtime Modules are created only from final winners, so definition order does
  not constrain forward or overridden dependencies.

## TDD matrix

- Sunny: prove local-over-include and later-include-over-earlier precedence with
  stable iteration order.
- Rainy: reject inconsistent resolved graphs while accepting duplicate locals
  through the documented chronological later-wins rule.
- Composite-complex: merge a diamond graph where four layers shadow two names,
  verify complete provenance, then build one unevaluated Module from a root and
  used file whose definitions depend on one another in both directions. Prove
  the dependency graph contains only expression edges and one Frame evaluates
  every winner at the same runtime level.

## Completion evidence

The milestone becomes DONE only after ledgered RED, focused GREEN, branch
coverage, full quality output, and verification date.
