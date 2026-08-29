# Cheat Sheet

## Local

### Start Flask + Postgres (Docker Compose)

```
cd ~/dev/veloclicks
open -a docker                    # starts Docker Desktop if not already running

docker compose up --build         # build + start
docker compose up                 # start (no rebuild)
docker compose up -d              # start in background
docker compose restart flask      # restart one service (db, flask, lambdas, auth)
docker compose down               # stop everything
```

### Start the frontend

The frontend is not in Docker Compose — run it separately.

```
cd ~/dev/veloclicks/frontend
npm run dev
```

### Local URLs

- Frontend: http://localhost:3000/login
- Flask health: http://localhost:5002/health
- Flask user list: http://localhost:5002/listusers
- Coach Lambda (RIE): http://localhost:3001/2015-03-31/functions/function/invocations
- Auth Lambda: http://localhost:3002/api/login

### VS Code

```
code ~/dev/veloclicks
```

### Adding a new library (Flask)

1. `flask/.venv` — `pip install <package>`
2. Also add it to `flask/requirements.txt` (this is what the Docker build and Zappa both install from)
3. If it's a large/native dependency, it may need to go into a Lambda Layer instead (`aws/lambda_layers/`) rather than being bundled directly — Zappa's deploy package has a size limit

---

## Production (Remote)

There is no separate "production" AWS environment today — only `dev`. See [claude.md](../claude.md) for why.

### Deploy the Flask app (Zappa)

```
cd ~/dev/veloclicks/zappa
source .venv/bin/activate
export AWS_PROFILE=zappa-deployer

zappa update dev
zappa tail dev --since 1h
```

Health check: https://ztbap26rs2.execute-api.eu-west-2.amazonaws.com/dev/health

### Deploy the Auth + Coach Lambdas (SAM)

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

1. Push to git — Vercel deploys on push automatically
2. Check deployment status: https://vercel.com/veloclicks/~/deployments
3. Login goes directly to the Auth Lambda (bypasses Flask), so Vercel needs `NEXT_PUBLIC_AUTH_URL` set to the Auth API URL above. If the Lambda stack is ever redeployed fresh (not just updated), this URL changes and needs updating in Vercel's project settings.

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
