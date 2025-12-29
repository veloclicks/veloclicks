#!/bin/bash
set -e

echo "----- entrypoint.sh >> Waiting for PostgreSQL............."
while ! nc -z ${POSTGRES_HOST} ${POSTGRES_PORT}; do
    sleep 0.1
done
echo "----- entrypoint.sh >> PostgreSQL started"

# Ensure we're in the correct directory
cd /app/app

if [ ! -d "migrations" ]; then
    echo "----- entrypoint.sh >> Initializing database...............\n"
    flask db init --directory migrations
    flask db migrate --directory migrations -m "Initial migration"
fi

echo "----- entrypoint.sh >> Applying database migrations..........."
flask db upgrade --directory migrations

echo "----- entrypoint.sh >> Starting Flask application............."
flask run --host=0.0.0.0
