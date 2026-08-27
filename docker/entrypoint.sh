#!/bin/sh
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

if [ "${SEED_DEMO:-true}" = "true" ]; then
  echo "Seeding demo data..."
  python manage.py seed_demo
fi

echo "Starting gunicorn..."
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-60}"
