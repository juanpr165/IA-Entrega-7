"""Send exactly five concurrent task requests and print job ids for LangSmith filtering."""

from __future__ import annotations

import asyncio
import os

import httpx

BASE_URL = os.getenv("API_URL", "http://localhost:8000")


async def submit(client: httpx.AsyncClient, number: int) -> dict:
    response = await client.post("/tasks", json={"task": f"Calculá {number} * {number} y explicá brevemente el resultado."})
    response.raise_for_status()
    return response.json()


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        responses = await asyncio.gather(*(submit(client, number) for number in range(1, 6)))
    for response in responses:
        print(f"job_id={response['job_id']} status={response['status']}")


if __name__ == "__main__":
    asyncio.run(main())
