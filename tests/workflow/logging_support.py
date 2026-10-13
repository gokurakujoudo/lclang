"""Callback contracts shared by workflow and mapping log tests."""

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Protocol


class Transform(Protocol):
    """Declare an asynchronous text callback without requiring a record type."""

    def __call__(self, value: str, /) -> Awaitable[str]: ...


@dataclass(kw_only=True)
class CallbackArgs:
    """Receive an LCL function through a callback annotation."""

    transform: Transform


@dataclass(kw_only=True)
class CallbackOutputs:
    """Retain the callback alongside its observable result."""

    transform: Transform
    value: str
