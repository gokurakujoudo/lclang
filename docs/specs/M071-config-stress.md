# M071: configuration stress and determinism

## Goal

Verify that configuration parsing and loading remain deterministic and bounded
for realistically large files, graphs, diagnostics, and concurrent callers.

## Module and test layout

- No feature module is planned; justified performance fixes stay in their owning
  configuration modules.
- Stress tests live in `tests/config/test_stress.py`; generators and clocks live
  in `tests/config/stress_support.py`.
- Any production change keeps files below 200 lines and preserves the full
  English rST docstring contract for every callable and value class.

## Contract

- A generated document with 10,000 simple definitions parses without recursion
  proportional to definition count and retains exact first/last spans.
- A 200-node acyclic include graph with shared subgraphs loads deterministically;
  resolver calls equal unique identities while merge placement follows includes.
- At least 100 concurrent callers for one root share source loads, receive equal
  immutable results, and may cancel half their waiters without owner loss.
- A configured `ConfigLoadLimits` caps source count, include depth, total Unicode
  characters, and declarations. Exceeding a limit raises a structured limit
  error before requesting or parsing more work.
- Tests assert algorithmic counts and stable outputs, not fragile wall-clock
  deadlines. An optional benchmark records time/memory without gating releases.

## TDD matrix

- Sunny: exercise the declared large document, graph, and concurrent loads twice
  with identical hashes and call counts.
- Rainy: exceed each limit by one, cancel waiters, inject a late source failure,
  and prove no poisoned cache or unobserved task remains.
- Composite-complex: combine a wide/deep diamond graph, Unicode multiline values,
  shadowing, concurrency, cancellation, and deterministic diagnostics.

## Completion evidence

Record generated sizes, exact focused commands/results, leak/task assertions,
full quality coverage, and date in `progress.md`.
