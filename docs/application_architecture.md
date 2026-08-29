# Application Architecture

Snapshot as of 2026-08-28. Reflects what's actually deployed, not aspirational config —
see notes under each diagram for known gaps between the two.

## Container diagram (C4, level 2)

```mermaid
graph TB
    Browser["Browser"]

    subgraph Vercel
        Frontend["Frontend<br/>Next.js<br/>veloclicks-prod.vercel.app"]
    end

    subgraph AWS["AWS (eu-west-2)"]
        Flask["Flask API<br/>Python / Flask<br/>Zappa → Lambda (veloclicks-dev)"]
        AuthLambda["Auth Lambda<br/>veloclicks-auth<br/>SAM → Lambda + API Gateway"]
        CoachLambda["Coach Lambda<br/>veloclicks-coach<br/>SAM → Lambda"]
        SSM["SSM Parameter Store<br/>secrets"]
    end

    Postgres[("Postgres<br/>(Neon, managed)")]
    Strava["Strava API"]
    Anthropic["Anthropic API<br/>Claude"]

    Browser --> Frontend
    Frontend -->|"REST — most routes"| Flask
    Frontend -->|"REST — login (register still on Flask)"| AuthLambda
    Flask -->|"boto3 invoke"| CoachLambda
    Flask --> Postgres
    Flask --> SSM
    Flask -->|"OAuth + REST"| Strava
    AuthLambda --> Postgres
    AuthLambda --> SSM
    CoachLambda -->|"Messages API"| Anthropic
    CoachLambda --> SSM
```

**Notes**
- Auth and Coach are deployed together under one CloudFormation stack (`veloclicks-lambdas`, from `lambdas/template.yaml`). Flask is deployed separately via Zappa, unrelated tooling.
- Only the frontend's **login** call was cut over to the Auth Lambda. **Register** still goes through Flask, even though the Auth Lambda also implements `/api/register` — see the Register sequence below.
- There is no "production" AWS environment — only `dev` exists (see [claude.md](../claude.md)). The Vercel frontend and Postgres DB are the only genuinely production-facing pieces today.

## Component diagram (C4, level 3)

### Flask API

```mermaid
graph TB
    subgraph Flask["Flask API (veloclicks-dev)"]
        AuthRoutes["auth blueprint<br/>/api/register, /api/login<br/>(login now redundant — see notes)"]
        StravaRoutes["strava blueprint<br/>OAuth connect, sync,<br/>activities, power metrics"]
        ProfileRoutes["profile blueprint<br/>/api/profile"]
        AICoachRoutes["ai_coach blueprint<br/>/ai-coach/activity/&lt;id&gt;"]
        AuthDecorator["require_auth<br/>JWT verify (shared SECRET_KEY)"]
        Analyser["activity_analyser +<br/>analytics engine<br/>(classifier, power, TSS, derivations)"]
        Models["SQLAlchemy models<br/>User, Activity, ActivityAnalytics,<br/>ActivityInsight, TrainingZone"]
    end

    StravaAPI["Strava API"]
    CoachLambda["Coach Lambda"]

    AuthRoutes --> Models
    ProfileRoutes --> AuthDecorator --> Models
    StravaRoutes --> AuthDecorator
    StravaRoutes --> Models
    StravaRoutes --> StravaAPI
    AICoachRoutes --> AuthDecorator
    AICoachRoutes --> Analyser --> Models
    AICoachRoutes -->|"boto3 invoke"| CoachLambda
    AICoachRoutes --> Models
```

### Auth Lambda & Coach Lambda

```mermaid
graph TB
    subgraph AuthLambda["Auth Lambda (veloclicks-auth)"]
        Handler["handler.py<br/>routes by path: login / register / refresh"]
        AuthService["auth_service.py<br/>password check, JWT issue"]
        AuthDB["db.py<br/>psycopg2 (DATABASE_URL)"]
    end

    subgraph CoachLambda["Coach Lambda (veloclicks-coach)"]
        LambdaFn["lambda_function.py<br/>build prompt, call Claude"]
        Prompts["coaching_prompts.py<br/>ACTIVITY_COACH_PROMPT"]
    end

    Postgres[("Postgres")]
    Anthropic["Anthropic API"]

    Handler --> AuthService --> AuthDB --> Postgres
    LambdaFn --> Prompts
    LambdaFn -->|"Anthropic SDK"| Anthropic
```

**Notes**
- `local_server.py` (Auth Lambda only, not shown) is a local-dev-only HTTP shim standing in for API Gateway when running under Docker Compose — see [lambdas/auth/local_server.py](../lambdas/auth/local_server.py). It has no effect on the deployed Lambda.
- Coach Lambda has no DB access — it's a pure prompt-in/text-out function; the analytics data is assembled entirely by Flask before invocation.

## Sequence: Login

```mermaid
sequenceDiagram
    participant B as Browser
    participant F as Frontend
    participant AL as Auth Lambda
    participant DB as Postgres

    B->>F: submit login form
    F->>AL: POST /api/login {username, password}
    AL->>DB: SELECT user by username
    DB-->>AL: user row (password hash)
    AL->>AL: verify password, sign JWT (SECRET_KEY)
    AL-->>F: 200 {token}
    F->>F: localStorage.setItem('authToken', token)
    F->>B: redirect to /activities
```

## Sequence: Register

```mermaid
sequenceDiagram
    participant B as Browser
    participant F as Frontend
    participant FL as Flask API
    participant DB as Postgres

    B->>F: submit register form
    F->>FL: POST /api/register {username, email, password, ...}
    FL->>DB: check username / email exists
    DB-->>FL: not found
    FL->>DB: INSERT new User (hashed password)
    DB-->>FL: user created
    FL-->>F: 201 {message: created}
    F->>B: redirect to /login
```

> Register still goes through Flask, not the Auth Lambda — only login was cut over so far, even though the Auth Lambda already implements `/api/register` too. Worth finishing the migration so there's one implementation, not two.

## Sequence: Activity Sync (Strava connect)

```mermaid
sequenceDiagram
    participant B as Browser
    participant F as Frontend
    participant S as Strava
    participant FL as Flask API
    participant DB as Postgres

    B->>F: click "Connect Strava"
    F->>B: redirect to Strava OAuth authorize URL
    B->>S: authorize app
    S->>FL: redirect w/ code, state → GET /strava/strava_auth/
    FL->>S: exchange code for access/refresh tokens
    S-->>FL: tokens
    FL->>DB: save Strava tokens on User
    FL->>S: fetch activities (last 30 days)
    S-->>FL: activity list
    FL->>DB: upsert Activity rows, set last_synch_epoch
    FL-->>B: redirect to /activities?strava_connected=true&activities=N
```

> A lighter incremental sync (`GET /strava/synch/`, using `last_synch_epoch` as the window start) exists for re-syncing after the initial connect, using the same `sync_activities` path.

## Sequence: Coach (AI Insights)

```mermaid
sequenceDiagram
    participant B as Browser
    participant F as Frontend
    participant FL as Flask API
    participant AN as Analytics engine
    participant CL as Coach Lambda
    participant AI as Anthropic API
    participant DB as Postgres

    B->>F: click "View AI Insights"
    F->>FL: GET /ai-coach/activity/:id
    FL->>DB: check cached ActivityInsight
    alt cached
        DB-->>FL: existing insight
        FL-->>F: 200 {coaching}
    else not cached
        FL->>AN: analyse_activity(mode='llm')
        AN->>DB: read Activity + streams
        AN-->>FL: llm_payload (power curve, zones, classification)
        FL->>CL: boto3 invoke {llm_payload, detail_level}
        CL->>AI: messages.create(model=claude-sonnet-5, prompt)
        AI-->>CL: coaching text
        CL-->>FL: {success, coaching, token_usage}
        FL->>DB: INSERT ActivityInsight
        FL-->>F: 200 {coaching}
    end
    F-->>B: render insight
```
