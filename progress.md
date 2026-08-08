# pylcl implementation progress

Status flow: `NOT_STARTED -> SPEC_READY -> RED -> GREEN -> VERIFIED -> DONE`.
`BLOCKED` may be used only with a concrete reason. At most one milestone is
actively implemented. The first non-DONE item is the default next task.

## Current state

- Target release: 0.4.0
- Active milestone: M080
- Latest completed milestone: M072
- Last verified: 2026-08-08

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

Planning verification: the parser-backed language-guide examples and all 26
individual M060-M072/M080-M092 specification structures passed 30 focused tests;
the complete quality gate passed 575 tests at 99.12% branch coverage with strict
mypy, Ruff, project-policy, and diff checks on 2026-08-04.

M060-M072 RED began with three collection failures because `pylcl.config` did
not exist. Focused GREEN passed 58 parser/config cases; the completed config
suite then passed 37 behavior/documentation/stress cases. The English tutorial
refactor recorded five expected RED failures, then passed seven focused tutorial
and configuration-documentation checks. Final M072 work corrected the policy
measurement contract, documented every remaining production declaration, and
closed the inherited repository-wide policy backlog. The focused 0.2 release
RED run failed 7 and passed 7 tests; GREEN passed 14. The authoritative
`venv\Scripts\python.exe -m scripts.quality` run passed 695 tests at 99.34%
branch coverage, strict mypy over 251 source files, Ruff, complete
source/docstring policy, and `git diff --check`. A later smoke-source regression
added one compile test and was fixed before final verification.

The no-publication command `venv\Scripts\python.exe -m scripts.release_candidate
--output ".codex_tmp\release 0.2.0 最终"` built and inspected
`pylcl-0.2.0.tar.gz` (284990 bytes, SHA-256
`2d9445a169b4bd97692a8d448a423f5d06d7a0f97dc64dc651793f5ecc1d2897`, 352
members) and `pylcl-0.2.0-py3-none-any.whl` (162699 bytes, SHA-256
`9ba0085b76415688b417cf826708304a3999f81b38fdc2a0f256b9cadbac8f55`, 126
members). Metadata reports `pylcl`, `0.2.0`, `>=3.14`, MIT, no dependencies,
and `py3-none-any`. Source and sdist-derived wheels have matching normalized
members. Both isolated offline installs reported `version=0.2.0`, `value=2`,
`dependency=base`, `config=42`, `history=2`, and `closed=true` after loading a
nested Unicode `using` graph with physical provenance. Verified artifacts were
copied without overwriting historical files to `dist/`.

## 0.3 CLI

| ID | Deliverable | Status | Evidence |
|---|---|---|---|
| M080 | Immutable typed CLI application contract | SPEC_READY | [`M080`](docs/specs/M080-cli-contract.md); contract and sunny/rainy/composite TDD matrix specified 2026-08-04 |
| M081 | Explicit invocation context and host boundaries | SPEC_READY | [`M081`](docs/specs/M081-cli-context.md); contract and sunny/rainy/composite TDD matrix specified 2026-08-04 |
| M082 | Entrance declaration and callable binding | SPEC_READY | [`M082`](docs/specs/M082-cli-entrances.md); contract and sunny/rainy/composite TDD matrix specified 2026-08-04 |
| M083 | Pure fixed-arity argv parser and conversions | SPEC_READY | [`M083`](docs/specs/M083-cli-fixed-arity.md); contract and sunny/rainy/composite TDD matrix specified 2026-08-04 |
| M084 | Longest-path command routing | SPEC_READY | [`M084`](docs/specs/M084-cli-routing.md); contract and sunny/rainy/composite TDD matrix specified 2026-08-04 |
| M085 | Deterministic help and usage rendering | SPEC_READY | [`M085`](docs/specs/M085-cli-help.md); contract and sunny/rainy/composite TDD matrix specified 2026-08-04 |
| M086 | CLI/config/preset Frame construction and ownership | SPEC_READY | [`M086`](docs/specs/M086-cli-frame-construction.md); contract and sunny/rainy/composite TDD matrix specified 2026-08-04 |
| M087 | Async-first run orchestration and exit mapping | SPEC_READY | [`M087`](docs/specs/M087-cli-run.md); contract and sunny/rainy/composite TDD matrix specified 2026-08-04 |
| M088 | Side-effect-free dry-run plans and redaction | SPEC_READY | [`M088`](docs/specs/M088-cli-dry-run.md); contract and sunny/rainy/composite TDD matrix specified 2026-08-04 |
| M089 | Help, version, config-check and dry-run built-ins | SPEC_READY | [`M089`](docs/specs/M089-cli-builtins.md); contract and sunny/rainy/composite TDD matrix specified 2026-08-04 |
| M090 | Console entry points and process adapter | SPEC_READY | [`M090`](docs/specs/M090-cli-entry-points.md); contract and sunny/rainy/composite TDD matrix specified 2026-08-04 |
| M091 | Windows/POSIX platform integration matrix | SPEC_READY | [`M091`](docs/specs/M091-cli-platform-tests.md); contract and sunny/rainy/composite TDD matrix specified 2026-08-04 |
| M092 | Bilingual documentation and 0.3 release gate | SPEC_READY | [`M092`](docs/specs/M092-cli-release.md); contract and sunny/rainy/composite TDD matrix specified 2026-08-04 |

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

## Completion evidence rules

Each detailed milestone entry added while work advances must link its spec and
tests, list exact verification commands, summarize observed output, and record
the completion date. Group rows above are split before implementation begins.
README files are updated on every `DONE` transition.
