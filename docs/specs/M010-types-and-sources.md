# M010: public identifiers and source locations

## Contract

Distinct `NewType` identifiers represent variable, module, frame, and source
names. `LanguageVersion` is a string enum whose first and default member is
`V1`. Immutable source-position and source-span value objects use one-based
line and column coordinates and half-open end positions.

A span validates positive coordinates and refuses an end before its start. A
source origin stores a display name and optional resolved filesystem path.
These objects contain no parser logic and are safe to share across tasks.

## Public interfaces

- `VarName`, `ModuleName`, `FrameId`, `SourceName`
- `LanguageVersion.V1` and `LCL_V1`
- `SourcePosition(line, column, offset)`
- `SourceSpan(origin, start, end)`
- `SourceOrigin(name, path=None)`

## Failure behaviour

Invalid line, column, offset, or reversed spans raise `ValueError` at
construction time.

## Test cases

- Identifier NewTypes preserve string values at runtime.
- Positions and spans compare structurally and are immutable.
- Every invalid coordinate and reversed range is rejected.

## Acceptance

The new behavioural tests pass with complete branch coverage and the full
quality script remains green.
