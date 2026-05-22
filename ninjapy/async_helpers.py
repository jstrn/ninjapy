"""Async pagination and concurrency helpers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger("ninjapy.helpers")

T = TypeVar("T")


async def paginate_after(
    method_func: Callable[..., Awaitable[list[dict[str, Any]]]],
    *,
    page_size: int = 100,
    **kwargs: Any,
) -> AsyncIterator[dict[str, Any]]:
    """Paginate endpoints that use the ``after`` parameter."""
    after = None

    while True:
        logger.info("Fetching page with page_size=%s, after=%s", page_size, after)
        page_results = await method_func(page_size=page_size, after=after, **kwargs)

        if not page_results:
            break

        for item in page_results:
            yield item

        if len(page_results) < page_size:
            break

        after = page_results[-1].get("id")
        if after is None:
            logger.warning(
                "No 'id' field found in last item, pagination may not work correctly"
            )
            break


async def paginate_cursor(
    method_func: Callable[..., Awaitable[dict[str, Any]]],
    *,
    page_size: int = 100,
    **kwargs: Any,
) -> AsyncIterator[dict[str, Any]]:
    """Paginate endpoints that return ``{results, cursor}`` envelopes."""
    cursor = None

    while True:
        logger.info("Fetching page with page_size=%s, cursor=%s", page_size, cursor)
        response = await method_func(page_size=page_size, cursor=cursor, **kwargs)

        if not isinstance(response, dict):
            logger.error("Expected dict response for cursor-based pagination")
            break

        results = response.get("results", [])
        if not results:
            break

        for item in results:
            yield item

        cursor_info = response.get("cursor", {})
        if not cursor_info:
            break

        cursor = cursor_info.get("name")
        if not cursor:
            break

        count = cursor_info.get("count", 0)
        if count < page_size:
            logger.info(
                "Received %s items, less than page_size %s, likely last page",
                count,
                page_size,
            )


async def collect_all(async_iterator: AsyncIterator[T]) -> list[T]:
    """Collect all items from an async iterator into a list."""
    return [item async for item in async_iterator]


async def map_concurrent(
    items: list[T],
    func: Callable[[T], Awaitable[Any]],
    *,
    max_concurrency: int = 10,
) -> list[Any]:
    """Run an async function over items with bounded concurrency."""
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _run(item: T) -> Any:
        async with semaphore:
            return await func(item)

    return await asyncio.gather(*(_run(item) for item in items))
