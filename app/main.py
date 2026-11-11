from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, status
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from redis.asyncio import Redis

from .config import settings
from .graph import build_graph
from .hitl import is_critical_task
from .schemas import ApprovalRequest, JobRecord, JobStatus, TaskAccepted, TaskCreate
from .store import JobStore
from .worker import RedisWorker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    await redis.ping()
    saver_context = AsyncRedisSaver.from_conn_string(settings.redis_url)
    saver = await saver_context.__aenter__()
    await saver.asetup()
    app.state.store = JobStore(redis)
    app.state.worker = RedisWorker(app.state.store, build_graph(saver))
    app.state.worker.start()
    try:
        yield
    finally:
        await app.state.worker.stop()
        await saver_context.__aexit__(None, None, None)
        await redis.aclose()


app = FastAPI(
    title="IA Entrega 7 — API multiagente",
    version="1.0.0",
    lifespan=lifespan,
)


def store_for(request: Request) -> JobStore:
    return request.app.state.store


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    await store_for(request).redis.ping()
    return {"status": "ok"}


@app.post("/tasks", response_model=TaskAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_task(payload: TaskCreate, request: Request) -> TaskAccepted:
    """Persist and queue quickly; the graph is never awaited by this endpoint."""
    now = datetime.now(UTC)
    job_id = str(uuid.uuid4())
    store = store_for(request)
    record = JobRecord(
        job_id=job_id,
        task=payload.task,
        status=JobStatus.PENDING,
        critical=is_critical_task(payload.task),
        created_at=now,
        updated_at=now,
    )
    await store.create(record)
    await store.enqueue(job_id)
    return TaskAccepted(job_id=job_id, status=JobStatus.PENDING)


@app.get("/tasks/{job_id}", response_model=JobRecord)
async def get_task(job_id: str, request: Request) -> JobRecord:
    job = await store_for(request).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job inexistente")
    return job


@app.post("/tasks/{job_id}/approve", response_model=JobRecord)
async def approve_task(job_id: str, payload: ApprovalRequest, request: Request) -> JobRecord:
    store = store_for(request)
    job = await store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job inexistente")
    if job.status != JobStatus.WAITING_APPROVAL:
        raise HTTPException(status_code=409, detail="El job no está esperando aprobación")
    updated = await store.update(job_id, reviewer_note=payload.reviewer_note, status=JobStatus.PENDING)
    await store.enqueue(job_id, mode="resume_approved" if payload.approved else "resume_rejected")
    return updated
