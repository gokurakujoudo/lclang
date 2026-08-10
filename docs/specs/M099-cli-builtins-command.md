# M099: CLI builtin inventory command

## Goal

Add `python -m pylcl.cli builtins` as a deterministic, human-readable inventory
of every value available through the canonical LCL builtin hierarchy.

## Module and test layout

- Stable descriptions and rendering live in `pylcl/cli/builtin_docs.py`.
- The leaf handler and module entrance remain in `pylcl/cli/application.py`.
- Renderer tests live in `tests/cli/test_builtin_docs.py`; entrance, help, and
  subprocess behavior remain in `tests/cli/test_module_entrance.py`.

## Contract

- The module entrance offers `builtins` beside `parse_lcl` and `eval_lcl`.
  It declares no command parameters and returns success without evaluating an
  LCL expression.
- Output contains every ordinary value from `LCL_BUILTINS`, root builtin
  `lhs`, and every namespace from `STANDARD_MANIFESTS` exactly once.
- Top-level entries are sorted by public name and use exactly
  `- <name>: <description>`.
- Each namespace is a top-level entry. Its methods immediately follow it in
  manifest declaration order and use exactly two leading spaces before
  `- <name>: <description>`.
- Descriptions are stable, non-blank, single-line text. Existing manifest entry
  summaries are reused for namespace methods. The renderer rejects inventory
  drift, duplicate names, or malformed descriptions during testing rather than
  silently omitting a builtin.
- Output contains no object addresses, implementation reprs, ANSI sequences,
  trailing whitespace, or blank lines. The normal CLI result writer adds one
  final newline.
- Root and command help list/describe `builtins`; version, logging, cleanup,
  status mapping, and import-inert module behavior remain unchanged.

## TDD matrix

- Sunny: assert representative function, `recursive`, `lhs`, namespace, and
  nested method lines with exact indentation and descriptions.
- Rainy: validate that every description is non-blank and single-line and that
  renderer metadata exactly covers the canonical builtin inventory.
- Composite-complex: run the module entrance and a real subprocess, assert the
  complete deterministic output, root help visibility, success status, empty
  stderr, and no log artifacts.

## Completion evidence

Record focused RED/GREEN commands, representative output, exact line counts,
full quality results, and the verification date in `progress.md` before DONE.
