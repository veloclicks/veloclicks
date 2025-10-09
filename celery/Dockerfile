FROM python:3.11-slim

RUN echo ">>>>>>>>> Celery Dockerfile"

# base directory within the container - not the local environment
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    bash \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies

RUN pwd
RUN ls /bin/bash && bash --version

COPY ./flask /app
COPY ./celery/entrypoint_celery.sh entrypoint_celery.sh

RUN ls -al .

RUN chmod +x /app/entrypoint_celery.sh

#COPY requirements.txt .
RUN pip install --no-cache-dir -r /app/requirements.txt


# Expose the application port
EXPOSE 6379

RUN ls -al

# Set entrypoint
#ENTRYPOINT ["/entrypoint_celery.sh"]

# Default entrypoint to keep the container flexible
# ENTRYPOINT ["/bin/bash"]