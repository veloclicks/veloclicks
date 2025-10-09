#!/bin/bash

# Function to wait for the Flask app to be ready
wait_for_flask() {
  echo "Celery : Waiting for the Flask app to be ready..."
  while ! curl -s -f http://127.0.0.1:5002/health > /dev/null; do
    echo "Celery : Flask app is not ready yet. Retrying in 2 seconds..."
    sleep 3
  done
  echo "Celery : Flask app is ready!"
}

# Call the wait function
wait_for_flask

# Start the Celery worker
echo "Celery: Starting the Celery worker..."
exec celery -A app.make_celery worker --loglevel=info



