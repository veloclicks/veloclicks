#!/bin/bash
set -e

echo "$(date '+%d %b %Y %H:%M:%S') ----- entrypoint.sh >> Starting...."

while ! nc -z ${POSTGRES_HOST} ${POSTGRES_PORT}; do
    sleep 0.1
done
echo "$(date '+%d %b %Y %H:%M:%S') ----- entrypoint.sh >> PostgreSQL started"

echo "$(date '+%d %b %Y %H:%M:%S') ----- entrypoint.sh >> Applying any database migrations..........."
flask db upgrade --directory app/migrations

echo "$(date '+%d %b %Y %H:%M:%S') ----- entrypoint.sh >> Starting Flask application............."
exec flask run --host=0.0.0.0 --port=5000
