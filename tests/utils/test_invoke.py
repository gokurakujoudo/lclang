"""Typed callback invocation preserves the ordinary Python execution boundary."""

import asyncio
from collections.abc import Awaitable
from functools import partial
from typing import assert_type, cast

import pytest

from lclang.utils import invoke


@pytest.mark.asyncio
async def test_sync_async_callable_objects_and_arguments() -> None:
    """Each callable is called once, in the current task, retaining its parameter types."""
    calls: list[object] = []
    task = asyncio.current_task()

    def synchronous(value: int, *, increment: int) -> int:
        assert asyncio.current_task() is task
        calls.append(value)
        return value + increment

    async def asynchronous(value: str) -> str:
        calls.append(value)
        await asyncio.sleep(0)
        assert asyncio.current_task() is task
        return value.upper()

    class Callback:
        def __call__(self, value: object) -> object:
            calls.append(value)
            return value

    assert assert_type(await invoke(synchronous, 3, increment=4), int) == 7
    assert assert_type(await invoke(asynchronous, "abc"), str) == "ABC"
    assert await invoke(partial(synchronous, increment=2), 5) == 7
    value = object()
    assert await invoke(Callback(), value) is value
    assert calls == [3, "abc", 5, value]


@pytest.mark.asyncio
async def test_nested_awaitables_errors_and_cancellation() -> None:
    """Awaitable recursion and original failures follow the existing resolver."""

    async def nested() -> Awaitable[int]:
        async def inner() -> int:
            return 4

        return inner()

    assert cast(object, await invoke(nested)) == 4
    for error in (ValueError("broken"), asyncio.CancelledError("cancelled")):

        def fail(failure: BaseException = error) -> None:
            raise failure

        with pytest.raises(type(error)) as caught:
            await invoke(fail)
        assert caught.value is error

    started = asyncio.Event()
    finished = asyncio.Event()

    async def waiting() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            finished.set()

    task = asyncio.create_task(invoke(waiting))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()
