"""Caller-owned, thread-safe Snowflake integer identifiers."""

from threading import Lock
from time import time_ns

# Unitless export names identify the supported downstream interface; layout constants stay local.
__all__ = ["SnowflakeGenerator"]

# This utility chooses 2024-01-01 UTC in Unix milliseconds as its default epoch, giving new
# applications roughly 69.7 years within the 41-bit elapsed-millisecond field.
DEFAULT_EPOCH_MS = 1704067200000

# The Snowflake 41/10/12 bit allocation leaves the signed 64-bit sign bit clear. Timestamp
# limits are elapsed milliseconds; worker and sequence limits are unitless inclusive maxima.
MAX_TIMESTAMP_MS = (1 << 41) - 1
MAX_WORKER_ID = (1 << 10) - 1
MAX_SEQUENCE = (1 << 12) - 1
WORKER_SHIFT = 12
TIMESTAMP_SHIFT = 22


class SnowflakeGenerator:
    """Generate increasing IDs with one retained instance per worker.

    :param worker_id: Application-assigned integer worker in 0..1023, excluding bool.
    :param epoch_ms: Nonnegative Unix millisecond epoch, excluding bool; defaults to
       2024-01-01 UTC. All generators in an ID domain must use the same epoch.
    :raises TypeError: If either argument is not an integer or is bool.
    :raises ValueError: If either argument is outside its supported range.

    .. note::
       Instances coordinate threads, not processes. Assign distinct workers to
       concurrent instances. State is not persisted: reusing a worker after a
       restart requires wall time beyond its previously emitted timestamps.
       Never recreate a generator per ID or inherit one into a forked child.
    """

    __slots__ = ("_worker_id", "_epoch_ms", "_lock", "_last_timestamp_ms", "_sequence")

    def __init__(self, worker_id: int, *, epoch_ms: int = DEFAULT_EPOCH_MS) -> None:
        """Validate the ID domain and initialize an unused millisecond sequence.

        :param worker_id: Integer worker in 0..1023, excluding bool.
        :param epoch_ms: Nonnegative integer Unix milliseconds, excluding bool.
        :raises TypeError: If an argument is not an integer or is bool.
        :raises ValueError: If an argument is outside its supported range.
        """
        for name, value in (("worker_id", worker_id), ("epoch_ms", epoch_ms)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer excluding bool")
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
        if worker_id > MAX_WORKER_ID:
            raise ValueError(f"worker_id must be at most {MAX_WORKER_ID}")
        self._worker_id = worker_id
        self._epoch_ms = epoch_ms
        self._lock = Lock()
        self._last_timestamp_ms = -1
        self._sequence = 0

    @property
    def worker_id(self) -> int:
        """Read the immutable worker identifier.

        :returns: Application-assigned worker in 0..1023.
        """
        return self._worker_id

    @property
    def epoch_ms(self) -> int:
        """Read the immutable timestamp origin.

        :returns: Epoch in nonnegative Unix milliseconds.
        """
        return self._epoch_ms

    def next_id(self) -> int:
        """Read wall time and atomically allocate the next 63-bit integer.

        A new millisecond starts at sequence zero. Failures preserve the last
        successful state; no clock waiting, sleeping, or logical time is used.

        :returns: Nonnegative ID packing elapsed milliseconds, worker, and sequence.
        :raises ValueError: If wall time precedes the configured epoch.
        :raises RuntimeError: If wall time moves behind the last successful timestamp.
        :raises OverflowError: If the 41-bit timestamp or 12-bit sequence is exhausted.
        """
        with self._lock:
            timestamp_ms = time_ns() // 1_000_000 - self._epoch_ms
            if timestamp_ms < 0:
                raise ValueError("clock precedes the Snowflake epoch")
            if timestamp_ms > MAX_TIMESTAMP_MS:
                raise OverflowError("Snowflake timestamp exhausted")
            if timestamp_ms < self._last_timestamp_ms:
                raise RuntimeError("clock moved backward during Snowflake generation")
            sequence = self._sequence + 1 if timestamp_ms == self._last_timestamp_ms else 0
            if sequence > MAX_SEQUENCE:
                raise OverflowError("Snowflake sequence exhausted; retry after the clock advances")
            self._last_timestamp_ms = timestamp_ms
            self._sequence = sequence
            return (timestamp_ms << TIMESTAMP_SHIFT) | (self._worker_id << WORKER_SHIFT) | sequence
