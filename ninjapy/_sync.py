"""Sync bridge utilities for wrapping async client methods."""

from __future__ import annotations

import asyncio
import inspect
import threading
from collections.abc import AsyncIterator, Iterator
from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")

_RUNNING_LOOP_ERROR = (
    "Cannot call synchronous NinjaRMMClient methods from a running event loop. "
    "Use AsyncNinjaRMMClient instead."
)


class SyncRunner:
    """Run async coroutines from synchronous code using a dedicated event loop."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._closed = False

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._closed:
            raise RuntimeError("SyncRunner is closed")

        if self._loop is not None and self._loop.is_running():
            return self._loop

        self._ready.clear()

        def _run_loop() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._ready.set()
            loop.run_forever()

        self._thread = threading.Thread(
            target=_run_loop,
            name="ninjapy-sync-runner",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait()
        assert self._loop is not None
        return self._loop

    def run(self, coro: Coroutine[Any, Any, T]) -> T:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(_RUNNING_LOOP_ERROR)

        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True
        if self._loop is None or not self._loop.is_running():
            return

        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._loop = None
        self._thread = None


def sync_iterator_from_async(async_iterator: AsyncIterator[T], runner: SyncRunner) -> Iterator[T]:
    """Bridge an async iterator into a synchronous iterator."""

    async def _drain() -> list[T]:
        items: list[T] = []
        async for item in async_iterator:
            items.append(item)
        return items

    for item in runner.run(_drain()):
        yield item


def wrap_async_method(
    runner: SyncRunner,
    async_method: Callable[..., Coroutine[Any, Any, T]],
) -> Callable[..., T]:
    """Wrap an async method so it can be called synchronously."""

    def sync_wrapper(*args: Any, **kwargs: Any) -> T:
        return runner.run(async_method(*args, **kwargs))

    return sync_wrapper


def wrap_async_iterator_method(
    runner: SyncRunner,
    async_method: Callable[..., AsyncIterator[T]],
) -> Callable[..., Iterator[T]]:
    """Wrap an async generator method for synchronous iteration."""

    def sync_wrapper(*args: Any, **kwargs: Any) -> Iterator[T]:
        async_gen = async_method(*args, **kwargs)
        return sync_iterator_from_async(async_gen, runner)

    return sync_wrapper


def is_public_async_method(name: str, value: Any) -> bool:
    """Return True if attribute should be exposed as a sync wrapper."""
    if name.startswith("_"):
        return False
    return inspect.iscoroutinefunction(value) or inspect.isasyncgenfunction(value)
