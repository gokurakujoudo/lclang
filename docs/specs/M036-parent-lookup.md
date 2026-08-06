# M036: parent lookup in the defining Frame

## Goal

Add hierarchical Frame lookup while preserving the lexical ownership of every
definition and its cache.

## Module and test layout

- `pylcl/runtime/frames.py` adds an optional parent and hierarchical fallback.
- `tests/runtime/test_frames.py` mirrors shadowing, parent ownership, cache
  identity, and missing-name source propagation.

## Contract

- `Frame(..., parent=parent)` retains an optional parent Frame in the same event
  loop. M036 does not yet add concurrent task coordination.
- Lookup order is local module definition, local host binding, then parent.
- A parent-owned definition is delegated to `parent.get`/resolver lookup and is
  evaluated and cached by that parent. Child bindings never affect its internal
  references.
- A child-owned definition may resolve unshadowed parent names through the
  child Frame resolver; local definitions and host bindings shadow ancestors.
- Parent results and failures are not copied into child cache state. Identity
  and exception ownership remain with the defining Frame.
- A name missing throughout the chain raises one `LclNameError` with the
  original requesting span.
- Public rST documentation and the 200-line implementation limit remain
  mandatory.

## TDD evidence

RED requires parent-construction and hierarchical lookup tests to fail against
the M035 constructor. GREEN requires all ownership/shadowing cases. DONE
requires the complete quality gate and synchronized documentation.
