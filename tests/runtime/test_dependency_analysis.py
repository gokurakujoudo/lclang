"""Unit tests mirroring :mod:`pylcl.runtime.dependency_analysis`."""

from pylcl.lang.parser import parse_expression
from pylcl.runtime import DependencyKind, analyze_dependencies


def _summary(source: str) -> list[tuple[str, DependencyKind]]:
    references = analyze_dependencies(parse_expression(source))
    return [(str(reference.name), reference.kind) for reference in references]


def test_ordinary_operands_are_eager_and_occurrences_remain_distinct() -> None:
    """Straight-line traversal retains runtime order and repeated spans."""
    assert _summary("left + right + left") == [
        ("left", DependencyKind.EAGER),
        ("right", DependencyKind.EAGER),
        ("left", DependencyKind.EAGER),
    ]


def test_short_circuit_and_conditional_nodes_weaken_only_skipped_paths() -> None:
    """Runtime-first operands stay eager while optional paths are conditional."""
    assert _summary("yes if condition else no") == [
        ("condition", DependencyKind.EAGER),
        ("yes", DependencyKind.CONDITIONAL),
        ("no", DependencyKind.CONDITIONAL),
    ]
    assert _summary("left and right or fallback") == [
        ("left", DependencyKind.EAGER),
        ("right", DependencyKind.CONDITIONAL),
        ("fallback", DependencyKind.CONDITIONAL),
    ]
    assert _summary("first < second < third") == [
        ("first", DependencyKind.EAGER),
        ("second", DependencyKind.EAGER),
        ("third", DependencyKind.CONDITIONAL),
    ]
    assert _summary("preferred ?? fallback") == [
        ("preferred", DependencyKind.EAGER),
        ("fallback", DependencyKind.CONDITIONAL),
    ]


def test_function_defaults_are_eager_and_bound_body_is_deferred() -> None:
    """Parameter scope begins in the body but not in default expressions."""
    source = "def (value=default, *items): value + items + outer"
    assert _summary(source) == [
        ("default", DependencyKind.EAGER),
        ("outer", DependencyKind.DEFERRED),
    ]


def test_materialized_comprehension_tracks_clause_scopes_and_paths() -> None:
    """Targets bind after iterable lookup and output remains conditional."""
    source = (
        "[combine(item, other, outer) for item in items "
        "if predicate(item) for other in others]"
    )
    assert _summary(source) == [
        ("items", DependencyKind.EAGER),
        ("predicate", DependencyKind.CONDITIONAL),
        ("others", DependencyKind.CONDITIONAL),
        ("combine", DependencyKind.CONDITIONAL),
        ("outer", DependencyKind.CONDITIONAL),
    ]


def test_generator_dependencies_are_all_deferred() -> None:
    """Creating a generator performs none of its iterable or body lookups."""
    source = "(combine(item, outer) for item in items if predicate(item))"
    assert _summary(source) == [
        ("items", DependencyKind.DEFERRED),
        ("predicate", DependencyKind.DEFERRED),
        ("combine", DependencyKind.DEFERRED),
        ("outer", DependencyKind.DEFERRED),
    ]
    assert _summary("{key: value for key in keys}") == [
        ("keys", DependencyKind.EAGER),
        ("value", DependencyKind.CONDITIONAL),
    ]


def test_try_assert_and_with_apply_precise_control_and_binding_scopes() -> None:
    """Handler/message paths weaken while finalization and with stay eager."""
    tried = (
        "try: operation() except Error as error: recover(error, fallback) "
        "finally: cleanup()"
    )
    assert _summary(tried) == [
        ("operation", DependencyKind.EAGER),
        ("Error", DependencyKind.CONDITIONAL),
        ("recover", DependencyKind.CONDITIONAL),
        ("fallback", DependencyKind.CONDITIONAL),
        ("cleanup", DependencyKind.EAGER),
    ]
    assert _summary("assert(condition, message)") == [
        ("condition", DependencyKind.EAGER),
        ("message", DependencyKind.CONDITIONAL),
    ]
    assert _summary("assert(condition)") == [("condition", DependencyKind.EAGER)]
    managed = "with manager as bound, factory(bound) as other: use(bound, other, outer)"
    assert _summary(managed) == [
        ("manager", DependencyKind.EAGER),
        ("factory", DependencyKind.EAGER),
        ("use", DependencyKind.EAGER),
        ("outer", DependencyKind.EAGER),
    ]
    assert _summary("with manager: outer") == [
        ("manager", DependencyKind.EAGER),
        ("outer", DependencyKind.EAGER),
    ]
    assert _summary("try: operation except: fallback") == [
        ("operation", DependencyKind.EAGER),
        ("fallback", DependencyKind.CONDITIONAL),
    ]


def test_nested_deferred_context_dominates_conditional_children() -> None:
    """Optional paths inside a lazy function cannot become less deferred."""
    source = "def (): yes if condition else no"
    assert _summary(source) == [
        ("condition", DependencyKind.DEFERRED),
        ("yes", DependencyKind.DEFERRED),
        ("no", DependencyKind.DEFERRED),
    ]
