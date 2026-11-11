from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from .config import settings
from .schemas import JobRecord, JobStatus


class JobStore:
    """Redis holds both durable job metadata and the queue entries."""

    def __init__(self, redis: Redis):
        self.redis = redis

    @staticmethod
    def key(job_id: str) -> str:
        return f"ia-entrega-7:job:{job_id}"

    async def create(self, record: JobRecord) -> None:
        await self.redis.set(self.key(record.job_id), record.model_dump_json())

    async def get(self, job_id: str) -> JobRecord | None:
        raw = await self.redis.get(self.key(job_id))
        return JobRecord.model_validate_json(raw) if raw else None

    async def update(self, job_id: str, **changes: Any) -> JobRecord:
        record = await self.get(job_id)
        if record is None:
            raise KeyError(job_id)
        changes["updated_at"] = datetime.now(UTC)
        updated = record.model_copy(update=changes)
        await self.redis.set(self.key(job_id), updated.model_dump_json())
        return updated

    async def enqueue(self, job_id: str, mode: str = "start") -> None:
        await self.redis.rpush(settings.queue_key, json.dumps({"job_id": job_id, "mode": mode}))

    async def dequeue(self, timeout: int = 1) -> dict[str, str] | None:
        item = await self.redis.blpop(settings.queue_key, timeout=timeout)
        return json.loads(item[1]) if item else None
