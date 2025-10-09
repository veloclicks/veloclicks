#!/bin/bash

echo "React frontend : Waiting for Flask backend............."
until curl -s -f http://127.0.0.1:5002/health > /dev/null 2>&1; do
  echo "React frontend : Flask is unavailable - sleeping"
  sleep 10
done
echo "React frontend : Flask is running....."
echo "React frontend : Starting React development server....."


