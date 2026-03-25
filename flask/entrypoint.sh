#!/bin/bash
set -e

echo "$(date '+%d %b %Y %H:%M:%S') ----- entrypoint.sh >> Starting...."

while ! nc -z ${POSTGRES_HOST} ${POSTGRES_PORT}; do
    sleep 0.1
done
echo "$(date '+%d %b %Y %H:%M:%S') ----- entrypoint.sh >> PostgreSQL started"

# Ensure we're in the correct directory
cd /app/app

if [ ! -d "migrations" ]; then
    echo "$(date '+%d %b %Y %H:%M:%S') ----- entrypoint.sh >> Initializing database..............."
    flask db init --directory migrations
    flask db migrate --directory migrations -m "Initial migration"
fi

echo "$(date '+%d %b %Y %H:%M:%S') ----- entrypoint.sh >> Applying any database migrations..........."
flask db upgrade --directory migrations

echo "$(date '+%d %b %Y %H:%M:%S') ----- entrypoint.sh >> Starting Flask application............."
flask run --host=0.0.0.0
