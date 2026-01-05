#!/bin/bash
# Test Anthropic SDK in AWS Lambda via Zappa

cd "$(dirname "$0")/.." || exit 1

echo "Testing Anthropic SDK in AWS Lambda..."
echo ""

cd zappa || exit 1

# Read the Python script and invoke it in Lambda
zappa invoke dev "$(cat ../scripts/test_lambda_insights.py)" --raw
