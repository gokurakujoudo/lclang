# M067: file sources and origin propagation

## Goal

Provide an opt-in filesystem resolver and preserve actionable origins throughout
parsing, inclusion, merging, and later evaluation.

## Module and test layout

- Filesystem retrieval lives in `pylcl/config/files.py`; origin-chain helpers
  live in `pylcl/config/origins.py` if separation is needed.
- Tests live in `tests/config/test_files.py` and `tests/config/test_origins.py`.
- Source files remain under 200 lines and all production callables/value classes,
  including private ones, have full English rST docstrings.

## Contract

- `FileConfigResolver` resolves a `.lclcfg` root path explicitly supplied by the host.
  Relative using targets resolve against the importing file's directory, not
  process CWD; normalized absolute paths form canonical identities.
- Files are decoded strictly as UTF-8, with an optional UTF-8 BOM accepted only
  at the beginning. Decode, permission, directory, and missing-file failures are
  structured include errors with preserved causes.
- Each definition retains its physical file origin and expression span after
  expansion. Magic constants use this same canonical file. The root origin and
  ordered using chain remain available for errors.
- Symlink resolution policy is injected and documented: the default canonical
  identity uses `Path.resolve(strict=False)` while opening the requested resolved
  path. Path case follows the host filesystem and is not manually folded.
- The resolver performs no globbing, environment expansion, network access, or
  evaluation and offers an optional allowed-root containment check.

## TDD matrix

- Sunny: load UTF-8 root/relative includes and retain exact winning and shadowed
  origins.
- Rainy: diagnose invalid UTF-8, missing files, directory targets, traversal
  outside an allowed root, and read failures.
- Composite-complex: load nested relative paths with `..`, Unicode filenames,
  shadowing, and a deep expression error whose excerpt and using chain are exact.
  In a three-file nested using chain, independently bind `__file__` in each
  physical file and prove all three eager constants contain their defining
  file's distinct canonical path.

## Completion evidence

Record platform-neutral RED/GREEN commands, focused coverage, complete quality
gate output, and date in `progress.md`.
