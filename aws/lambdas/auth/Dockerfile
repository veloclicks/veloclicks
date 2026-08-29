FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY handler.py .
COPY auth_service.py .
COPY db.py .
COPY local_server.py .

# WHY ENTRYPOINT instead of CMD:
# The Lambda base image defines its own ENTRYPOINT (the Lambda RIC bootstrap)
# which intercepts CMD and expects a handler name as its first argument.
# Using ENTRYPOINT here overrides the base image's entrypoint entirely, so
# local_server.py starts directly instead of the Lambda RIC.
# For AWS deployment, SAM packages source as a ZIP and never reads this
# Dockerfile, so this change has no effect in production.
ENTRYPOINT ["python", "local_server.py"]
