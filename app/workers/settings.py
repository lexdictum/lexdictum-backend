from arq.connections import RedisSettings

from app.config import get_settings
from app.workers.tasks.document_pipeline import process_document

_settings = get_settings()


class WorkerSettings:
    functions = [process_document]
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    max_tries = _settings.arq_max_tries
    job_timeout = 600
