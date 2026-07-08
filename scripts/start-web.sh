#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn config.asgi:application \
	--worker-class uvicorn.workers.UvicornWorker \
	--bind 0.0.0.0:8000 \
	--workers "${GUNICORN_WORKERS:-2}" \
	--timeout "${GUNICORN_TIMEOUT:-0}" \
	--graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-30}" \
	--keep-alive "${GUNICORN_KEEPALIVE:-30}"
