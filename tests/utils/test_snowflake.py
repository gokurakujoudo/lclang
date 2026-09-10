"""Deterministic downstream Snowflake generation contracts."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from lclang.utils import SnowflakeGenerator


def test_default_epoch_and_read_only_configuration() -> None:
    """The documented epoch and worker are immutable public configuration."""
    generator = SnowflakeGenerator(0)
    assert generator.epoch_ms == 1704067200000
    assert generator.worker_id == 0
    with patch("lclang.utils.snowflake.time_ns", return_value=1704067200000 * 1_000_000):
        assert generator.next_id() == 0
        assert generator.next_id() == 1
    with pytest.raises(AttributeError):
        generator.worker_id = 1  # type: ignore[misc]
    with pytest.raises(AttributeError):
        generator.epoch_ms = 0  # type: ignore[misc]


@pytest.mark.parametrize("value", [True, False, 1.5, "1", None])
def test_noninteger_arguments_are_rejected(value: object) -> None:
    """Boolean and coercible inputs never silently change the ID domain."""
    with pytest.raises(TypeError, match="worker_id"):
        SnowflakeGenerator(value)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="epoch_ms"):
        SnowflakeGenerator(0, epoch_ms=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("worker_id", [-1, 1024])
def test_worker_range_is_validated(worker_id: int) -> None:
    """Only the ten-bit worker domain is accepted."""
    with pytest.raises(ValueError, match="worker_id"):
        SnowflakeGenerator(worker_id)


def test_negative_epoch_is_rejected() -> None:
    """The epoch uses nonnegative Unix milliseconds."""
    with pytest.raises(ValueError, match="epoch_ms"):
        SnowflakeGenerator(0, epoch_ms=-1)


def test_layout_worker_separation_and_millisecond_sequence_reset() -> None:
    """Exact integer conversion packs all fields and resets only after time advances."""
    left = SnowflakeGenerator(7, epoch_ms=100)
    right = SnowflakeGenerator(8, epoch_ms=100)
    with patch("lclang.utils.snowflake.time_ns", return_value=101_999_999):
        assert left.next_id() == (1 << 22) | (7 << 12)
        assert left.next_id() == (1 << 22) | (7 << 12) | 1
        assert right.next_id() == (1 << 22) | (8 << 12)
    with patch("lclang.utils.snowflake.time_ns", return_value=102_000_000):
        assert left.next_id() == (2 << 22) | (7 << 12)


def test_clock_failures_preserve_state_and_allow_recovery() -> None:
    """Rollback and pre-epoch reads neither duplicate IDs nor corrupt the sequence."""
    generator = SnowflakeGenerator(0, epoch_ms=100)
    readings = [99, 102, 101, 99, 102, 103]
    with patch("lclang.utils.snowflake.time_ns", side_effect=[ms * 1_000_000 for ms in readings]):
        with pytest.raises(ValueError, match="epoch"):
            generator.next_id()
        assert generator.next_id() == 2 << 22
        with pytest.raises(RuntimeError, match="backward"):
            generator.next_id()
        with pytest.raises(ValueError, match="epoch"):
            generator.next_id()
        assert generator.next_id() == (2 << 22) | 1
        assert generator.next_id() == 3 << 22


def test_full_sequence_fails_repeatedly_then_recovers_next_millisecond() -> None:
    """No sequence wraps or clock waiting occur at the per-millisecond capacity."""
    generator = SnowflakeGenerator(1023, epoch_ms=0)
    with patch("lclang.utils.snowflake.time_ns", return_value=0):
        assert [generator.next_id() for _ in range(4096)] == [
            (1023 << 12) | sequence for sequence in range(4096)
        ]
        for _ in range(2):
            with pytest.raises(OverflowError, match="sequence"):
                generator.next_id()
    with patch("lclang.utils.snowflake.time_ns", return_value=1_000_000):
        assert generator.next_id() == (1 << 22) | (1023 << 12)


def test_timestamp_boundary_and_failed_read_do_not_consume_sequence() -> None:
    """The largest ID fits signed 64-bit storage; overflow never wraps the timestamp."""
    generator = SnowflakeGenerator(1023, epoch_ms=0)
    with patch("lclang.utils.snowflake.time_ns", return_value=(2**41 - 1) * 1_000_000):
        first = generator.next_id()
    with (
        patch("lclang.utils.snowflake.time_ns", return_value=2**41 * 1_000_000),
        pytest.raises(OverflowError, match="timestamp"),
    ):
        generator.next_id()
    with patch("lclang.utils.snowflake.time_ns", return_value=(2**41 - 1) * 1_000_000):
        assert generator.next_id() == first + 1
        remaining = [generator.next_id() for _ in range(4094)]
        assert remaining[-1] == 2**63 - 1


def test_concurrent_threads_share_one_sequence() -> None:
    """One generator issues each sequence once across concurrent callers."""
    generator = SnowflakeGenerator(1, epoch_ms=0)
    with (
        patch("lclang.utils.snowflake.time_ns", return_value=1_000_000),
        ThreadPoolExecutor(max_workers=8) as executor,
    ):
        futures = [executor.submit(generator.next_id) for _ in range(4096)]
        values = [future.result() for future in futures]
    assert sorted(values) == [(1 << 22) | (1 << 12) | sequence for sequence in range(4096)]
