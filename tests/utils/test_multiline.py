"""Multiline formatting retains order and never reads masked payloads."""

from dataclasses import dataclass
from typing import Any, cast

import pytest

from lclang.utils import make_multi_log_lines, make_repr_lines


@dataclass
class Record:
    """Keep declaration order different from sorted order."""

    zebra: object = 1
    a: object = 2


def test_record_sequences_keep_duplicates_and_stable_order() -> None:
    """Mixed one-shot input aligns all records without merging names."""
    records = [Record(), {"a": 3, "longer": 4}]
    assert make_repr_lines(iter(records)) == [
        "zebra : 1", "a     : 2", "a     : 3", "longer: 4",
    ]
    assert make_repr_lines(records, sort_keys=True, key_column_length=8) == [
        "a       : 2", "a       : 3", "longer  : 4", "zebra   : 1",
    ]
    assert make_repr_lines(Record(), key_column_length=1) == ["zebra: 1", "a    : 2"]
    assert make_repr_lines({}) == make_repr_lines(iter(())) == []


def test_masking_precedes_record_and_dictionary_reads() -> None:
    """Getters and dictionary hooks cannot observe masked value reads."""
    @dataclass
    class Guarded:
        secret: object = None

        def __getattribute__(self, name: str) -> object:
            if name == "secret":
                raise AssertionError("secret read")
            return object.__getattribute__(self, name)

    class GuardedDict(dict[str, object]):
        def __getitem__(self, name: str) -> object:
            raise AssertionError("dictionary read")

    assert make_repr_lines([Guarded(), GuardedDict(secret=object())], masked_keys={"secret"}) == [
        "secret: *masked*", "secret: *masked*",
    ]


@pytest.mark.parametrize("records", [Record, [Record], 42, "", "text", b"", [object()], {1: 2}])
def test_invalid_records_are_rejected(records: object) -> None:
    """Only record instances and string-keyed dictionaries are supported."""
    with pytest.raises(TypeError):
        make_repr_lines(records)


@pytest.mark.parametrize("width", [True, "3", 1.5, -1])
def test_width_is_validated_even_for_empty_input(width: object) -> None:
    """Invalid explicit widths cannot silently pass on an empty record."""
    with pytest.raises(ValueError if width == -1 else TypeError):
        make_repr_lines({}, key_column_length=cast(Any, width))


def test_body_indentation_and_safe_value_rendering() -> None:
    """Body newlines indent literally while represented value newlines stay escaped."""
    class Broken:
        def __repr__(self) -> str:
            raise ValueError("cannot render")

    assert make_multi_log_lines("title", ["a\n\nb", ""], "> ") == "title\n> a\n> \n> b\n> "
    assert make_multi_log_lines("title", []) == "title"
    assert make_repr_lines({"a": "x\ny", "b": Broken()}) == [
        "a: 'x\\ny'", "b: <repr failed: ValueError>",
    ]
    assert make_repr_lines({"a": "x" * 300})[0].endswith("...<truncated>")


def test_many_records_share_one_width_without_losing_fields() -> None:
    """A larger generator retains every repeated field and its stable order."""
    lines = make_repr_lines({"number": number} for number in range(5000))
    assert len(lines) == 5000
    assert lines[0] == "number: 0" and lines[-1] == "number: 4999"
