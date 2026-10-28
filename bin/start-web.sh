#!/bin/sh
set -eu

case "${WEB_MIGRATE_ON_STARTUP:-false}" in
    1|true|True|TRUE) python manage.py migrate --noinput ;;
esac

python manage.py migrate --check --noinput

exec gunicorn InspectGovRR.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --access-logfile - \
    --error-logfile -
