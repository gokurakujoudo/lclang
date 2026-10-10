"""Configurable context managers shared by evaluator context tests."""

from types import TracebackType


class SyncManager:
    """Record configurable synchronous context protocol calls."""

    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        value: object = None,
        enter_error: BaseException | None = None,
        exit_error: BaseException | None = None,
        suppress: bool = False,
    ) -> None:
        """Store configured protocol outcomes and shared event sink."""
        self.name = name
        self.events = events
        self.value = value
        self.enter_error = enter_error
        self.exit_error = exit_error
        self.suppress = suppress
        self.seen_error: BaseException | None = None

    def __enter__(self) -> object:
        """Record acquisition and return the configured value."""
        self.events.append(f"enter {self.name}")
        if self.enter_error is not None:
            raise self.enter_error
        return self.value

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Record release, the pending error, and configured outcome."""
        del error_type, traceback
        self.events.append(f"exit {self.name}")
        self.seen_error = error
        if self.exit_error is not None:
            raise self.exit_error
        return self.suppress


class AsyncManager:
    """Record the asynchronous protocol while rejecting sync fallback."""

    def __init__(self, events: list[str], value: object) -> None:
        """Store the shared event sink and async enter value."""
        self.events = events
        self.value = value

    async def __aenter__(self) -> object:
        """Record and complete asynchronous acquisition."""
        self.events.append("async enter")
        return self.value

    async def __aexit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Record and complete asynchronous release."""
        del error_type, error, traceback
        self.events.append("async exit")
        return False

    def __enter__(self) -> object:
        """Fail if asynchronous protocol selection regresses."""
        raise AssertionError("sync protocol must not be selected")

    def __exit__(self, *details: object) -> bool:
        """Fail if asynchronous protocol selection regresses."""
        del details
        raise AssertionError("sync protocol must not be selected")
