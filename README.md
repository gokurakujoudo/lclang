# pylcl

[中文说明](README_cn.md)

`pylcl` is a pure-Python, async-first configuration expression language for
Python 3.14+. The 0.1.0 implementation and clean-install artifact gate are
verified; publication remains pending the repository-wide source-policy gate.
See [CHANGELOG.md](CHANGELOG.md).

## Project status

- Target: 0.4.0 development release
- Latest completed milestone: M050 — 0.1 bilingual user documentation
- Current milestone: M051 — 0.1 release-candidate gate
- Implemented: foundation, enforced English rST API docs, source-aware lexer,
  immutable AST, complete expression/comprehension parsing, all planned V1
  expression forms, deterministic AST-to-source rendering, semantic f-string
  parsing, stable root parse/print APIs, async expression evaluation, lexical
  closures, structured failures, assertions, try recovery, finalization, and
  synchronous/asynchronous context management, semantic f-string evaluation,
  immutable runtime modules, and hierarchical single-flight Frame caching with
  structured cycle detection, cancellation isolation, and atomic targeted
  recalculation without dependant invalidation, plus task-local depth, work, and
  materialized-collection limits, deterministic Frame close/resource cleanup,
  scope-aware eager/conditional/deferred dependency analysis, immutable module
  dependency graphs, filtered queries, deterministic topological ordering,
  bounded runtime lookup tracing, static/dynamic edge reconciliation, and
  owner-aware immutable Frame dependency snapshots with atomic refresh semantics,
  plus shallow immutable host presets, reusable independent Frame factories,
  manifest-driven read-only attribute namespaces, and reviewed async iterable,
  text, immutable data, and strict JSON helpers in a standard preset, exposed
  through a focused root API for the complete runtime workflow
- Test status: 578 tests pass with 99.12% branch coverage; the unified quality gate passes

The authoritative milestone ledger is in [progress.md](progress.md). Planned
features are deliberately not presented as implemented features.

## Quickstart

Run from a checkout with its development environment installed. The example is
extracted and executed by the test suite.

```python
import asyncio

import pylcl


async def main() -> None:
    module = pylcl.Module(
        pylcl.ModuleName("quickstart"),
        {
            "result": pylcl.parse_expression(
                'json.encode({"message": "hello pylcl"})'
            )
        },
    )
    frame = pylcl.FrameFactory(module, pylcl.STANDARD_PRESET).create(
        pylcl.FrameId("quickstart:1"),
    )
    try:
        print(await frame.get("result"))
        snapshot = frame.dependency_snapshot("result")
        print(",".join(str(edge.target) for edge in snapshot.dynamic_edges))
    finally:
        await frame.close()


asyncio.run(main())
```

Continue with the [runtime quickstart](docs/tutorials/runtime-quickstart.md) and
[runtime API guide](docs/reference/runtime-api.md). For task-oriented coverage
of every public Python feature, use the
[Python user cheatsheet](docs/user-cheatsheet.md).

## Intended capability

The 0.4 target comprises:

- a versioned Python-like expression grammar with a custom AST;
- an async-first interpreter and cached hierarchical runtime frames;
- dependency analysis with eager, conditional, deferred, and dynamic edges;
- UTF-8 `.lclcfg` files with versioned includes and source-aware diagnostics;
- a typed framework for building configuration-driven command-line tools;
- strict typing, branch coverage, parser differential tests, stress tests,
  memory-leak checks, and portable package verification.

## Engineering policy

Development is documentation-first and test-driven. Every implementation
milestone starts with an executable behavioural contract, demonstrates a
failing test, implements the behaviour, passes the complete quality gate, and
then updates both README files and the progress ledger. Production and unit-test
submodules mirror one another as defined in
[the module-layout specification](docs/architecture/module-layout.md).

The language is intended for trusted application configuration. It is not a
security sandbox for hostile expressions.

## Documentation

- Durable development rules: [AGENTS.md](AGENTS.md)
- Progress and verification evidence: [progress.md](progress.md)
- English specifications: `docs/specs/`
- Complete LCL syntax: [docs/lcl-lang.md](docs/lcl-lang.md)
- Complete Python user cheatsheet: [docs/user-cheatsheet.md](docs/user-cheatsheet.md)
- English tutorials: `docs/tutorials/`
- Chinese tutorials: `doc_cn/`

## License

MIT. The package currently requires Python 3.14+ and has no runtime dependencies.
