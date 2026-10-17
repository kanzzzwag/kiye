from concurrent.futures import ThreadPoolExecutor

from .config import settings
from .tasks import run_job

_pool = ThreadPoolExecutor(max_workers=1) if settings.queue_mode == "thread" else None


def enqueue(job_id: str):
    if _pool:
        _pool.submit(run_job, job_id)
        return
    from redis import Redis
    from rq import Queue

    Queue("analyze", connection=Redis.from_url(settings.redis_url)).enqueue(
        run_job, job_id, job_timeout=settings.job_timeout_sec
    )
