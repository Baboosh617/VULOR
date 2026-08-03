#!/bin/sh
set -e

python manage.py migrate --noinput

exec gunicorn vulor.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --timeout 120 \
    --worker-class gthread \
    --threads 2 \
    --workers 1
