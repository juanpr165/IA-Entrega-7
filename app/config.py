from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    queue_key: str = os.getenv("JOB_QUEUE_KEY", "ia-entrega-7:queue")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    max_iterations: int = int(os.getenv("MAX_ITERATIONS", "6"))


settings = Settings()
