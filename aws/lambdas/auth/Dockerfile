FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY lambda_function.py .
COPY auth_service.py .
COPY db.py .
COPY api_gateway_shim.py .

# WHY ENTRYPOINT instead of CMD:
# The Lambda base image defines its own ENTRYPOINT (the Lambda RIC bootstrap)
# which intercepts CMD and expects a handler name as its first argument.
# Using ENTRYPOINT here overrides the base image's entrypoint entirely, so
# api_gateway_shim.py starts directly instead of the Lambda RIC.
# For AWS deployment, SAM packages source as a ZIP and never reads this
# Dockerfile, so this change has no effect in production.
ENTRYPOINT ["python", "api_gateway_shim.py"]
