# M011: structured errors

## Contract

Every expected language/runtime failure derives from `LclError`. Errors expose
a stable string code, plain message, and optional `SourceSpan`. Their rendered
form is `[CODE] message` without a span and
`source:line:column: [CODE] message` with one.

Dedicated public subclasses represent syntax, missing names, evaluation,
circular dependency, closed Frame, configuration, CLI, and usage failures.
Subclasses supply stable default codes while callers may override a code.

## Failure behaviour

The error constructor rejects an empty message or empty code. Original Python
exceptions are preserved through normal exception chaining rather than copied
into an untyped payload.

## Test cases

- Base and subclass errors are catchable through `LclError`.
- Default and custom codes render exactly.
- Source rendering uses the span start and logical source name.
- Empty messages/codes are rejected.

## Acceptance

The error tests and complete project quality script pass with at least 99%
branch coverage.
