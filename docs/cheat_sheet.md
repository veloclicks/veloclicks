# Cheat Sheet

## Quick start: local — frontend, Flask and database

All local services run in Docker Compose: PostgreSQL (`db`), Flask (`flask`) and Next.js (`frontend`). Flask handles local auth and coaching in-process; **Zappa, SAM and Vercel are not needed locally**.

```bash
cd ~/dev/veloclicks
open -a Docker
docker compose up --build -d     # start all three components
docker compose ps                # check service status
docker compose logs -f flask     # Flask logs (Ctrl+C to stop viewing)
```

Open http://localhost:3000/login; check Flask at http://localhost:5002/health.

```bash
cd ~/dev/veloclicks
docker compose restart flask     # restart backend after source changes if needed
docker compose up --build -d     # rebuild after dependency/image changes
docker compose down              # stop everything; database volume is retained
```

## Quick start: production — Vercel, Zappa and Lambdas

Production components are already hosted remotely; **deployment updates them** rather than starting local processes. The live AWS Zappa stage is called `dev`.

**0. Merge tested changes to main and push:**

```bash
cd ~/dev/veloclicks
git checkout main
git pull origin main
git merge feature/coaching-feedback-v2  # omit if already merged
git push origin main
```

**1. Frontend (Vercel):** pushing `main` automatically deploys Next.js. Check https://vercel.com/veloclicks/~/deployments and https://veloclicks-prod.vercel.app.

**2. Flask API (Zappa):**

```bash
cd ~/dev/veloclicks/zappa
source .venv/bin/activate       # hidden directory; ls -la to show it
export AWS_PROFILE=zappa-deployer
zappa update dev
zappa tail dev --since 1h
```

**3. Auth and Coach Lambdas (SAM):** from `~/dev/veloclicks/aws/lambdas`, run `sam build` and the **full** `sam deploy` command documented in **Deploy the Auth + Coach Lambdas (SAM)** below. Both Lambdas share the `veloclicks-lambdas` CloudFormation stack. **Zappa does not deploy either standalone Lambda.**

For coaching changes involving frontend, Flask and Coach Lambda, deploy **all three**: Vercel automatically on push, then Zappa and SAM manually. For isolated changes, deploy only affected components.

---

## Local

Docker Compose starts PostgreSQL, Flask and Next.js. Flask serves authentication and
runs coaching in process.

### Start the application

Start Docker Desktop and create a root `.env` with `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_DB` and a local `SECRET_KEY`. Add
`ANTHROPIC_API_KEY` for live coaching and the existing Strava settings if you use
Strava OAuth. Compose connects Flask to its own PostgreSQL service and applies
the existing migrations during startup.

```bash
cd ~/dev/veloclicks
open -a Docker
docker compose up --build
docker compose up --build -d    # start in the background
docker compose restart flask
docker compose down
```

### Run Python scripts inside the Flask container

The Flask container is named `vc_flask`. Its working directory is `/app`, while the host's `flask/` directory is mounted at `/app`. For scripts stored in `flask/scripts/`, use the absolute path and set `PYTHONPATH=/app` so `from app import ...` works.

From the repository root on the host:

```bash
docker exec -e PYTHONPATH=/app vc_flask python /app/scripts/<script_name>.py
```

Export recent cycling streams for analytics regression testing (requires Docker Compose's Flask container running and working Strava access):

```bash
cd ~/dev/veloclicks
docker exec -e PYTHONPATH=/app vc_flask python /app/scripts/export_analytics_fixtures.py > analytics-fixtures.json
```

The output file is written on the **host**. Do not commit it: it contains personal ride data. Python errors appear in the terminal; if the script fails, the redirected JSON may be empty. For local development, prefer this documented `docker exec` pattern over guessing container working directories.

### Local URLs

- Frontend login: http://localhost:3000/login
- Flask health: http://localhost:5002/health
- Frontend auth API: `POST http://localhost:5002/auth/api/login`, `/auth/api/register` and `/auth/api/refresh`
- Profile: `GET http://localhost:5002/api/profile` with an access token
- Coaching: `GET http://localhost:5002/ai-coach/activity/<id>` with a premium account and an owned activity
- PostgreSQL from the host: `localhost:5432`

### VS Code

```
code ~/dev/veloclicks
```

### Adding a new library (Flask)

1. `flask/.venv` — `pip install <package>`
2. Also add it to `flask/requirements.txt` (this is what the Docker build and Zappa both install from)
3. If it's a large/native dependency, it may need to go into a Lambda Layer instead (`aws/lambda_layers/`) rather than being bundled directly — Zappa's deploy package has a size limit


### Resetting coaching insights locally

```bash
cd ~/dev/veloclicks
docker compose exec -T db sh -c \
  'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
DELETE FROM vc_activity_insight
WHERE insight_type = 'ACTIVITY_INSIGHT';
SQL
```

---

## Production (Remote)

**Deployment overview:** Pushing to GitHub automatically deploys the Next.js frontend through Vercel. It does **not** deploy Flask or the standalone Lambdas. Backend changes must be deployed separately: use Zappa for the core Flask API and AWS SAM for the Auth and Coach Lambdas. These are independent deployments; deploy only the component you changed.

| Component | Production deployment | Trigger |
| --- | --- | --- |
| Next.js frontend | Vercel | Automatic on Git push |
| Core Flask API | `zappa update dev` | Manual |
| Auth + Coach Lambdas | `sam build` then `sam deploy` | Manual, shared CloudFormation stack |


There is no separate "production" AWS environment today — only `dev`. See [claude.md](../claude.md) for why.

### Deploy the Flask app (Zappa)

Use this for changes to the existing Flask backend. The Zappa `dev` stage is the current remote environment; it is not a separate production stage.

```
cd ~/dev/veloclicks/zappa
source .venv/bin/activate
export AWS_PROFILE=zappa-deployer

zappa update dev
zappa tail dev --since 1h
```

Health check: https://ztbap26rs2.execute-api.eu-west-2.amazonaws.com/dev/health

### Deploy the Auth + Coach Lambdas (SAM)

Use this for changes to either standalone Lambda or their SAM configuration.

Both are deployed together under one CloudFormation stack (`veloclicks-lambdas`) from `aws/lambdas/template.yaml`. Their secrets (`DATABASE_URL`, `SECRET_KEY`, `ANTHROPIC_API_KEY`) are pulled fresh from SSM at deploy time and passed in as parameters — CloudFormation doesn't support secure SSM references directly on Lambda environment variables.

```
cd ~/dev/veloclicks/aws/lambdas
sam build

sam deploy \
  --stack-name veloclicks-lambdas \
  --region eu-west-2 \
  --s3-bucket veloclicks-zappa-deployments-eu-west-2 \
  --s3-prefix sam-lambdas \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    AnthropicApiKey=$(aws ssm get-parameter --region eu-west-2 --name /veloclicks/dev/anthropic-api-key --with-decryption --query Parameter.Value --output text) \
    DatabaseUrl=$(aws ssm get-parameter --region eu-west-2 --name /veloclicks/dev/database-url --with-decryption --query Parameter.Value --output text) \
    SecretKey=$(aws ssm get-parameter --region eu-west-2 --name /veloclicks/dev/secret-key --with-decryption --query Parameter.Value --output text)
```

Current live endpoints:
- Auth API: https://hbd117p6u7.execute-api.eu-west-2.amazonaws.com/Prod
- Coach Lambda: invoked internally by Flask via `boto3` — not exposed via API Gateway

Find the current URL again any time via:
```
aws cloudformation describe-stacks --stack-name veloclicks-lambdas --region eu-west-2 --query "Stacks[0].Outputs"
```

### Deploy the frontend (Vercel)

No manual Vercel deployment command is needed for the normal Git-based workflow.

1. Push to git — Vercel deploys on push automatically
2. Check deployment status: https://vercel.com/veloclicks/~/deployments
3. Login from the frontend uses the Auth Lambda endpoint, so Vercel needs `NEXT_PUBLIC_AUTH_URL` set to the Auth API URL above. In the AWS Console, find it under **API Gateway → Stages → Prod** (or use the CloudFormation output command above). If the Lambda stack is recreated rather than updated, check whether this URL has changed and update Vercel's project settings if necessary.
4. The legacy Flask login and registration URLs remain available. Both deployments use the shared auth service with their existing response and access-token formats.

---

## AWS CLI Profiles

Credentials: `~/.aws/credentials` — profiles are `default`, `vc_admin`, `zappa-deployer`.

```
aws sts get-caller-identity     # verify current identity (should be vc_admin by default)
aws configure list               # show which profile/region is active

export AWS_PROFILE=zappa-deployer   # switch profile
unset AWS_PROFILE                   # back to default
echo $AWS_PROFILE                   # check current
```

## Logs

```
# Flask (Zappa)
aws logs tail /aws/lambda/veloclicks-dev --follow --region eu-west-2 | grep -v "Zappa Event"

# Coach Lambda
aws logs tail /aws/lambda/veloclicks-coach --follow --region eu-west-2

# Auth Lambda
aws logs tail /aws/lambda/veloclicks-auth --follow --region eu-west-2
```

## Git

- Local directory: `~/dev/veloclicks`
- Repo: https://github.com/veloclicks/veloclicks.git
- Credentials (git account, personal access token) — keep these in a password manager / `gh auth login`, not in this file or any committed file.
