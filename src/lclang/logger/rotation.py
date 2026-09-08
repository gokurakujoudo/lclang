"""Validated rotation policies and independently advancing deadlines."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lclang.logger.validation import boolean, fields

# Seconds per accepted interval unit; SI seconds and conventional UTC days avoid DST ambiguity.
INTERVAL_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


@dataclass(frozen=True, slots=True)
class RotationConfig:
    """Hold resolved rotation controls.

    :param mode: None, size, time, or either-trigger policy.
    :param max_bytes: Size threshold in encoded bytes, zero when unused.
    :param seconds: Time interval in seconds, zero when unused.
    :param align: Whether to use UTC wall-clock boundaries.
    """

    mode: str = "none"
    max_bytes: int = 0
    seconds: int = 0
    align: bool = False


def rotation_config(value: object, path: str, *, partial: bool = False) -> RotationConfig:
    """Resolve a rotation declaration without touching time or files.

    :param value: Mapping of policy fields.
    :param path: Diagnostic configuration path.
    :param partial: Whether a default template may omit fields supplied by sinks.
    :returns: Validated policy.
    :raises ValueError: If mode, interval, alignment, or size is invalid.
    """
    data = fields(value, {"mode", "max_bytes", "interval", "align"}, path)
    mode = data.get("mode", "none")
    if mode not in ("none", "size", "time", "size_or_time"):
        raise ValueError(f"{path}.mode: invalid rotation mode")
    maximum = data.get("max_bytes", 0)
    if type(maximum) is not int or maximum < 0:
        raise ValueError(f"{path}.max_bytes: expected nonnegative integer bytes")
    if not partial and mode in ("size", "size_or_time") and maximum == 0:
        raise ValueError(f"{path}.max_bytes: size rotation requires positive bytes")
    interval = data.get("interval")
    seconds = 0
    if interval is not None:
        if not isinstance(interval, str) or not (
            match := re.fullmatch(r"([1-9]\d*)([smhd])", interval)
        ):
            raise ValueError(f"{path}.interval: expected positive integer s/m/h/d")
        seconds = int(match[1]) * INTERVAL_SECONDS[match[2]]
    if not partial and mode in ("time", "size_or_time") and not seconds:
        raise ValueError(f"{path}.interval: time rotation requires an interval")
    align = boolean(data.get("align", False), f"{path}.align")
    if align and interval not in ("1h", "1d") and not (partial and interval is None):
        raise ValueError(f"{path}.align: aligned intervals must be 1h or 1d UTC")
    return RotationConfig(str(mode), maximum, seconds, align)


class RotationTimer:
    """Track one sink's deadline without resetting it after size rotation."""

    def __init__(self, config: RotationConfig, monotonic: float, wall: float) -> None:
        """Start time rotation from runtime initialization.

        :param config: Resolved rotation policy.
        :param monotonic: Current monotonic seconds.
        :param wall: Current Unix seconds.
        """
        self.config = config
        self.deadline = float("inf")
        if config.mode in ("time", "size_or_time"):
            self.deadline = (
                (wall // config.seconds + 1) * config.seconds
                if config.align
                else monotonic + config.seconds
            )

    def remaining(self, monotonic: float, wall: float) -> float:
        """Return the delay until this sink must rotate.

        :param monotonic: Current monotonic seconds.
        :param wall: Current Unix seconds.
        :returns: Nonnegative seconds, or infinity for disabled timers.
        """
        return max(0.0, self.deadline - (wall if self.config.align else monotonic))

    def advance(self, monotonic: float, wall: float) -> None:
        """Skip elapsed intervals while retaining the original schedule.

        :param monotonic: Current monotonic seconds.
        :param wall: Current Unix seconds.
        """
        now = wall if self.config.align else monotonic
        self.deadline += (
            int((now - self.deadline) // self.config.seconds) + 1
        ) * self.config.seconds
