# pylcl implementation progress

Status flow: `NOT_STARTED -> SPEC_READY -> RED -> GREEN -> VERIFIED -> DONE`.
`BLOCKED` may be used only with a concrete reason. At most one milestone is
actively implemented. The first non-DONE item is the default next task.

## Current state

- Target release: 0.4.0
- Active milestone: M100
- Latest completed milestone: M602
- Last verified: 2026-08-10

## 0.0 governance and foundation

| ID | Deliverable | Status | Evidence |
|---|---|---|---|
| M000 | Agent handoff, progress ledger, bilingual README protocol | DONE | Files created; repository inspection recorded 2026-08-03 |
| M001 | Product specification and architecture decisions | DONE | Structural acceptance and `git diff --check` passed 2026-08-03; `docs/specs/M001-product-and-architecture.md` |
| M002 | MIT packaging skeleton and 0.x version policy | DONE | RED missing metadata/package; GREEN 2 unittest tests and `git diff --check`, 2026-08-03 |
| M003 | pytest, coverage, strict mypy, Ruff, size/doc checks | DONE | RED missing configs/script; GREEN 7 tests, 100% branch, strict mypy, Ruff, source policy and diff checks, 2026-08-03 |
| M004 | Platform-neutral quality/build/smoke scripts | DONE | RED missing modules; GREEN portable unit tests and complete `scripts.quality` gate, 2026-08-03 |
| M005 | Documentation trees and templates | DONE | Required indexes/template present and complete quality gate passed, 2026-08-03 |
| M006 | Empty-package wheel/sdist and clean-install gate | DONE | Built sdist and `py3-none-any` wheel; metadata/content inspection, no-deps clean-venv install, import 0.0.0, and full quality gate passed 2026-08-03 |
| M007 | English rST production-docstring contract and automated gate | DONE | [`M007`](docs/specs/M007-rst-docstrings.md); RED structural tests; automated parameter/result/raise/note checks; production audit and full quality gate passed 2026-08-03 |

## 0.1 language and runtime

| IDs | Deliverables | Status | Evidence |
|---|---|---|---|
| M010 | Identifier NewTypes, language version, source origins and spans | DONE | [`M010`](docs/specs/M010-types-and-sources.md); tests in `tests/test_types_and_sources.py`; full quality gate passed 2026-08-03 |
| M011 | Structured base, syntax, name, evaluation and lifecycle errors | DONE | [`M011`](docs/specs/M011-errors.md); tests in `tests/test_errors.py`; 20 tests and full quality gate passed 2026-08-03 |
| M012 | Immutable AST base and visitor protocol | DONE | [`M012`](docs/specs/M012-ast-base.md); RED missing `pylcl.ast`; `tests/ast/test_base.py`; 24 tests, 100% branch coverage, strict mypy, Ruff and project checks passed via `python -m scripts.quality` 2026-08-03 |
| M013 | Core lexer tokens, identifiers, whitespace and punctuation | DONE | [`M013`](docs/specs/M013-core-lexer.md); RED missing `pylcl.lang`; mirrored lexer tests; 34 tests, 100% branch coverage and full quality gate passed 2026-08-03 |
| M014 | Numeric, string, bytes, raw and adjacent literals | DONE | [`M014`](docs/specs/M014-literals.md); RED missing literal module; mirrored literal/escape tests; 71 tests, 100% branch coverage and full quality gate passed 2026-08-03 |
| M015 | Complete f-string lexical and AST model | DONE | [`M015`](docs/specs/M015-fstrings.md); RED missing lexical/AST modules; scanner/value modules split under 200 lines; 97 tests, 99.52% branch coverage and full quality gate passed 2026-08-03 |
| M016 | Operator and primary-expression AST node families | DONE | [`M016`](docs/specs/M016-expression-ast.md); RED four absent modules; five responsibility modules with mirrored tests; 108 tests, 99.62% branch coverage and full quality gate passed 2026-08-03 |
| M017 | Pratt parser core, atoms, unary and binary precedence | DONE | [`M017`](docs/specs/M017-pratt-core.md); RED absent parser package; three mirrored modules; 139 tests, 99.33% branch coverage and full quality gate passed 2026-08-03 |
| M018 | Attribute, safe attribute, subscript, slice and call primaries | DONE | [`M018`](docs/specs/M018-parser-primaries.md); RED missing lookahead/postfix parsing; mirrored module; 155 tests, 99.40% branch coverage and full quality gate passed 2026-08-03 |
| M019 | Tuple, list, set and dict displays with unpacking | DONE | [`M019`](docs/specs/M019-parser-displays.md); RED delimiters rejected; isolated display parser and mirror; 169 tests, 99.53% branch coverage and full quality gate passed 2026-08-03 |
| M020 | Comparisons, booleans, conditionals and null coalescing | DONE | [`M020`](docs/specs/M020-logical-parser.md); RED trailing logical tokens; isolated low-precedence module and mirror; 182 tests, 99.56% branch coverage and full quality gate passed 2026-08-03 |
| M021 | Generator/list/set/dict comprehensions and PEP 798 unpacking | DONE | [`M021`](docs/specs/M021-comprehensions.md); RED absent AST/parser modules; two mirrored suites; 200 tests, 99.48% branch coverage and full quality gate passed 2026-08-03 |
| M022 | Function, raise and assert expression forms | DONE | [`M022`](docs/specs/M022-function-error-forms.md); RED absent form modules; mirrored AST/parser suites; 218 tests, 99.42% branch coverage and full quality gate passed 2026-08-03 |
| M023 | Try and with expression forms | DONE | [`M023`](docs/specs/M023-control-forms.md); RED absent control modules; mirrored AST/parser suites; 235 tests, 99.17% branch coverage and full quality gate passed 2026-08-03 |
| M024 | Precedence-aware canonical printer and round trips | DONE | [`M024`](docs/specs/M024-canonical-printer.md); RED absent package; six mirrored suites plus numeric-boundary regression; 285 tests, 99.17% branch coverage and full quality gate passed 2026-08-03 |
| M025 | Parser diagnostics, versioned entry point and public API | DONE | [`M025`](docs/specs/M025-parser-api.md); RED six focused failures; semantic f-string conversion and root API exports; 290 tests, 99.30% branch coverage and full quality gate passed 2026-08-03 |
| M026 | Async evaluator core, resolver protocol, constants, names and sync boundary | DONE | [`M026`](docs/specs/M026-evaluator-core.md); RED absent evaluator package; three mirrored modules; 302 tests, 99.32% branch coverage and full quality gate passed 2026-08-03 |
| M027 | Unary, binary and comparison operations | DONE | [`M027`](docs/specs/M027-operations.md); RED 29 unsupported cases; full operator families and ordering; 331 tests, 99.33% branch coverage and full quality gate passed 2026-08-03 |
| M028 | Boolean short-circuiting, conditionals and null coalescing | DONE | [`M028`](docs/specs/M028-logical-evaluation.md); RED 14 unsupported cases; value-preserving short circuits; 345 tests, 99.35% branch coverage and full quality gate passed 2026-08-03 |
| M029 | Displays, unpacking and sync/async comprehensions | DONE | [`M029`](docs/specs/M029-collections.md); RED absent iteration module; three mirrored evaluator modules; 357 tests, 99.28% branch coverage and full quality gate passed 2026-08-03 |
| M030 | Attributes, safe attributes, subscripts, slices and calls | DONE | [`M030`](docs/specs/M030-primaries-and-calls.md); RED ten unsupported cases; primary/call modules; 367 tests, 99.20% branch coverage and full quality gate passed 2026-08-03 |
| M031 | Functions, defaults, argument binding and lexical closures | DONE | [`M031`](docs/specs/M031-functions.md); RED ten unsupported cases; binding/closure/non-recursion module; 377 tests, 99.13% branch coverage and full quality gate passed 2026-08-03 |
| M032 | Raise, assert, try handlers and failure wrapping | DONE | [`M032`](docs/specs/M032-error-control.md); RED ten unsupported/wrapping cases; structured failure boundary and recovery module; 389 tests, 99.09% branch coverage and full quality gate passed 2026-08-03 |
| M033 | Sync/async context managers and with cleanup | DONE | [`M033`](docs/specs/M033-context-managers.md); RED nine unsupported cases; nested sync/async acquisition and cleanup module; 398 tests, 99.10% branch coverage and full quality gate passed 2026-08-03 |
| M034 | Semantic f-string evaluation, auto-await audit and evaluator public API | DONE | [`M034`](docs/specs/M034-fstrings-and-evaluator-api.md); RED eight unsupported cases; semantic formatter and public boundary audit; 406 tests, 99.12% branch coverage and full quality gate passed 2026-08-03 |
| M035 | Runtime module values and local Frame result/failure cache | DONE | [`M035`](docs/specs/M035-frame-cache.md); RED eight absent-runtime cases; immutable modules and local success/failure cache; 416 tests, 99.14% branch coverage and full quality gate passed 2026-08-03 |
| M036 | Parent lookup in the defining Frame | DONE | [`M036`](docs/specs/M036-parent-lookup.md); RED four absent-parent cases; lexical parent delegation; 420 tests, 99.14% branch coverage and full quality gate passed 2026-08-03 |
| M037 | Per-name task single-flight and cycle detection | DONE | [`M037`](docs/specs/M037-single-flight.md); RED duplicate-owner/recursion cases; per-name Tasks and task-local cycle paths; 424 tests, 99.15% branch coverage and full quality gate passed 2026-08-03 |
| M038 | Waiter/owner cancellation isolation | DONE | [`M038`](docs/specs/M038-cancellation.md); RED peer-cancellation case; shielded waiter boundary with owner retry semantics; 426 tests, 99.15% branch coverage and full quality gate passed 2026-08-03 |
| M039 | Atomic explicit recalculation without dependant invalidation | DONE | [`M039`](docs/specs/M039-recalculation.md); RED seven absent-API groups; atomic success/failure commits, refresh single-flight and cancellation isolation; `venv\\Scripts\\python.exe -m scripts.quality` passed 437 tests at 99.17% branch coverage with strict mypy, Ruff and project checks on 2026-08-04 |
| M040 | Evaluation depth, work and collection limits | DONE | [`M040`](docs/specs/M040-evaluation-limits.md); RED absent limits API; language guard/runtime budget separation with hierarchy and task isolation; `venv\\Scripts\\python.exe -m scripts.quality` passed 451 tests at 99.19% branch coverage with strict mypy, Ruff and project checks on 2026-08-04 |
| M041 | Frame close lifecycle and cleanup | DONE | [`M041`](docs/specs/M041-frame-close.md); RED seven absent lifecycle groups; shielded idempotent close, owner cancellation, reverse deduplicated resource cleanup and hierarchy isolation; `venv\\Scripts\\python.exe -m scripts.quality` passed 459 tests at 99.22% branch coverage with strict mypy, Ruff and project checks on 2026-08-04 |
| M042 | Dependency reference model and scope-aware static AST analysis | DONE | [`M042`](docs/specs/M042-static-dependencies.md); RED absent dependency exports; occurrence-preserving scope/control/laziness analysis; `venv\\Scripts\\python.exe -m scripts.quality` passed 469 tests at 99.25% branch coverage with strict mypy, Ruff and project checks on 2026-08-04 |
| M043 | Module dependency graph construction, queries and ordering | DONE | [`M043`](docs/specs/M043-dependency-graph.md); RED three absent graph/edge/order exports; immutable occurrence-preserving graph, filtered queries and deterministic kind-aware topological ordering; `venv\\Scripts\\python.exe -m scripts.quality` passed 479 tests at 99.03% branch coverage with strict mypy, Ruff and project checks on 2026-08-04 |
| M044 | Runtime dynamic dependency tracing and edge reconciliation | DONE | [`M044`](docs/specs/M044-dynamic-dependencies.md); RED absent public exports; bounded occurrence traces, closure-retained resolver decoration and pure exact reconciliation; `venv\\Scripts\\python.exe -m scripts.quality` passed 487 tests at 99.04% branch coverage with strict mypy, Ruff and project checks on 2026-08-04 |
| M045 | Frame dependency snapshots and recalculation integration | DONE | [`M045`](docs/specs/M045-frame-dependencies.md); RED absent snapshot API; owner-aware immutable snapshots, nested/deferred tracing, cache-aligned success/failure publication and cancellation-safe atomic refresh replacement; `venv\\Scripts\\python.exe -m scripts.quality` passed 495 tests at 99.06% branch coverage with strict mypy, Ruff and project checks on 2026-08-04 |
| M046 | Immutable preset overlays and Frame factories | DONE | [`M046`](docs/specs/M046-presets-and-factories.md); RED absent exports; detached shallow right-biased presets and immutable independent-Frame construction policy; `venv\\Scripts\\python.exe -m scripts.quality` passed 505 tests at 99.08% branch coverage with strict mypy, Ruff and project checks on 2026-08-04 |
| M047 | Standard-library manifest model and namespace assembly | DONE | [`M047`](docs/specs/M047-stdlib-manifests.md); RED absent package; immutable reviewed manifests, collision-safe mapping/attribute namespaces and one-pass no-execution Preset assembly; `venv\\Scripts\\python.exe -m scripts.quality` passed 520 tests at 99.10% branch coverage with strict mypy, Ruff and project checks on 2026-08-04 |
| M048 | Reviewed zero-dependency async standard-library helpers | DONE | [`M048`](docs/specs/M048-stdlib-helpers.md); RED absent concrete exports; reviewed async iterable/text, immutable mapping and strict JSON helpers with stable manifests, end-to-end Frame use and ambient-capability import audit; `venv\\Scripts\\python.exe -m scripts.quality` passed 534 tests at 99.12% branch coverage with strict mypy, Ruff and project checks on 2026-08-04 |
| M049 | Stable 0.1 top-level runtime/stdlib public API integration | DONE | [`M049`](docs/specs/M049-runtime-public-api.md); RED seven absent root exports; canonical seven-name root boundary, advanced namespace isolation and root-only parse/create/evaluate/inspect/close workflow; `venv\\Scripts\\python.exe -m scripts.quality` passed 538 tests at 99.12% branch coverage with strict mypy, Ruff and project checks on 2026-08-04 |
| M050 | 0.1 tutorials, API guide and executable examples | DONE | [`M050`](docs/specs/M050-runtime-documentation.md); original bilingual guide evidence retained; English tutorial refactor RED failed five absent/stale groups, GREEN passed installation/TOC, runtime, complete gallery, config integration, executable-example and link acceptance; full gate passed 633 tests at 99.22% coverage with strict mypy/Ruff on 2026-08-08 |
| M051 | 0.1 version, artifacts, clean-install and release-candidate gate | DONE | [`M051`](docs/specs/M051-runtime-release.md); historical 0.1 artifact evidence is retained below; its inherited repository-policy blocker was fully closed by the M072 quality gate on 2026-08-08 |
| M053 | Canonical Frame hierarchy and definition shortcuts | DONE | [`M053`](docs/specs/M053-frame-hierarchy-shortcuts.md); initial shortcut, lookup, and derivation RED/GREEN evidence retained; mixin RED `venv\Scripts\python.exe -m pytest tests\runtime\test_frame_values.py -q --no-cov` failed 5 cases because `Frame.mixin` was absent, then GREEN passed detached/right-biased updates, definition precedence, descendant fallback, cached-snapshot/recalculation semantics, atomic validation, and closed rejection; `Frame.values` remains a read-only live view over controlled mutable bindings; `venv\Scripts\python.exe -m pytest -q` passed 589 tests at 99.15% branch coverage and strict mypy/Ruff passed; new frame lookup/derivation/value modules have 100% branch coverage and pass isolated source/docstring/line policy; `venv\Scripts\python.exe -m scripts.quality` still stops only at the already-ledgered legacy source-policy backlog after pytest/mypy/Ruff; `git diff --check` passed 2026-08-08; synchronized changelog, preferred-workflow docs, and English/Chinese runtime guides |
| M054 | Definition context, date builtins, and Frame dependency graphs | DONE | [`M054`](docs/specs/M054-definition-context-dates-frame-graph.md); focused RED stopped at three import/collection failures because date helpers and Frame graph exports did not exist; focused GREEN passed 37 behavior tests and the combined runtime/config/documentation set passed 42; nested/concurrent `lhs()`, strict leap/early-year date conversion, config integration, qualified definition/value lookup paths, masking, unresolved names, hierarchy cycles, validation invariants, and zero-evaluation/cache/trace effects are covered; `venv\Scripts\python.exe -m pytest -q --basetemp .test_tmp_m054_final` passed 664 tests at 99.26% branch coverage; strict mypy and Ruff passed; every new production module has 100% branch coverage and passes isolated source/docstring/line policy; repository-wide `scripts.quality` still stops only at the ledgered legacy source-policy backlog after pytest/mypy/Ruff; `git diff --check` passed 2026-08-08; specs, changelog, APIs, tutorials, and English/Chinese status synchronized |
| M055 | Evaluation ergonomics and audited Python module layout | DONE | [`M055`](docs/specs/M055-api-ergonomics-module-layout.md); RED passed 18 existing cases and failed 10 expected lexical-lhs/API/layout/tutorial cases (`y-y`, required Frame ID, unparsed string, and absent paths/docs); GREEN passed 38 core cases, then 74 dependency/refactor cases and 197 evaluator/dependency/layout cases; `lhs()` function bodies retain their lexical definition while arguments retain the caller, `FrameFactory.create()` defaults to `frame-<module name>`, and `evaluate_sync` prefers source text while preserving AST input; every production/maintenance filename is individually recorded in the architecture audit, dependency analytics now lives under mirrored nested packages, and touched evaluator files were split below 200 lines; the dependency tutorial's static/Frame/runtime examples execute with stated results and zero-evaluation guarantees; `venv\Scripts\python.exe -m pytest -q --basetemp .test_tmp_m055_final` passed 676 tests at 99.31% branch coverage; strict mypy/Ruff and isolated source policy pass; repository-wide policy remains gated only by the ledgered legacy backlog; `git diff --check` passed 2026-08-08 |
| M056 | Nested Frame package and side-effect-free variable inspection | DONE | [`M056`](docs/specs/M056-frame-inspection-package.md); RED collection failed because inspection exports did not exist; GREEN passed 89 focused Frame tests, 165 runtime/API/config tests, and 7 executable-doc/layout checks; direct Frame IDs accept strings or default to `frame-<module name>`; inspection reports cached success/failure, external and missing leaves, lexical owners, exact paths, repeated branches, and finite cycles without evaluating or tracing; the complete Frame subsystem and mirrored tests moved under nested packages, with core split to 128 lines; final full pytest passed 687 tests at 99.33% branch coverage, strict mypy/Ruff passed, new/changed Frame modules pass isolated source policy, `git diff --check` passed, and the repository-wide policy remains gated only by ledgered legacy debt 2026-08-08 |
| M057 | Per-parent inspection dependency deduplication | DONE | [`M057`](docs/specs/M057-inspection-dependency-deduplication.md); RED failed 2 focused cases because repeated direct `host`/`base` names produced duplicate children while 8 unaffected cases passed; GREEN passed 12 inspection cases covering first-seen order, missing/external terminals, separate shared branches, cycles, cache states, rendering, and zero-evaluation behavior; 9 executable tutorial/link/layout checks passed; final full pytest passed 689 tests at 99.33% branch coverage with `frame.inspector` at 100%; strict mypy/Ruff, isolated source policy, and `git diff --check` passed 2026-08-08 |
| M058 | Source-oriented inspection tree representation | DONE | [`M058`](docs/specs/M058-inspection-representation.md); external definition text omitted, AST/status spacing explicit, values use `type: repr`, and errors use `ErrorType: message`; RED/GREEN/full evidence recorded 2026-08-08 |

M051 commands: `venv\Scripts\python.exe -m pytest tests\release tests\test_package_metadata.py tests\test_m051_release.py -q --no-cov` passed 10 tests; `venv\Scripts\python.exe -m scripts.quality` passed pytest (558 tests, 99.12% branch coverage), strict mypy, and Ruff, then stopped at `scripts.check_project` on the pre-existing production-policy backlog. The composite release command was `venv\Scripts\python.exe -m scripts.release_candidate --output <new space-and-Unicode directory>` and returned zero; its two fresh environments installed with pip `--no-deps --no-index`, with `PYTHONPATH` removed and imports resolved from each environment's site-packages.

## Release engineering

| ID | Deliverable | Status | Evidence |
|---|---|---|---|
| M052 | JihuLab GitLab-compatible shared verify/publish pipeline | VERIFIED | [`M052`](docs/specs/M052-jihulab-ci-pipeline.md); exact local tool pins and one-container setup/build/test/inspection structure pass regression checks and the full local quality gate 2026-08-09; an actual JihuLab runner and configured publication credentials remain external verification |

M058 refined-representation evidence: the focused RED command `venv\Scripts\python.exe -m pytest tests\runtime\frame\test_inspection.py -q --no-cov --basetemp .test_tmp_m058_refined_red` failed 6 and passed 8 tests before implementation. The GREEN rerun passed all 14 focused tests. `venv\Scripts\python.exe -m pytest tests\test_tutorials.py -q --no-cov --basetemp .test_tmp_m058_docs_escalated` passed 5 executable documentation checks. The full suite passed 691 tests at 99.34% branch coverage, with `pylcl/runtime/frame/inspection.py` at 100%. Strict mypy passed 251 source files, Ruff passed, the changed production file passed isolated documentation/source-size policy, and `git diff --check` passed.

## 0.2 configuration

| ID | Deliverable | Status | Evidence |
|---|---|---|---|
| M060 | Immutable configuration document/declaration model | DONE | [`M060`](docs/specs/M060-config-model.md); model order/origin/invariant tests pass 2026-08-08 |
| M061 | Source-aware explicit-continuation logical lines | DONE | [`M061`](docs/specs/M061-config-lines.md); newline, masking, continuation and exact-span tests pass 2026-08-08 |
| M062 | Configuration whitespace and comment semantics | DONE | [`M062`](docs/specs/M062-config-comments.md); literal-safe full/trailing comment and blank-line tests pass 2026-08-08 |
| M063 | Optional version metadata and colon definitions | DONE | [`M063`](docs/specs/M063-config-definitions.md); version/colon/duplicate and every binding-family test pass 2026-08-08 |
| M064 | Memory sources and eager file magic | DONE | [`M064`](docs/specs/M064-config-memory-sources.md); direct/f-string magic, physical spans, pathless errors and zero dependency edges pass 2026-08-08 |
| M065 | `using` syntax, paths, and async resolver protocol | DONE | [`M065`](docs/specs/M065-config-includes.md); quoted targets and canonical relative/absolute/`__dir__` resolver tests pass 2026-08-08 |
| M066 | Source-ordered expansion, precedence, and shadow history | DONE | [`M066`](docs/specs/M066-config-precedence.md); nested/repeated expansion, later-wins history, zero-load-evaluation, and flat cross-file dependency tests pass 2026-08-08 |
| M067 | Filesystem resolver and physical source origins | DONE | [`M067`](docs/specs/M067-config-origins.md); UTF-8/BOM, missing/directory/decode, containment, physical-origin, and three-level defining-file magic tests pass 2026-08-08 |
| M068 | Using cycles, single-flight, cache and cancellation | DONE | [`M068`](docs/specs/M068-config-include-cycles.md); cycles, retry, identity cache, cancellation isolation and cross-loop tests pass 2026-08-08 |
| M069 | Version negotiation and structured diagnostics | DONE | [`M069`](docs/specs/M069-config-versions-diagnostics.md); config subclasses/codes, spans, causes and version distinctions pass 2026-08-08 |
| M070 | Async-first public API and runtime bridge | DONE | [`M070`](docs/specs/M070-config-public-api.md); curated API, conversion, independent Frames and cleanup evaluation pass 2026-08-08 |
| M071 | Configuration limits, concurrency and stress corpus | DONE | [`M071`](docs/specs/M071-config-stress.md); 10,000 definitions, 200 sources, 100 callers/cancellations and all limits pass 2026-08-08 |
| M072 | English tutorials, configuration docs, and 0.2 release gate | DONE | [`M072`](docs/specs/M072-config-release.md); coherent 0.2.0 metadata, English tutorial path, full quality gate, artifacts, and two isolated nested-Unicode configuration smokes passed 2026-08-08; exact evidence below |

M073-M079 are intentionally unallocated; the numbering gap separates the 0.2
configuration track from the 0.3 CLI track and does not represent missing work.

## 0.3 CLI

| ID | Deliverable | Status | Evidence |
|---|---|---|---|
| M080 | Immutable CLI value contract | DONE | [`M080`](docs/specs/M080-cli-contract.md); immutable model/validation matrices pass; shared exact evidence below, 2026-08-09 |
| M081 | Invocation context and isolated logging boundaries | DONE | [`M081`](docs/specs/M081-cli-context.md); isolated disabled/UTF-8 file logger, format, exception, and automatic temporary cleanup cases pass; shared evidence below, 2026-08-09 |
| M082 | Commands, exact async decorators, and command groups | DONE | [`M082`](docs/specs/M082-cli-entrances.md); exact handler annotations, metadata inference, immutable groups, collisions, and snake_case validation pass; shared evidence below, 2026-08-09 |
| M083 | Full-argv and common-option parser | DONE | [`M083`](docs/specs/M083-cli-fixed-arity.md); aliases, strict dates, fixed arity, right-biased literals/LCL markers, and usage failures pass; shared evidence below, 2026-08-09 |
| M084 | Nested command-group routing | DONE | [`M084`](docs/specs/M084-cli-routing.md); root-container and nested exact leaf routing, scoped failures, and immutable paths pass; shared evidence below, 2026-08-09 |
| M085 | Deterministic structured help | DONE | [`M085`](docs/specs/M085-cli-help.md); fixed-width ANSI-free root/group/command help and stream behavior pass; shared evidence below, 2026-08-09 |
| M086 | Layered CLI Frame construction and ownership | DONE | [`M086`](docs/specs/M086-cli-frame-construction.md); preset/default/config/override/runtime precedence, laziness, presence checks, and reverse cleanup pass; shared evidence below, 2026-08-09 |
| M087 | Async command execution and result mapping | DONE | [`M087`](docs/specs/M087-cli-run.md); statuses, streams, ordinary/control exceptions, logging, output failures, and cleanup mapping pass; shared evidence below, 2026-08-09 |
| M088 | Dryrun pass-through semantics | DONE | [`M088`](docs/specs/M088-cli-dry-run.md); params/context/Frame propagation and handler-owned side-effect behavior pass without framework short-circuiting; shared evidence below, 2026-08-09 |
| M089 | Help and version built-ins | DONE | [`M089`](docs/specs/M089-cli-builtins.md); root/group/command help and root-only version short-circuit all runtime setup; shared evidence below, 2026-08-09 |
| M090 | Python-script process adapter | DONE | [`M090`](docs/specs/M090-cli-entry-points.md); explicit/ambient full argv, host-neutral labels, inert imports, and process-control propagation pass; shared evidence below, 2026-08-09 |
| M091 | Windows/POSIX CLI integration matrix | DONE | [`M091`](docs/specs/M091-cli-platform-tests.md); Windows 3.14 subprocess plus Windows/POSIX path-token corpus, Unicode/spaces/static includes/temporary logs, and Linux 3.14 CI configuration pass; shared evidence below, 2026-08-09 |
| M092 | CLI tutorial, bilingual docs, and 0.3 release gate | DONE | [`M092`](docs/specs/M092-cli-release.md); both tutorials execute, 0.3 API/metadata is coherent, and source/sdist-derived clean-install CLI smokes pass; shared evidence below, 2026-08-09 |
| M093 | CLI result shortcuts and `python -m pylcl.cli` commands | DONE | [`M093`](docs/specs/M093-cli-module-commands.md); shortcuts, static RESULT tree, lazy evaluation, ambient module adapter, subprocess, and full quality gates pass; exact evidence below, 2026-08-09 |
| M094 | CLI literal overrides as external host strings | DONE | [`M094`](docs/specs/M094-cli-literal-host-overrides.md); exact external literal/malformed nodes, lazy marker distinction, concatenation, CLI suite, and full quality gate pass; evidence below, 2026-08-09 |
| M095 | Native builtin/namespace dependency-tree values | DONE | [`M095`](docs/specs/M095-native-inspection-values.md); canonical provenance, stable typed native reprs, CLI composite tree, docs, and full quality gate pass; exact evidence below, 2026-08-09 |
| M096 | Uniform builtin repr and variable evaluation stacks | DONE | [`M096`](docs/specs/M096-builtin-repr-evaluation-stack.md); exhaustive builtin grammar, task-local lexical stacks, screenshot diagnosis, docs, and full quality gate pass; exact evidence below, 2026-08-09 |
| M097 | Boolean overrides and evaluated `parse_lcl` inspection | DONE | [`M097`](docs/specs/M097-boolean-overrides-evaluated-inspection.md); optional override boundaries, Boolean binding, cached success/failure trees, help/docs, and full quality gate pass; exact evidence below, 2026-08-09 |
| M098 | Canonical LCL AST value inspection repr | DONE | [`M098`](docs/specs/M098-ast-value-inspection-repr.md); external, cached, and native-fallback AST values plus evaluated LCL closures use typed canonical source without implementation-state leaks; exact evidence below, 2026-08-09 |
| M099 | CLI builtin inventory command | DONE | [`M099`](docs/specs/M099-cli-builtins-command.md); complete sorted top-level inventory with manifest-ordered nested methods, help, subprocess, drift validation, docs, and full gate pass; exact evidence below, 2026-08-09 |

CLI implementation evidence on 2026-08-09:

- RED: `venv\Scripts\python.exe -m pytest tests\cli -q --no-cov` failed during
  five test-module collections because `pylcl.cli` did not exist.
- GREEN/platform: `venv\Scripts\python.exe -m pytest tests\cli -q --no-cov`
  passed 80 behavioural cases; the dedicated Windows/POSIX command used
  `tests\cli\test_process.py tests\cli\test_platform.py` and passed 7 cases on
  win32 Python 3.14.2. Runtime configs are static case constants and every
  enabled test log is beneath `TemporaryDirectory`.
- Quality: `venv\Scripts\python.exe -m scripts.quality` passed 768 tests at
  99.39% branch coverage, strict mypy over 276 files, Ruff, exhaustive
  source/docstring/line policy, and `git diff --check`.
- Release: `venv\Scripts\python.exe -m scripts.release_candidate --output
  ".codex_tmp\release-cli-0.3.0-final-tree"` built and inspected exactly
  `pylcl-0.3.0.tar.gz` (313800 bytes, 380 members,
  SHA-256 `7f35d5da4435ee5f185c406a20b655d9c86f0c08b1aa0be884adcea72aabcbf6`)
  and `pylcl-0.3.0-py3-none-any.whl` (183207 bytes, 139 members,
  SHA-256 `160d4fbc5e87763368bb574367cc61d7eb83ca2f3b066bc9bca4d22e4a907a62`).
  Separate no-index/no-dependency clean environments for the source wheel and
  sdist-derived wheel passed import, nested lazy override, as-of, dryrun, help,
  version, usage failure, temporary logging, and handler-exception smokes.

M093 RED command: `venv\Scripts\python.exe -m pytest
tests\cli\test_models.py tests\cli\test_module_entrance.py -q --no-cov` stopped
during `test_module_entrance.py` collection with `ModuleNotFoundError: No module
named 'pylcl.cli.application'`, proving the shortcuts/module-command milestone
was absent before implementation on 2026-08-09.

M093 GREEN and verification evidence on 2026-08-09:

- `venv\Scripts\python.exe -m pytest tests\cli\test_models.py
  tests\cli\test_module_entrance.py -q --no-cov` passed 26 focused tests;
  `venv\Scripts\python.exe -m pytest tests\cli -q --no-cov` passed all 84 CLI
  tests. Strict mypy passed 31 focused source files, Ruff and isolated
  `scripts.check_project pylcl\cli` passed, and `git diff --check` passed.
- The parse example printed a non-evaluated `RESULT@cli_runtime/cli_overrides`
  root for `a + b` followed by ordered `a` and `b` literal-string leaves. The
  unsafe `1 / 0 + missing` case returned success with `NotEvaluated` and a
  missing-name leaf, proving static inspection performed no evaluation.
- The eval example printed exactly `100200`; missing `RESULT` and division by
  zero returned status 2 on stderr. In-process ambient argv and a real
  `python -m pylcl.cli` Unicode/option-looking subprocess both returned zero,
  preserved token values, and created no default log or other working files.
- `venv\Scripts\python.exe -m scripts.quality` passed 772 tests at 99.39%
  branch coverage, strict mypy over 279 files, Ruff, exhaustive
  source/docstring/line policy, and the final diff check.

M094 RED command: `venv\Scripts\python.exe -m pytest
tests\cli\test_module_entrance.py::test_parse_lcl_renders_a_non_evaluating_static_result_tree
-q --no-cov` failed the literal-result assertion: actual output was
`RESULT@cli_runtime/cli_overrides: '100' (NotEvaluated) NoneType: None` instead
of `(ExternalProvided) str: '100'`, reproducing the override-origin bug on
2026-08-09.

M094 GREEN and verification evidence on 2026-08-09:

- `venv\Scripts\python.exe -m pytest tests\cli\test_parser.py
  tests\cli\test_binding.py tests\cli\test_module_entrance.py -q --no-cov`
  passed 19 focused cases, then `venv\Scripts\python.exe -m pytest tests\cli -q
  --no-cov` passed all 85 CLI cases. Strict mypy, Ruff, isolated CLI source and
  docstring policy, and `git diff --check` passed.
- `python -m pylcl.cli parse_lcl -o RESULT 100` printed exactly
  `RESULT@cli_runtime/cli_overrides: (ExternalProvided) str: '100'`. The
  `RESULT=LCL[a+b]` tree retained a `NotEvaluated` root with external string
  leaves `a='100'` and `b='200'`; `eval_lcl` still printed `100200`.
- Empty/malformed markers remain exact external strings, while valid markers,
  including `LCL['100']`, remain lazy definitions. Direct binding coverage also
  proves raw `CliParams`, runtime values, precedence, evaluation, and cleanup.
- `venv\Scripts\python.exe -m scripts.quality` passed 773 tests at 99.39%
  branch coverage, strict mypy over 279 files, Ruff, exhaustive
  source/docstring/line policy, and the final diff check.

M095 RED command: `venv\Scripts\python.exe -m pytest
tests\runtime\frame\test_inspection.py::test_canonical_values_are_native_with_stable_typed_representations
tests\stdlib\test_namespaces.py::test_namespace_is_an_ordered_mapping_and_attribute_view
tests\cli\test_module_entrance.py::test_parse_lcl_renders_a_non_evaluating_static_result_tree
-q --no-cov` failed all 3 cases: `NativeProvided` was absent, `len` remained
external, and `StdlibNamespace` exposed `mappingproxy` members plus function
addresses, reproducing the screenshot on 2026-08-09.

M095 GREEN and verification evidence on 2026-08-09:

- The expanded runtime/stdlib/API/CLI/tutorial/documentation command passed 53
  focused cases. It covers canonical builtins, Python types/functions, standard
  namespaces, ordinary external values, lookalike Frame IDs, missing names, and
  descendant provenance without evaluating the inspected expression.
- `python -m pylcl.cli parse_lcl -o RESULT
  "LCL[len(a)+iter(b)+[c for c in x]]"` printed `len` as
  `(NativeProvided) builtin_function_or_method: <built-in function len>` and
  `iter` as `(NativeProvided) StdlibNamespace:
  StdlibNamespace(namespace='iter')`, with no `mappingproxy` or memory address.
  A second composite tree retained `a@cli_overrides: (ExternalProvided) str:
  'items'`, proving that native classification does not absorb CLI values.
- `venv\Scripts\python.exe -m scripts.quality` passed 774 tests at 99.39%
  branch coverage, strict mypy over 279 source files, Ruff, exhaustive
  source/docstring/line policy, and the final diff check. The changed Frame
  inspection, Frame core, API, and stdlib namespace modules each report 100%
  coverage.

M096 RED command: `venv\Scripts\python.exe -m pytest
tests\runtime\frame\test_inspection.py::test_canonical_values_use_uniform_builtin_representations
tests\test_errors.py::test_evaluation_error_renders_an_immutable_variable_stack
tests\test_errors.py::test_error_rejects_invalid_variable_stacks
tests\runtime\frame\test_flights.py::test_nested_failure_reports_direct_to_failing_variable_stack
tests\cli\test_module_entrance.py::test_eval_lcl_reports_malformed_override_and_lexical_variable_stacks
-q --no-cov` failed 4 and passed 3 parameterized cases: native `len` still used
the Python `builtin_function_or_method` repr, `LclError` rejected or lacked
`variable_stack`, and both nested Frame and malformed-marker CLI errors omitted
their variable evaluation stacks on 2026-08-09.

M096 GREEN and verification evidence on 2026-08-09:

- The focused RED selection passed all 7 cases after implementation; the
  expanded evaluator/Frame/CLI/documentation command passed 352 cases. Tests
  exhaust every canonical builtin and namespace, preserve external callable
  reprs, retain cached failure identity, and prove nested and concurrent stack
  isolation plus lexical LCL function ownership.
- `python -m pylcl.cli parse_lcl -o RESULT
  "LCL[len([]) + iter.first([1])]"` printed exact native leaves
  `(NativeProvided) Builtin Function: len` and
  `(NativeProvided) Builtin Namespace: iter`.
- The screenshot-shaped incomplete `quicksort` marker appeared under
  `parse_lcl` as `quicksort@cli_overrides: (ExternalProvided) str: ...`.
  `eval_lcl` then reported `TypeError: 'str' object is not callable [variable
  evaluation stack: RESULT]`. A valid `quicksort` LCL function with an internal
  division failure reported `[variable evaluation stack: RESULT -> quicksort]`.
- `venv\Scripts\python.exe -m scripts.quality` passed 781 tests at 99.40%
  branch coverage, strict mypy over 279 source files, Ruff, exhaustive
  source/docstring/line policy, and the final diff check.

M097 RED command: `venv\Scripts\python.exe -m pytest
tests\cli\test_parser.py::test_override_without_value_is_true_and_never_consumes_an_override_option
tests\cli\test_parser.py::test_common_parser_rejects_duplicate_and_arity_errors
tests\cli\test_models.py::test_cli_values_are_detached_and_statuses_are_exit_codes
tests\cli\test_models.py::test_value_models_reject_each_invalid_public_shape
tests\cli\test_binding.py::test_literal_overrides_are_host_values_beside_lazy_definitions
tests\cli\test_module_entrance.py::test_parse_lcl_eval_flag_renders_success_and_failure_cache_trees
-q --no-cov` failed 4 and passed 26 parameterized cases: the parser consumed
the next `-o` as a value or rejected trailing `-o EVAL`, `CliParams` rejected
`True`, binding could not receive a Boolean override, and `parse_lcl` had no
evaluated-inspection mode on 2026-08-09.

M097 GREEN and verification evidence on 2026-08-09:

- The focused RED command passed all 30 parameterized cases after implementation;
  the complete CLI suite passed 89 cases and the focused parser/model/binding/
  help/module/tutorial/documentation gate passed 54. Strict mypy, Ruff, isolated
  CLI source policy, and `git diff --check` passed.
- `python -m pylcl.cli parse_lcl -o var -o RESULT "LCL[var]"` rendered
  `var@cli_overrides: (ExternalProvided) bool: True`, proving the following
  `-o` began a new override rather than becoming `var`'s string value.
- `python -m pylcl.cli parse_lcl -o RESULT "LCL[1 + 2]" -o EVAL` rendered
  `RESULT` as `(Cached) int: 3`. The failing `LCL[1 / 0]` variant still returned
  a tree containing `(Cached) LclEvaluationError`, `division by zero`, and
  `[variable evaluation stack: RESULT]`.
- `venv\Scripts\python.exe -m scripts.quality` passed 784 tests at 99.40%
  branch coverage, strict mypy over 279 source files, Ruff, exhaustive
  source/docstring/line policy, and the final diff check.

M098 RED command: `venv\Scripts\python.exe -m pytest
tests\runtime\frame\test_inspection.py::test_inspection_renders_ast_values_as_typed_canonical_lcl_source
-q --no-cov` failed its exact external-value assertion: instead of
`LclBinary: base + 2`, inspection emitted the complete `LclBinary(...)`
dataclass repr with nested `SourceSpan`, `LclName`, operator, and constant
internals on 2026-08-09.

M098 GREEN and verification evidence on 2026-08-09:

- The focused regression passed, covering external, cached-definition, and
  native-fallback AST values, ordinary strings, unsupported custom AST fallback,
  canonical function/comprehension source, and unchanged object identity.
- The combined Frame, CLI module/tutorial, and documentation set passed 37
  tests. The runtime smoke rendered
  `expression@user/LCL_IMPORTS: (ExternalProvided) LclBinary: base + 2`.
- `venv\Scripts\python.exe -m scripts.quality` passed 785 tests at 99.40%
  branch coverage, strict mypy over 279 source files, Ruff, exhaustive
  source/docstring/line policy, executable documentation, artifact checks, and
  the final diff check.

M098 evaluated-function repr refinement evidence on 2026-08-09:

- RED: `venv\Scripts\python.exe -m pytest
  tests\runtime\frame\test_inspection.py::test_cached_lcl_function_uses_typed_canonical_source_repr
  -q --no-cov` failed because `repr(LclFunctionValue)` exposed
  `BoundParameter`, nested AST/`SourceSpan`, resolver, and evaluator internals.
- GREEN retains the originating `LclFunction` node and prints it through the
  canonical source printer. The screenshot-shaped fixed-point quicksort smoke
  returned `[-1, 2, 2, 5, 7, 9]` and rendered the cached value as
  `LclFunctionValue: def (items): ...` with no dataclass state.
- The focused evaluator/Frame/CLI gate passed 35 cases outside the Windows
  sandbox so subprocess temporary directories could clean up normally.
  `venv\Scripts\python.exe -m scripts.quality` then passed 786 tests at 99.40%
  branch coverage, strict mypy over 279 source files, Ruff, exhaustive source
  and documentation policy, executable documentation, and artifact checks.

Requested native recursion follow-up evidence on 2026-08-09 (no new spec):

- Added the Python variadic eager Z-combinator helper `recursive(builder)` to
  `LCL_BUILTINS`. Focused factorial, invalid-builder/step, recursive quicksort,
  native inspection, and fixed-inventory coverage passed 34 tests.
- Added a separate executable-style builtin example to the LCL tutorial. The
  existing LCL Y/Z tutorial source and `tests/lang/evaluator/test_functions.py`
  combinator cases were not changed.
- `venv\Scripts\python.exe -m scripts.quality` passed 789 tests at 99.40%
  branch coverage, strict mypy over 281 source files, Ruff, exhaustive source
  and documentation policy, executable documentation, and artifact checks.

M099 RED command: `venv\Scripts\python.exe -m pytest
tests\cli\test_builtin_docs.py
tests\cli\test_module_entrance.py::test_builtins_command_prints_the_reviewed_inventory
-q --no-cov` stopped during collection because `pylcl.cli.builtin_docs` did not
exist on 2026-08-09.

M099 GREEN and verification evidence on 2026-08-09:

- The focused RED selection passed 3 cases after implementation. Expanded
  CLI/API/stdlib verification passed 146 cases, including root/command help and
  an actual `python -m pylcl.cli builtins` subprocess with empty stderr and no
  log artifacts.
- The command prints 52 deterministic lines: 44 name-sorted top-level builtin,
  root-function, and namespace entries plus 8 two-space-indented methods in
  manifest declaration order. Representative lines are
  `- recursive: Build a variadic eager fixed point.` and
  `  - collect: Collect sync or async items.`.
- Rainy metadata cases cover missing builtin/namespace summaries, cross-layer
  duplicate names, blank descriptions, and multiline descriptions; the new
  renderer has 100% statement and branch coverage.
- `venv\Scripts\python.exe -m scripts.quality` passed 797 tests at 99.41%
  branch coverage, strict mypy over 283 source files, Ruff, exhaustive source
  and documentation policy, executable documentation, artifact checks, and the
  final diff check.

Requested recursive-result repr follow-up evidence on 2026-08-09:

- RED: the focused LCL/Python builder cases failed because `recursive` returned
  `<function recursive.<locals>.invoke at 0x...>`.
- GREEN replaces the anonymous closure with a callable `RecursiveFunction`.
  LCL builders render their canonical expression and Python builders render
  their function name. Inspection uses the value repr directly, avoiding a
  duplicate Python type prefix.
- The screenshot-shaped evaluated quicksort tree returned
  `[-1, 2, 2, 5, 7, 9]` and rendered `(Cached) Recursive Function: def (again):
  ...`; the nested native leaf remained `Builtin Function: recursive`.
- The focused recursive/inspection/CLI regression gate passed 34 cases.
  `venv\Scripts\python.exe -m scripts.quality` passed 798 tests at 99.41%
  branch coverage, strict mypy over 283 source files, Ruff, exhaustive source
  and documentation policy, executable documentation, and artifact checks.

Awaitable iterable-item RED evidence on 2026-08-09:

- The focused shared-iteration, screenshot-shaped starred `map`, PEP 798
  comprehension, and reviewed iterable-helper command failed all 5 cases.
  Synchronous and asynchronous iterables yielded raw coroutine objects, and an
  item coroutine's exception was deferred instead of raised while consuming it.

Awaitable iterable-item GREEN and verification evidence on 2026-08-09:

- `iterate_values` now recursively resolves every sync/async yielded item. The
  five RED cases passed, covering ordinary and failing item awaitables, starred
  Python `map` over an LCL function, PEP 798 comprehension flattening, and
  `iter.collect`/`iter.first`.
- The exact screenshot command run with `RuntimeWarning` promoted to an error
  rendered `(Cached) list: ['a', 'b']` and no coroutine warning. The expanded
  evaluator/stdlib/CLI warning-as-error gate passed 193 cases.
- `venv\Scripts\python.exe -m scripts.quality` passed 803 tests at 99.41%
  branch coverage, strict mypy over 283 source files, Ruff, exhaustive source
  and documentation policy, executable documentation, artifact checks, and the
  final diff check.

Post-M099 exhaustive coverage audit evidence on 2026-08-09:

- Baseline `venv\Scripts\python.exe -m pytest --cov-report=term-missing
  --cov-report=json:coverage.json` passed 803 tests at 99.41% branch coverage
  while reporting 16 missing statements and 25 partial branches across AST,
  CLI, config, evaluator, lexer, parser, and dependency-ordering modules.
- RED updated the M003 contract and policy assertion to require 100% branch
  coverage; the focused command failed at `99 != 100`. The complete audit added
  sunny, rainy, and composite assertions for every reported path, including
  repeated cleanup failures, nested help, no-log output, task-owner replacement,
  nested file magic, unpacking failures, exact EOF diagnostics, parser guards,
  complete acyclic DFS traversal, and malformed union-valued ASTs.
- The audit found that malformed call and dictionary AST wrappers were silently
  ignored. Their evaluators now raise explicit `TypeError` failures, with public
  `LclEvaluationError` cause assertions covering each case.
- Focused GREEN passed 149 cases, the final call-wrapper regression passed 8,
  and the repository coverage run passed 818 tests with 5,306 statements and
  1,616 branches at 100.00%: zero missing statements and zero partial branches.
- `venv\Scripts\python.exe -m scripts.quality` passed the same 818 tests at
  100.00% branch coverage, strict mypy over 283 source files, Ruff, exhaustive
  source/docstring policy, executable documentation, artifact checks, and the
  final project checks.

## 0.4 hardening

| ID | Deliverable | Status |
|---|---|---|
| M100 | Trusted-input security boundary audit | NOT_STARTED |
| M101 | Public API types, docstrings and logging audit | NOT_STARTED |
| M102 | Python 3.14 differential corpus | NOT_STARTED |
| M103 | AST round-trip properties and parser fuzzing | NOT_STARTED |
| M104 | Large dependency graph stress | NOT_STARTED |
| M105 | Concurrency, refresh, cancellation and close stress | NOT_STARTED |
| M106 | Frame, closure, task and async-iterator leak checks | NOT_STARTED |
| M107 | Windows/Linux-neutral packaging and install audit | NOT_STARTED |
| M108 | Non-blocking parse/evaluation/memory performance baseline | NOT_STARTED |
| M109 | 0.4.0 documentation, full quality gate and release candidate | NOT_STARTED |

## Utilities

| ID | Deliverable | Status | Evidence |
|---|---|---|---|
| M601 | Workflow execution status trees and scoped finalization | DONE | [`M601`](docs/specs/M601-execution-status.md); RED failed with two expected missing-module collection errors; focused GREEN passed 18 tests including executable tutorial examples; final `venv\Scripts\python.exe -m scripts.quality` passed 836 tests at 100.00% branch coverage with strict mypy, Ruff, source/docstring, executable-documentation, artifact, and project checks; `git diff --check` passed, 2026-08-10 |
| M602 | Scoped workflow steps | DONE | [`M602`](docs/specs/M602-scoped-steps.md); RED focused collection failed with the expected missing `ExecutionStatusStep` import; focused GREEN passed 24 workflow tests; final `venv\Scripts\python.exe -m scripts.quality` passed 842 tests at 100.00% branch coverage with strict mypy, Ruff, source/docstring, executable-documentation, artifact, and project checks; `git diff --check` passed, 2026-08-10 |

## Completion evidence rules

Each detailed milestone entry added while work advances must link its spec and
tests, list exact verification commands, summarize observed output, and record
the completion date. Group rows above are split before implementation begins.
README files are updated on every `DONE` transition.
