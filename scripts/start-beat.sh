#!/bin/sh
set -eu

exec celery -A config beat --loglevel=INFO
