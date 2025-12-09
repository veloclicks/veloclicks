#!/usr/bin/env python3
"""
Test script to check which Anthropic models are available with your API key.
"""
import anthropic
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

api_key = os.getenv('ANTHROPIC_API_KEY')
if not api_key:
    print("ERROR: ANTHROPIC_API_KEY not found in environment")
    exit(1)

print(f"Testing API key: {api_key[:20]}...")
print()

# List of models to test
models_to_test = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-20240620",
    "claude-3-sonnet-20240229",
    "claude-3-opus-20240229",
    "claude-3-haiku-20240307",
]

client = anthropic.Anthropic(api_key=api_key)

for model in models_to_test:
    try:
        print(f"Testing {model}... ", end="", flush=True)
        response = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print(f"✓ WORKS (response: {response.content[0].text})")
    except anthropic.NotFoundError as e:
        print(f"✗ NOT FOUND")
    except Exception as e:
        print(f"✗ ERROR: {str(e)}")

print()
print("Test complete!")
