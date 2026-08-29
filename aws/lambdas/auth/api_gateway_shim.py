"""
Local development HTTP server for the auth lambda.

WHY THIS EXISTS:
  In production, the auth lambda sits behind AWS API Gateway, which translates
  incoming HTTP requests into Lambda event dicts and passes them to lambda_handler().
  Locally (Docker Compose), we use the Lambda RIC base image which only speaks
  the Lambda invocation protocol — it cannot accept plain HTTP from the browser.
  This script replaces the Lambda RIC entrypoint for local dev only. It acts as
  a minimal stand-in for API Gateway: it receives plain HTTP, builds a Lambda
  event dict, calls lambda_handler(), and sends the response back as HTTP.

  The Dockerfile CMD is set to run this script. For AWS deployment, SAM packages
  the Python source as a ZIP and ignores the Dockerfile entirely, so this file
  has no effect in production.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from lambda_function import lambda_handler


class APIGatewayShim(BaseHTTPRequestHandler):

    def _invoke(self, method):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8") if length else ""

        # Build a minimal API Gateway v1 proxy event so lambda_handler() sees the
        # same shape it receives in production.
        event = {
            "httpMethod": method,
            "path": self.path,
            "headers": dict(self.headers),
            "body": raw_body,
            "requestContext": {
                "http": {"method": method}
            },
        }

        result = lambda_handler(event, None)

        self.send_response(result["statusCode"])
        for key, value in result.get("headers", {}).items():
            self.send_header(key, value)
        self.end_headers()
        response_body = result.get("body", "")
        self.wfile.write(response_body.encode("utf-8"))

    def do_POST(self):
        self._invoke("POST")

    def do_OPTIONS(self):
        self._invoke("OPTIONS")

    def log_message(self, format, *args):
        # Use standard print so output appears in `docker compose logs auth`
        print(f"[auth-local] {self.address_string()} {format % args}")


if __name__ == "__main__":
    port = 8080
    print(f"[auth-local] Starting local API Gateway shim on port {port}")
    HTTPServer(("0.0.0.0", port), APIGatewayShim).serve_forever()
