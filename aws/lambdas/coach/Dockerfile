FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY lambda_function.py .
COPY coach_service.py .
COPY coaching_prompts.py .

CMD ["lambda_function.lambda_handler"]
