"""Tests for async pagination and concurrency helpers."""

from __future__ import annotations

import asyncio

import pytest

from ninjapy.async_helpers import collect_all, map_concurrent, paginate_after, paginate_cursor


@pytest.mark.asyncio
async def test_paginate_after_single_page():
    async def fetch_page(*, page_size: int, after=None, **kwargs):
        assert after is None
        return [{"id": 1}]

    items = [item async for item in paginate_after(fetch_page, page_size=2)]

    assert items == [{"id": 1}]


@pytest.mark.asyncio
async def test_paginate_after_multiple_pages():
    calls: list[int | None] = []

    async def fetch_page(*, page_size: int, after=None, **kwargs):
        calls.append(after)
        if after is None:
            return [{"id": 1}, {"id": 2}]
        if after == 2:
            return [{"id": 3}]
        return []

    items = [item async for item in paginate_after(fetch_page, page_size=2)]

    assert items == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert calls == [None, 2]


@pytest.mark.asyncio
async def test_paginate_after_empty_first_page():
    async def fetch_page(*, page_size: int, after=None, **kwargs):
        return []

    items = [item async for item in paginate_after(fetch_page)]

    assert items == []


@pytest.mark.asyncio
async def test_paginate_after_stops_when_last_item_has_no_id():
    async def fetch_page(*, page_size: int, after=None, **kwargs):
        assert after is None
        return [{"name": "a"}]

    items = [item async for item in paginate_after(fetch_page, page_size=1)]

    assert items == [{"name": "a"}]


@pytest.mark.asyncio
async def test_paginate_cursor_multiple_pages():
    pages = {
        None: {
            "results": [{"id": 1}],
            "cursor": {"name": "page2", "count": 1},
        },
        "page2": {
            "results": [{"id": 2}],
            "cursor": {"name": "page3", "count": 1},
        },
        "page3": {
            "results": [{"id": 3}],
            "cursor": {},
        },
    }

    async def fetch_page(*, page_size: int, cursor=None, **kwargs):
        return pages[cursor]

    items = [item async for item in paginate_cursor(fetch_page, page_size=1)]

    assert items == [{"id": 1}, {"id": 2}, {"id": 3}]


@pytest.mark.asyncio
async def test_paginate_cursor_empty_results():
    async def fetch_page(*, page_size: int, cursor=None, **kwargs):
        return {"results": [], "cursor": {"name": "next", "count": 0}}

    items = [item async for item in paginate_cursor(fetch_page)]

    assert items == []


@pytest.mark.asyncio
async def test_paginate_cursor_non_dict_response():
    async def fetch_page(*, page_size: int, cursor=None, **kwargs):
        return ["not", "a", "dict"]

    items = [item async for item in paginate_cursor(fetch_page)]

    assert items == []


@pytest.mark.asyncio
async def test_paginate_cursor_missing_cursor_name():
    async def fetch_page(*, page_size: int, cursor=None, **kwargs):
        return {
            "results": [{"id": 1}],
            "cursor": {"count": 1},
        }

    items = [item async for item in paginate_cursor(fetch_page, page_size=10)]

    assert items == [{"id": 1}]


@pytest.mark.asyncio
async def test_paginate_cursor_partial_page_logs_last_page():
    calls = 0

    async def fetch_page(*, page_size: int, cursor=None, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "results": [{"id": 1}],
                "cursor": {"name": "next", "count": 1},
            }
        return {"results": [], "cursor": {}}

    items = [item async for item in paginate_cursor(fetch_page, page_size=10)]

    assert items == [{"id": 1}]
    assert calls == 2


@pytest.mark.asyncio
async def test_collect_all():
    async def gen():
        for value in (1, 2, 3):
            yield value

    assert await collect_all(gen()) == [1, 2, 3]


@pytest.mark.asyncio
async def test_map_concurrent_respects_limit():
    active = 0
    peak = 0

    async def work(item: int) -> int:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return item * 2

    results = await map_concurrent(list(range(6)), work, max_concurrency=2)

    assert sorted(results) == [0, 2, 4, 6, 8, 10]
    assert peak <= 2
