# M066: configuration merge and precedence

## Goal

Turn a resolved include graph into one deterministic definition set with explicit
shadowing rules and auditable provenance.

## Module and test layout

- Merge policy and immutable results live in `pylcl/config/merge.py`.
- Tests live in `tests/config/test_merge.py` and consume M065 resolver fixtures.
- All private/public production callables and value classes use full English rST
  docstrings; modules stay below 200 lines.

## Contract

- Declarations apply from left to right. An include contributes its fully merged
  definitions at its declaration position; a later include or local definition
  therefore has higher precedence than an earlier contribution.
- Duplicate definitions inside one physical document remain the M063 syntax
  error. Shadowing across different documents is valid.
- `MergedConfig` exposes the winning definition order by first appearance, a
  name lookup, and an immutable chronological history for every shadowed name.
  Overriding a name replaces its value without moving its display position.
- Repeated inclusion of the same canonical identity contributes at every include
  position; source retrieval/parsing may be cached but merge application is not
  silently deduplicated.
- Merge results never mutate source documents and do not evaluate ASTs.

## TDD matrix

- Sunny: prove local-over-include and later-include-over-earlier precedence with
  stable iteration order.
- Rainy: reject inconsistent resolved graphs and duplicate locals rather than
  choosing an accidental winner.
- Composite-complex: merge a diamond graph where four layers shadow two names,
  then verify winners, first-appearance order, and complete provenance histories.

## Completion evidence

The milestone becomes DONE only after ledgered RED, focused GREEN, branch
coverage, full quality output, and verification date.
