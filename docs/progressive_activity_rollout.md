# Progressive activity loading rollout

This runbook is for the owner-controlled rollout from main. The implementation can be built and exercised locally. A source push can trigger Vercel, so publish the production host activation only after the migration, APIs and snapshot seed have been verified.

## Execution and data safety

- PostgreSQL holds one durable import slot per user. Login, manual sync, OAuth and historical entry points enqueue through the same owner lock. Workers use `FOR UPDATE SKIP LOCKED` to avoid a second worker fetching that owner’s page. Each step commits the inserted rows and cursor together. A terminated Lambda releases its lock and the next invocation resumes from the last committed page.
- `sync_history` tracks half-open UTC windows. The final page records and consolidates coverage, including successful empty windows. Automatic sync fetches the last 30 days. Manual sync uses the new, successful recent watermark with a calendar-year cap. Its first run uses 30 days. Historical work does not move this watermark. The legacy timestamp and existing rides do not initialise coverage.
- The worker considers newest gaps first within entitlement. Historical windows span at most 365 days and a step makes one bounded Strava page request, with a token-refresh attempt when needed. Premium backfill works back to Unix epoch, with the lower parameter omitted at that boundary. Strava documents the filters as epoch timestamps. The worker compensates for exclusive `after` and checks the half-open window again before persistence. [Strava activity list API](https://developers.strava.com/docs/reference/#api-Activities-getLoggedInAthleteActivities)
- Strava 429 responses honour a numeric `Retry-After` or wait 15 minutes. Other transient failures use bounded backoff. A job enters a terminal failure state after four unsuccessful attempts, and manual Sync can requeue it. Rejected refresh credentials block automatic work until a successful OAuth reconnect.
- PostgreSQL triggers invalidate snapshot work in the same transaction as activity or tier changes. A separate advisory lock serializes publication for an owner without holding the dirty row during object I/O. The worker compares digests, publishes only changed or damaged objects, and leaves a newer dirty generation pending if data changed during publication. Basic expiry is checked on read and reevaluated by the worker. No older rides are deleted.
- Snapshots use a Docker volume locally and a private, encrypted S3 bucket in AWS. The Activities Lambda only reads its dedicated object prefix. The Zappa publisher role can read and replace objects in that prefix. The verified Veloclicks JWT selects the owner. A snapshot containing rows outside the Basic window requires a live tier check before those rows can be returned. A normal recent-only hit loads no SQLAlchemy or PostgreSQL driver. Access tokens still use the existing signing and expiry model. Strava revocation is handled separately and does not revoke a Veloclicks JWT.
- The browser downloads the snapshot and stored pages independently of the sync job. A persisted revision makes the browser reconcile its stored pages immediately. It does not wait for snapshot publication. A status poll repairs lost browser notifications, and same-origin tabs receive a notification when sync is queued. The database lock is authoritative across tabs and domains.
- The AWS worker is an EventBridge schedule on the existing Zappa stack with a bounded step count and a soft time budget. Docker uses the same worker in a dedicated container. No browser tab is required for work to continue. Monitor queue age, retry and reconnect states, activity-worker log errors, S3 errors, and the existing Activities API latency logs. The new logging never includes tokens or secret values. Set Zappa debug off so the framework does not log raw bearer headers.

## Local check

From the repo root:

```bash
docker compose up -d --build --wait
docker compose exec -T flask flask db current --directory app/migrations
docker compose exec -T flask flask seed-activity-snapshot USER_ID
docker compose logs --tail 80 activities-worker
```

Local Compose enables the frontend flag. Its worker shares the Flask snapshot volume and runs without SAM emulation. Use an existing local user ID for seeding.

## Production release procedure

Use the established AWS identities and compare the observed stack, function role and API URL with the currently deployed application. The production Flask stage is named `dev`.

```bash
aws sts get-caller-identity --profile vc_admin --region eu-west-2
aws sts get-caller-identity --profile zappa-deployer --region eu-west-2
aws cloudformation describe-stacks --profile vc_admin --region eu-west-2 \
  --stack-name veloclicks-activities-prod \
  --query 'Stacks[0].{Status:StackStatus,Outputs:Outputs,Parameters:Parameters[*].ParameterKey}'
aws lambda get-function-configuration --profile vc_admin --region eu-west-2 \
  --function-name veloclicks-dev --query '{Role:Role,Runtime:Runtime,Timeout:Timeout}'
```

1. Back up the database according to the owner’s existing policy. Run the migration from the repo root. The command uses the SSM value in a subprocess environment without printing it.

   ```bash
   (
     db_url=$(aws ssm get-parameter --profile vc_admin --region eu-west-2 \
       --name /veloclicks/dev/database-url --with-decryption \
       --query Parameter.Value --output text) &&
     DATABASE_URL="$db_url" LOG_LEVEL=INFO PYTHONPATH=flask \
       flask/.venv/bin/flask --app app:application db upgrade \
       --directory flask/app/migrations e1322af018c9
   )
   ```

2. Package the Activities stack and preview an update. The CORS setting and signing and database parameters must already exist on the stack. Pass `UsePreviousValue=true` as a CloudFormation parameter field.

   ```bash
   (
     cd aws/lambdas &&
     sam validate --lint --template-file template.activities-prototype.yaml --region eu-west-2 &&
     sam build --template-file template.activities-prototype.yaml &&
     sam package --template-file .aws-sam/build/template.yaml \
       --s3-bucket veloclicks-zappa-deployments-eu-west-2 --s3-prefix sam-activities \
       --output-template-file /tmp/veloclicks-activities-packaged.yaml \
       --profile vc_admin --region eu-west-2
   )
   zappa_role=$(aws lambda get-function-configuration --profile vc_admin --region eu-west-2 \
     --function-name veloclicks-dev --query Role --output text)
   change_id=$(aws cloudformation create-change-set --profile vc_admin --region eu-west-2 \
     --stack-name veloclicks-activities-prod --change-set-name "progressive-activities-$(date +%s)" \
     --change-set-type UPDATE --capabilities CAPABILITY_IAM \
     --template-body file:///tmp/veloclicks-activities-packaged.yaml \
     --parameters ParameterKey=DatabaseUrl,UsePreviousValue=true \
                  ParameterKey=SecretKey,UsePreviousValue=true \
                  ParameterKey=CorsOrigin,UsePreviousValue=true \
                  "ParameterKey=SnapshotWriterRoleArn,ParameterValue=$zappa_role" \
     --query Id --output text)
   aws cloudformation wait change-set-create-complete --profile vc_admin --region eu-west-2 \
     --change-set-name "$change_id"
   aws cloudformation describe-change-set --profile vc_admin --region eu-west-2 \
     --change-set-name "$change_id" --query Changes
   ```

   Review the private bucket, narrow access policy, and additions to the existing API. Keep the current REST API and function. Execute only the reviewed change set.

   ```bash
   aws cloudformation execute-change-set --profile vc_admin --region eu-west-2 --change-set-name "$change_id"
   aws cloudformation wait stack-update-complete --profile vc_admin --region eu-west-2 \
     --stack-name veloclicks-activities-prod
   snapshot_bucket=$(aws cloudformation describe-stacks --profile vc_admin --region eu-west-2 \
     --stack-name veloclicks-activities-prod \
     --query "Stacks[0].Outputs[?OutputKey=='ActivitySnapshotBucket'].OutputValue | [0]" --output text)
   ```

3. Merge the worker schedule and bucket into the existing private Zappa settings. Retain the existing keys, role, SSM values and layers. Export the stack output from the preceding step and run this from the repo root.

   ```bash
   export ACTIVITY_SNAPSHOT_BUCKET="$snapshot_bucket"
   python3 - <<'PY'
   import json
   import os
   from pathlib import Path

   bucket = os.environ["ACTIVITY_SNAPSHOT_BUCKET"]
   assert bucket and bucket != "None"
   path = Path("zappa/zappa_settings.json")
   settings = json.loads(path.read_text())
   dev = settings["dev"]
   dev["debug"] = False
   dev.setdefault("environment_variables", {}).update(
       ACTIVITY_SNAPSHOT_BUCKET=bucket, LOG_LEVEL="INFO"
   )
   function = "app.strava.worker.tick"
   events = [event for event in dev.get("events", []) if event.get("function") != function]
   dev["events"] = [*events, {"function": function, "expression": "rate(1 minute)"}]
   path.write_text(json.dumps(settings, indent=2) + "\n")
   PY
   (cd zappa && source .venv/bin/activate && AWS_PROFILE=zappa-deployer zappa update dev)
   curl -fsS https://ztbap26rs2.execute-api.eu-west-2.amazonaws.com/dev/health
   ```

4. Before enabling the frontend, seed the chosen existing account. Set `activity_seed_user_id` to the verified Veloclicks user ID. This operation can be repeated. It neither calls Strava nor infers coverage.

   ```bash
   (
     db_url=$(aws ssm get-parameter --profile vc_admin --region eu-west-2 \
       --name /veloclicks/dev/database-url --with-decryption --query Parameter.Value --output text) &&
     AWS_PROFILE=vc_admin AWS_DEFAULT_REGION=eu-west-2 DATABASE_URL="$db_url" LOG_LEVEL=INFO PYTHONPATH=flask \
       flask/.venv/bin/flask --app app:application seed-activity-snapshot "${activity_seed_user_id:?Set the verified user ID}"
   )
   ```

5. Verify API contracts using the Git-ignored smoke account file. This prints status codes only and does not start an import.

   ```bash
   aws s3api get-public-access-block --profile vc_admin --region eu-west-2 --bucket "$snapshot_bucket"
   python3 - <<'PY'
   import json
   from pathlib import Path
   from urllib.error import HTTPError
   from urllib.request import Request, urlopen

   settings = json.loads(Path(".smoke-account.json").read_text())
   account = settings["users"][0] if "users" in settings else settings
   auth = "https://hbd117p6u7.execute-api.eu-west-2.amazonaws.com/Prod"
   flask = "https://ztbap26rs2.execute-api.eu-west-2.amazonaws.com/dev"
   activities = "https://1m4c74owqj.execute-api.eu-west-2.amazonaws.com/Prod"
   payload = json.dumps({key: account[key] for key in ("username", "password")}).encode()
   with urlopen(Request(auth + "/api/login", data=payload,
                        headers={"Content-Type": "application/json"}), timeout=35) as response:
       token = json.load(response)["token"]
   headers = {"Authorization": "Bearer " + token, "Origin": "https://www.veloclicks.com"}
   for label, url, keys in (
       ("Snapshot", activities + "/strava/activities/snapshot", {"activities"}),
       ("Paginated list", activities + "/strava/activities/?limit=50", {"activities", "next_cursor"}),
       ("Sync status", flask + "/strava/sync/status", {"status", "revision", "reconnect"}),
       ("OAuth URL", flask + "/strava/oauth-url", {"url"}),
   ):
       with urlopen(Request(url, headers=headers), timeout=35) as response:
           assert keys <= json.load(response).keys()
           print(label, response.status)
   try:
       urlopen(activities + "/strava/activities/snapshot", timeout=35)
   except HTTPError as error:
       assert error.code == 401
       print("Anonymous snapshot", error.code)
   else:
       raise AssertionError("Anonymous snapshot unexpectedly succeeded")
   PY
   ```

   Inspect only sanitized worker and Gateway logs. Run the seed for the smoke account as well if it uses a different user ID.
6. Push the frontend activation through the normal Git/Vercel workflow. The verified production hostnames enable the flow by default. An explicit `NEXT_PUBLIC_PROGRESSIVE_ACTIVITY_SYNC=0` overrides this default. The updated reconnect page uses Flask’s authenticated OAuth URL endpoint, so Flask must be live before the frontend build is published. Check initial rows, sync state and subsequent rows on both `www.veloclicks.com` and the Vercel alias. Test reconnect, continued background work after closing the browser, and first-page cold and warm timings. Visualizations and AI Insights should still receive the Flask array contract.

## Rollback

Set `NEXT_PUBLIC_PROGRESSIVE_ACTIVITY_SYNC=0` and redeploy, or revert the production host activation commit and push. Both disable automatic sync and snapshot fetching while keeping the signed OAuth flow. Keep the new migration and the private bucket. Existing queued work can finish. To halt background work, identify the exact `app.strava.worker.tick` EventBridge rule from Zappa status, then disable only that rule:

```bash
aws events disable-rule --profile vc_admin --region eu-west-2 \
  --name "${activity_worker_rule:?Set the verified activity worker rule name}"
```

For a full backend rollback, restore the previously retained Lambda packages and the matching Zappa slim archive, including the prior frontend if needed. Leave the additive migration in place until the owner decides whether to discard queue state. Old clients that use unsigned OAuth state cannot reconnect against the new backend. Roll back the two together if restoring that older client. The database downgrade is a local verification step and removes sync and snapshot work records.
