# M096: uniform builtin rendering and variable evaluation stacks

## Goal

Give every canonical LCL builtin one concise dependency-tree representation and
make evaluation failures identify the complete variable-owner stack from the
directly requested definition to the definition whose expression failed.

## Screenshot diagnosis

The second reported command supplies an invalid or incomplete `LCL[...]` marker
for `quicksort`. CLI override compatibility deliberately stores malformed
markers as external literal strings. `RESULT` then attempts to call that string,
so evaluation correctly reaches Python's ``TypeError: 'str' object is not
callable``. The enhanced diagnostic identifies the variable expression in which
that call failed; `parse_lcl` continues to expose the malformed override as an
`ExternalProvided` string.

## Module and test layout

- Native inspection payload formatting remains in
  `pylcl/runtime/frame/inspection.py` with exhaustive canonical-value behavior in
  `tests/runtime/frame/test_inspection.py`.
- Task-local definition ownership remains in
  `pylcl/lang/evaluator/definition_context.py`; structured diagnostic state lives
  in `pylcl/errors.py`, and evaluator propagation is tested across language,
  Frame, and CLI subsystem boundaries.
- The screenshot-shaped command regression belongs in
  `tests/cli/test_module_entrance.py` and uses only static command tokens.

## Contract

- Every selected callable in canonical `LCL_BUILTINS` or the callable `lhs`
  binding in `LCL_ROOT` renders exactly
  `(NativeProvided) Builtin Function: <binding-name>`.
- Every selected reviewed standard namespace in canonical `LCL_ROOT` renders
  exactly `(NativeProvided) Builtin Namespace: <namespace-name>`.
- The display is based on canonical Frame provenance, not a lookalike Frame ID
  or the callable's Python implementation type. External callables and strings
  retain the ordinary `<type>: <repr>` payload.
- Definition ownership is a task-local ordered stack. Nested lazy definitions
  and calls through LCL closures append their lexical definition owner; adjacent
  repeats of the same owner are collapsed. `lhs()` continues to return the
  innermost owner, and concurrent tasks remain isolated.
- `LclError.variable_stack` is an immutable tuple of non-empty variable names.
  An error created outside Frame definition evaluation has an empty stack.
  Evaluation attaches the first non-empty active stack and never replaces a
  deeper stack while the same failure propagates or is served from cache.
- String rendering remains one physical line. A non-empty stack is appended as
  `[variable evaluation stack: RESULT -> intermediate -> failing]` after the
  existing diagnostic; codes, source coordinates, messages, causes, and error
  identities remain unchanged.
- A malformed `LCL[...]` override remains an external literal string under the
  M094 compatibility contract. Calling it from `RESULT` fails with the original
  structured TypeError diagnostic plus `[variable evaluation stack: RESULT]`.
  A valid nested LCL function failure includes its lexical function owner, for
  example `RESULT -> quicksort`.

## TDD matrix

- Sunny: inspect every canonical builtin function, `lhs`, and every standard
  namespace and assert the exact two uniform payload grammars.
- Rainy: prove user/external callables keep ordinary reprs; direct errors outside
  definitions have no stack; malformed CLI markers remain external strings and
  fail without being silently parsed.
- Composite-complex: evaluate `RESULT -> middle -> failing`, a valid LCL closure
  owned by `quicksort`, and the screenshot-shaped malformed override. Assert
  ordered stacks, source-aware original failures, cached identity, `lhs()`
  behavior, and concurrent task isolation.

## Completion evidence

Record focused RED/GREEN commands, exact CLI lines for native values and both
failure shapes, the full quality result, and the verification date in
`progress.md` before marking this milestone DONE.
