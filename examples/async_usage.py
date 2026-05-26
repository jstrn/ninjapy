#!/usr/bin/env python3
"""Example async usage of NinjaPy."""

import asyncio
import os

from ninjapy import AsyncNinjaRMMClient


async def main() -> None:
    async with AsyncNinjaRMMClient(
        token_url=os.environ["NINJA_TOKEN_URL"],
        client_id=os.environ["NINJA_CLIENT_ID"],
        client_secret=os.environ["NINJA_CLIENT_SECRET"],
        scope=os.environ.get("NINJA_SCOPE", "monitoring management control"),
        base_url=os.environ.get("NINJA_BASE_URL", "https://api.ninjarmm.com"),
    ) as client:
        orgs = await client.get_organizations(page_size=5)
        print(f"Found {len(orgs)} organizations on first page")

        count = 0
        async for org in client.iter_all_organizations(page_size=50):
            count += 1
            print(f"Org: {org.get('name')}")
            if count >= 5:
                break


if __name__ == "__main__":
    asyncio.run(main())
