from datetime import UTC, datetime

from app.schemas import JobRecord, JobStatus


def test_job_record_serializes_to_redis_json() -> None:
    record = JobRecord(
        job_id="job-1", task="hola", status=JobStatus.PENDING, critical=False,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    restored = JobRecord.model_validate_json(record.model_dump_json())
    assert restored.job_id == "job-1"
    assert restored.status is JobStatus.PENDING
