"""Select the coaching adapter for the current Flask deployment."""

import json
import os

from app.shared_coach.service import coaching_result


def get_coaching(llm_payload: dict, detail_level: str) -> dict:
    """Run coaching locally or invoke the existing production Coach Lambda."""
    if os.getenv("LOCAL_DOMAIN_SERVICES") == "1":
        return coaching_result(llm_payload, detail_level)

    import boto3

    response = boto3.client("lambda", region_name="eu-west-2").invoke(
        FunctionName=os.getenv("COACH_LAMBDA_NAME", "veloclicks-coach"),
        Payload=json.dumps({"llm_payload": llm_payload, "detail_level": detail_level}),
    )
    with response["Payload"] as payload:
        return json.load(payload)
