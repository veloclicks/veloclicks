FROM python:3.11-slim

# This is the working directory relative to the CONTAINER filesystem
# The files copied in here come from the build context specificed in docker-compose
# This sets the working directory for all subsequent commands in Dockerfile
# It also becomes the default working directory when the container starts
WORKDIR /app/app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y netcat-traditional && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements.txt into container and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entrypoint.sh into container and install
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy application code from the current directory
COPY . .

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
