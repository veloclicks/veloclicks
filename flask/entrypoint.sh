#!/bin/bash
set -e

echo "Waiting for PostgreSQL............."
while ! nc -z ${POSTGRES_HOST} ${POSTGRES_PORT}; do
    sleep 0.1
done
echo "PostgreSQL started"

if [ ! -d "migrations" ]; then
    echo "\nInitializing database...............\n"
    flask db init
    flask db migrate -m "Initial migration"
fi

echo "Applying database migrations..........."
flask db upgrade

echo "Starting Flask application............."
flask run --host=0.0.0.0
