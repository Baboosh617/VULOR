#!/bin/sh
set -e

# Railway (and plain Docker bind mounts) attach the media volume root-owned,
# so the non-root runtime user cannot create MEDIA_ROOT inside it — every
# product image and payment receipt upload died with EACCES on /data/media.
# The image therefore starts as root purely to create that directory and hand
# it to `vulor`, then re-execs this same script with privileges dropped. Every
# line below the guard runs unprivileged, exactly as before.
MEDIA_DIR="${MEDIA_ROOT:-/app/media}"
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$MEDIA_DIR"
    chown -R vulor:vulor "$MEDIA_DIR"
    exec setpriv --reuid=vulor --regid=vulor --init-groups "$0" "$@"
fi

python manage.py migrate --noinput

exec gunicorn vulor.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --timeout 120 \
    --worker-class gthread \
    --threads 2 \
    --workers 1
