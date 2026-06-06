"""Gunicorn configuration for ServiceDesk."""

import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", f"0.0.0.0:{os.environ.get('PORT', '8000')}")
workers = int(os.environ.get("GUNICORN_WORKERS", str(min(4, multiprocessing.cpu_count() * 2 + 1))))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gthread")
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "5"))
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", "50"))
preload_app = os.environ.get("GUNICORN_PRELOAD", "true").lower() in ("true", "1", "yes")

accesslog = os.environ.get("GUNICORN_ACCESS_LOG", "-")
errorlog = os.environ.get("GUNICORN_ERROR_LOG", "-")
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'
)

proc_name = "servicedesk"
