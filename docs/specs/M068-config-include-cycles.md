# M068: using cycles, caching, and concurrency

## Goal

Make recursive async using expansion safe under cycles, concurrent callers,
failures, and cancellation.

## Module and test layout

- Load coordination lives in `pylcl/config/loader.py`; cycle-path state may be
  isolated in `pylcl/config/load_state.py`.
- Tests live in `tests/config/test_loader.py` with controllable async resolvers.
- Every production function, method, and value class has a complete English rST
  docstring. Each source module stays below 200 lines.

## Contract

- A task-local ordered identity stack detects direct and indirect cycles before
  awaiting an already-owned load. `LclConfigCycleError` reports the closed cycle
  and every corresponding using span in traversal order.
- Concurrent requests for the same identity share one resolver/parse owner task.
  Waiting tasks use cancellation shielding, so cancelling one waiter does not
  cancel the owner or peers.
- Successfully parsed source documents are cached as immutable snapshots. Merge
  placement still occurs at every using declaration according to M066.
- Failed or owner-cancelled loads are not cached. All waiters observe the same
  exception instance for one attempt, and a later request may retry.
- Cache and inflight state belong to one loader/event loop. Cross-loop use raises
  a lifecycle error rather than corrupting task ownership.

## TDD matrix

- Sunny: single-flight two concurrent diamond loads and reuse successful parsed
  snapshots on a later load.
- Rainy: report self/indirect cycles, isolate waiter cancellation, retry failures,
  and reject cross-loop reuse.
- Composite-complex: interleave a slow shared include, cancelled waiter, failing
  sibling, retry, and cycle while asserting call counts and deterministic paths.

## Completion evidence

Ledger the failing concurrency tests, focused GREEN suite, full quality/coverage
result, and verification date before DONE.
