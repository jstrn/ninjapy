"""Tests for sync bridge utilities."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest

from ninjapy._sync import (
    SyncRunner,
    is_public_async_method,
    sync_iterator_from_async,
    wrap_async_iterator_method,
    wrap_async_method,
)


@pytest.fixture
def runner():
    sync_runner = SyncRunner()
    yield sync_runner
    sync_runner.close()


def test_sync_runner_runs_coroutine(runner):
    async def add(a: int, b: int) -> int:
        return a + b

    assert runner.run(add(2, 3)) == 5


def test_sync_runner_raises_inside_running_loop(runner):
    async def noop():
        return None

    async def call_sync_from_loop():
        runner.run(noop())

    with pytest.raises(RuntimeError, match="Cannot call synchronous NinjaRMMClient"):
        asyncio.run(call_sync_from_loop())


def test_sync_runner_close_is_idempotent(runner):
    runner.close()
    runner.close()


def test_sync_runner_raises_after_close():
    runner = SyncRunner()
    runner.close()

    with pytest.raises(RuntimeError, match="SyncRunner is closed"):
        runner.run(asyncio.sleep(0))


def test_sync_iterator_from_async(runner):
    async def async_gen() -> AsyncIterator[int]:
        for value in (1, 2, 3):
            yield value

    assert list(sync_iterator_from_async(async_gen(), runner)) == [1, 2, 3]


def test_wrap_async_method(runner):
    async def async_add(a: int, b: int) -> int:
        return a + b

    sync_add = wrap_async_method(runner, async_add)

    assert sync_add(4, 5) == 9


def test_wrap_async_iterator_method(runner):
    async def async_gen(start: int) -> AsyncIterator[int]:
        yield start
        yield start + 1

    sync_gen = wrap_async_iterator_method(runner, async_gen)

    assert list(sync_gen(10)) == [10, 11]


def test_is_public_async_method():
    async def public_async():
        return None

    async def _private_async():
        return None

    def public_sync():
        return None

    assert is_public_async_method("public_async", public_async) is True
    assert is_public_async_method("_private_async", _private_async) is False
    assert is_public_async_method("public_sync", public_sync) is False
