from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from langgraph.types import Command

from .schemas import JobStatus
from .store import JobStore


class RedisWorker:
    """One async worker consuming Redis jobs; can be scaled into a separate process."""

    def __init__(self, store: JobStore, graph: Any):
        self.store = store
        self.graph = graph
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        self._task = asyncio.create_task(self.run(), name="redis-job-worker")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def run(self) -> None:
        while not self._stopping.is_set():
            item = await self.store.dequeue()
            if item:
                await self.process(item["job_id"], item["mode"])

    async def process(self, job_id: str, mode: str) -> None:
        job = await self.store.get(job_id)
        if job is None:
            return
        try:
            await self.store.update(job_id, status=JobStatus.RUNNING, error=None)
            config = {"configurable": {"thread_id": job_id}}
            input_value: Any = (
                {"user_request": job.task}
                if mode == "start"
                else Command(resume={"approved": mode == "resume_approved", "reviewer_note": job.reviewer_note})
            )
            result = await self.graph.ainvoke(input_value, config=config)
            if result.get("__interrupt__"):
                await self.store.update(job_id, status=JobStatus.WAITING_APPROVAL)
                return
            await self.store.update(
                job_id,
                status=JobStatus.DONE,
                result=result.get("final_answer", ""),
                routing_history=result.get("routing_history", []),
            )
        except Exception as exc:
            await self.store.update(job_id, status=JobStatus.FAILED, error=f"{type(exc).__name__}: {exc}")
