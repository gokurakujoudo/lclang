# pylcl

[中文说明](README_cn.md)

`pylcl` is a pure-Python, async-first configuration expression language for
Python 3.14+. The 0.3.0 language, runtime, `.lclcfg`, and typed CLI release candidate is
verified; publication is a separate maintainer action. See
[CHANGELOG.md](CHANGELOG.md).

## Project status

- Target: 0.4.0 development release
- Latest completed milestone: M602 — scoped workflow steps
- Next planned milestone: M100 — trusted-input security boundary audit
- Implemented: foundation, enforced English rST API docs, source-aware lexer,
  immutable AST, complete expression/comprehension parsing, all planned V1
  expression forms, deterministic AST-to-source rendering, semantic f-string
  parsing, stable root parse/print APIs, async expression evaluation with
  recursively awaited sync/async iterable items, lexical
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
  through a focused root API for the complete runtime workflow, plus preferred
  source-string `define_module`/`define_frame` shortcuts and the canonical
  `LCL_ROOT -> LCL_BUILTINS -> LCL_RUNTIME -> LCL_IMPORTS -> user` hierarchy,
  preferred `Frame.derive` child construction, non-evaluating `has` and
  `get_definition` lookup inspection, side-effect-free `inspect_variable`
  dependency trees with first-seen direct-name deduplication and source-oriented
  one-line representations with typed value/error payloads, including canonical
  `<node-type>: <LCL expression>` payloads for AST values and canonical source
  reprs for evaluated LCL function closures, plus controlled
  right-biased `Frame.mixin`
  host-value updates, definition-scoped `lhs()`, strict `YYYYMMDD` date builtins,
  the native variadic fixed-point builtin `recursive`,
  and non-evaluating Frame-qualified dependency graphs with value terminals and
  lookup paths, lexical closure ownership for `lhs()`, source-string
  `evaluate_sync`, deterministic direct/FrameFactory IDs, and a dependency
  analytics tutorial backed by audited nested dependency and Frame packages,
  plus immutable CLI values, exact async command decorators, nested snake_case
  groups, full-argv parsing, structured help, lazy preset/default/config/override
  Frame layering, handler-owned dryrun, isolated logging, result/cleanup mapping,
  concise `CliResult.success`/`fail` constructors, valueless override keys as
  boolean `True`, and built-in `parse_lcl` with optional evaluated inspection,
  lazy `eval_lcl`, and deterministic nested `builtins` module commands, with canonical pylcl
  builtins and standard namespaces identified as `NativeProvided` and rendered
  uniformly as `Builtin Function` or `Builtin Namespace`, plus structured
  failures carrying direct-to-failing variable evaluation stacks, plus ordered
  workflow execution-status trees, shared sub-task manager cursors, deterministic
  parent aggregation, subtree locking, exception-transparent `with` finalization,
  and scoped steps with atomic description/status updates and clean auto-success
- Test status: 842 tests pass at 100.00% branch coverage; strict mypy, Ruff,
  exhaustive source/docstring policy, executable documentation, and artifact
  gates pass

The authoritative milestone ledger is in [progress.md](progress.md). Planned
features are deliberately not presented as implemented features.

## Quickstart

Run from a checkout with its development environment installed. The example is
extracted and executed by the test suite.

```python
import asyncio

import pylcl


async def main() -> None:
    module = pylcl.define_module(
        "quickstart",
        {"result": 'json.encode({"message": "hello pylcl"})'},
    )
    frame = pylcl.define_frame(module)
    try:
        print(await frame.get("result"))
        snapshot = frame.dependency_snapshot("result")
        print(",".join(str(edge.target) for edge in snapshot.dynamic_edges))
    finally:
        await frame.close()


asyncio.run(main())
```

Inspect an override-defined result without evaluating it, or evaluate it through
the same lazy Frame pipeline:

```console
python -m pylcl.cli builtins
python -m pylcl.cli parse_lcl -o a 100 -o b 200 -o RESULT "LCL[a+b]"
python -m pylcl.cli eval_lcl -o a 100 -o b 200 -o RESULT "LCL[a+b]"
```

The first command lists canonical builtins and nested namespace methods. The
second prints the static `RESULT -> a, b` inspection tree. The third prints
`100200` because ordinary CLI override values are literal strings.

Continue with the [tutorial index](docs/tutorials/README.md), then choose the
[runtime guide](docs/tutorials/runtime.md),
[LCL examples gallery](docs/tutorials/lcl_examples.md), or
[configuration-file guide](docs/tutorials/config_file.md). Use the
[dependency analytics tutorial](docs/tutorials/dependency-analytics.md) for
static graphs, Frame paths, runtime traces, and reconciliation. The
[CLI tutorial](docs/tutorials/cli.md) shows how to build a configuration-driven
Python script. The [workflow-status tutorial](docs/tutorials/workflow-status.md)
explains task/step trees, aggregation, descriptions, locking, and scoped error
capture for both tasks and steps. The
[runtime API guide](docs/reference/runtime-api.md) remains the detailed
reference.

## JihuLab CI/CD

The repository pipeline is defined in `.gitlab-ci.yml` with one shared verify
job for setup, build, test, and package inspection, followed by publication.
The verify job exports Cobertura coverage for JihuLab merge
request annotations and a percentage for pipeline coverage reporting. Tag-only
manual jobs publish the verified wheel and sdist to a local Artifactory and to
PyPI. Configure `ARTIFACTORY_REPOSITORY_URL`,
`ARTIFACTORY_USERNAME`, `ARTIFACTORY_PASSWORD`, `PYPI_USERNAME`, and
`PYPI_PASSWORD` as masked/protected JihuLab CI/CD variables before publishing.

## JihuLab CI/CD

The repository pipeline is defined in `.gitlab-ci.yml` with one shared verify
job for setup, build, test, and package inspection, followed by publication.
The verify job exports Cobertura coverage for JihuLab merge
request annotations and a percentage for pipeline coverage reporting. Tag-only
manual jobs publish the verified wheel and sdist to a local Artifactory and to
PyPI. Configure `ARTIFACTORY_REPOSITORY_URL`,
`ARTIFACTORY_USERNAME`, `ARTIFACTORY_PASSWORD`, `PYPI_USERNAME`, and
`PYPI_PASSWORD` as masked/protected JihuLab CI/CD variables before publishing.

## Intended capability

The 0.4 target comprises:

- a versioned Python-like expression grammar with a custom AST;
- an async-first interpreter and cached hierarchical runtime frames;
- dependency analysis with eager, conditional, deferred, and dynamic edges;
- UTF-8 `.lclcfg` files with versioned `using` expansion and source-aware diagnostics;
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
- English tutorial index: [docs/tutorials/README.md](docs/tutorials/README.md)
- Runtime tutorial: [docs/tutorials/runtime.md](docs/tutorials/runtime.md)
- LCL examples gallery: [docs/tutorials/lcl_examples.md](docs/tutorials/lcl_examples.md)
- Configuration-file tutorial: [docs/tutorials/config_file.md](docs/tutorials/config_file.md)
- Dependency analytics tutorial: [docs/tutorials/dependency-analytics.md](docs/tutorials/dependency-analytics.md)
- Python-script CLI tutorial: [docs/tutorials/cli.md](docs/tutorials/cli.md)
- Workflow-status tutorial: [docs/tutorials/workflow-status.md](docs/tutorials/workflow-status.md)
- Chinese CLI tutorial: [doc_cn/cli_cn.md](doc_cn/cli_cn.md)
- Chinese tutorials: `doc_cn/`

## License

MIT. Version 0.3.0 requires Python 3.14+ and has no runtime dependencies.
