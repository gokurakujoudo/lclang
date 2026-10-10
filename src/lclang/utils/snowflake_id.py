"""Caller-owned, thread-safe Snowflake integer identifiers.

Defines ``SnowflakeGenerator``.
"""

from threading import Lock
from time import time_ns

from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.exception_base import LclStateError, LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure

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


@guard_constructor(LclValidationError, UtilityErrorCode.E41_SNOWFLAKE_GENERATION_NATIVE_FAILURE)
class SnowflakeGenerator:
    """Generate increasing IDs with one retained instance per worker.

    :param worker_id: Application-assigned integer worker in 0..1023, excluding bool.
    :param epoch_ms: Nonnegative Unix millisecond epoch, excluding bool; defaults to
       2024-01-01 UTC. All generators in an ID domain must use the same epoch.
    :raises LclValidationError: If either argument is not an integer or is bool.
    :raises LclValidationError: If either argument is outside its supported range.

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
        :raises LclValidationError: If an argument is not an integer or is bool.
        :raises LclValidationError: If an argument is outside its supported range.
        """
        for name, value in (("worker_id", worker_id), ("epoch_ms", epoch_ms)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise LclValidationError(
                    f"{name} must be an integer excluding bool",
                    code=UtilityErrorCode.E41_ARGUMENT_MUST_BE_AN_INTEGER_EXCLUDING_BOOL,
                )
            if value < 0:
                raise LclValidationError(
                    f"{name} must be nonnegative",
                    code=UtilityErrorCode.E41_ARGUMENT_MUST_BE_NONNEGATIVE,
                )
        if worker_id > MAX_WORKER_ID:
            raise LclValidationError(
                f"worker_id must be at most {MAX_WORKER_ID}",
                code=UtilityErrorCode.E41_WORKER_ID_MUST_BE_AT_MOST,
            )
        self._worker_id = worker_id
        self._epoch_ms = epoch_ms
        self._lock = Lock()
        self._last_timestamp_ms = -1
        self._sequence = 0

    @property
    @guard_failure(LclUtilityError, UtilityErrorCode.E41_SNOWFLAKE_GENERATION_NATIVE_FAILURE)
    def worker_id(self) -> int:
        """Read the immutable worker identifier.

        :returns: Application-assigned worker in 0..1023.
        """
        return self._worker_id

    @property
    @guard_failure(LclUtilityError, UtilityErrorCode.E41_SNOWFLAKE_GENERATION_NATIVE_FAILURE)
    def epoch_ms(self) -> int:
        """Read the immutable timestamp origin.

        :returns: Epoch in nonnegative Unix milliseconds.
        """
        return self._epoch_ms

    @guard_failure(LclUtilityError, UtilityErrorCode.E41_SNOWFLAKE_GENERATION_NATIVE_FAILURE)
    def next_id(self) -> int:
        """Read wall time and atomically allocate the next 63-bit integer.

        A new millisecond starts at sequence zero. Failures preserve the last
        successful state; no clock waiting, sleeping, or logical time is used.

        :returns: Nonnegative ID packing elapsed milliseconds, worker, and sequence.
        :raises LclValidationError: If wall time precedes the configured epoch.
        :raises LclStateError: If wall time moves behind the last successful timestamp.
        :raises LclUtilityError: If the 41-bit timestamp or 12-bit sequence is exhausted.
        """
        with self._lock:
            timestamp_ms = time_ns() // 1_000_000 - self._epoch_ms
            if timestamp_ms < 0:
                raise LclValidationError(
                    "clock precedes the Snowflake epoch",
                    code=UtilityErrorCode.E41_CLOCK_PRECEDES_THE_SNOWFLAKE_EPOCH,
                )
            if timestamp_ms > MAX_TIMESTAMP_MS:
                raise LclUtilityError(
                    "Snowflake timestamp exhausted",
                    code=UtilityErrorCode.E41_SNOWFLAKE_TIMESTAMP_EXHAUSTED,
                )
            if timestamp_ms < self._last_timestamp_ms:
                raise LclStateError(
                    "clock moved backward during Snowflake generation",
                    code=UtilityErrorCode.E41_CLOCK_MOVED_BACKWARD_DURING_SNOWFLAKE_GENERATION,
                )
            sequence = self._sequence + 1 if timestamp_ms == self._last_timestamp_ms else 0
            if sequence > MAX_SEQUENCE:
                raise LclUtilityError(
                    "Snowflake sequence exhausted; retry after the clock advances",
                    code=UtilityErrorCode.E41_SNOWFLAKE_SEQUENCE_EXHAUSTED_RETRY_AFTER_THE_CLOCK_ADVANCES,
                )
            self._last_timestamp_ms = timestamp_ms
            self._sequence = sequence
            return (timestamp_ms << TIMESTAMP_SHIFT) | (self._worker_id << WORKER_SHIFT) | sequence
