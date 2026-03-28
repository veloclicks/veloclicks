# Veloclicks Coach — Conversational Coaching Feature

You are working on an existing cycling analytics app called Veloclicks. Read the files referenced below to confirm details before writing code, but the architectural patterns and conventions are documented here — follow them precisely.

---

## Existing Architectural Patterns

### Flask blueprints
Each feature module lives in `flask/app/<module>/` with `__init__.py` registering a blueprint and `routes.py` containing the API endpoints. Routes are thin — they handle JWT auth, delegate to helpers or Lambdas, persist results, and return JSON. No business logic lives in routes. Auth follows this exact pattern in every route:

```python
auth_header = request.headers.get('Authorization')
token = auth_header.split(' ')[1]
payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
user_id = payload['user_id']
```

### Lambda invocation from Flask
Lambdas are invoked via boto3, never exposed directly to the client. The client calls a Flask route, Flask invokes the Lambda, persists the result, returns JSON to the client. The Lambda client is constructed like this:

```python
def _get_lambda_client():
    endpoint_url = os.environ.get('COACH_LAMBDA_ENDPOINT')
    kwargs = dict(region_name='eu-west-2')
    if endpoint_url:
        kwargs['endpoint_url'] = endpoint_url
        kwargs['aws_access_key_id'] = 'local'
        kwargs['aws_secret_access_key'] = 'local'
    return boto3.client('lambda', **kwargs)
```

This allows local SAM invocation via `COACH_LAMBDA_ENDPOINT` and real AWS in production.

### Lambda structure
Every Lambda follows this pattern:

```python
def lambda_handler(event, context):
    try:
        # extract from event
        # call _call_llm()
        return {'success': True, ...}
    except Exception as e:
        logger.error(f"lambda_handler() failed: {e}")
        return {'success': False, 'error': str(e)}

def _call_llm(prompt, ...):
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    response = client.messages.create(
        model=os.environ.get('LLM_MODEL', 'claude-sonnet-4-6-20251101'),
        max_tokens=...,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}]
    )
    text = ''.join(block.text for block in response.content if block.type == 'text')
    token_usage = {
        'input_tokens': response.usage.input_tokens,
        'output_tokens': response.usage.output_tokens,
        'total_tokens': response.usage.input_tokens + response.usage.output_tokens
    }
    return text, token_usage
```

### Database models
- ORM is SQLAlchemy via Flask-SQLAlchemy, imported from `.db` which exports `db`
- Table names are `vc_` prefixed
- Integer PKs: `Column(Integer, primary_key=True, autoincrement=True)`
- User FKs: `Column(Integer, ForeignKey('vc_user.id', ondelete='CASCADE'), nullable=False)`
- Activity FKs: `Column(BigInteger, ForeignKey('vc_strava_activity.id', ondelete='CASCADE'), nullable=False)`
- Timestamps: `Column(DateTime, server_default=func.now(), nullable=False)`
- JSON is stored as `Text` — never use `db.JSON` — serialise/deserialise explicitly in route code
- Enums use Python `enum.Enum` with `Column(Enum(MyEnum))`

### Key existing models
- `vc_user` — has `id` (Integer PK), `ftp` (Integer), `max_heart_rate`, `resting_heart_rate`. FTP lives here — do not duplicate it on any new model.
- `vc_strava_activity` — has `id` (BigInteger PK), `user_id`, all activity metrics
- `vc_activity_insight` — has `id`, `activity_id`, `user_id`, `insight_type` (String), `coach_insight` (Text), `created_at`. The new coach feature must preserve this model and its existing route unchanged.
- `vc_training_zone` — has `user_id`, `type` (Enum: `power`/`heart_rate`), `name` (e.g. `'z2'`, `'sweet_spot'`), `min`, `max`. Training plan session zones must use these name conventions.

### Next.js frontend
Pages live in `frontend/src/app/<page>/page.jsx`. Read existing pages to understand the fetch and auth patterns before writing the coach page — do not introduce new auth logic or new dependencies. Tailwind is used for styling throughout.

### SAM template
New Lambdas must be added to `lambdas/template.yaml` following the existing Lambda definition structure. Read the file before adding entries.

---

## What We Are Building

A conversational AI coaching feature for sportive riders. The coach maintains a persistent relationship with the rider across three phases:

**Phase 1 — Onboarding:** A free-form chat where the coach interviews the rider to establish their target event (name, date, distance, altitude), weekly hours available, recent training history, and any limiters. If ftp and max hr are not already available they should be asked for or estimated if possible. If FTP is already known it will be in from `vc_user.ftp` and is passed into the Lambda. If the rider is training for a target event the coach will need to work out how many weeks away that is in order to strucutre the plan. The coach should also ask the user when they want to start the plan. The conversation continues until the coach has sufficient information, at which point it signals completion by appending `<<<PROFILE_COMPLETE: {...JSON...}>>>` to its response. The Lambda strips this marker, sets `onboarding_complete: true`, and returns the extracted profile separately from the clean reply.

**Phase 2 — Plan generation:** Triggered automatically when onboarding completes. A separate Lambda takes the rider profile and FTP and generates a structured periodised training plan as JSON — weekly blocks from today to the target event date, each with a label (Base, Build, Peak, Taper), weekly hours target, and sessions (day, type, duration_minutes, target_zone, notes). Zone names must follow `vc_training_zone` naming conventions.

**Phase 3 — Ongoing coaching (future, not in scope):** Each completed Strava activity is reviewed in context of the plan.

All interactions form a single persistent conversation thread per rider stored as `CoachMessage` records. The rider profile and training plan are stored as structured records for efficient context assembly — not reconstructed from raw message history each time.

---

## Task 1 — Database Models

Create `flask/app/models/coach.py` with three models following the conventions above exactly.

### `vc_rider_coach_profile` — one per user (unique on user_id)
- `id`, `user_id` (unique), `created_at`, `updated_at` (add `onupdate=func.now()`)
- `target_event_name` String(128) nullable
- `target_event_date` Date nullable
- `target_event_distance_km` Float nullable
- `target_event_altitude_m` Float nullable
- `plan_start_date` Date nullable
- `weekly_hours_available` Float nullable
- `coaching_style` String(32) default `'supportive'`
- `onboarding_complete` Boolean default False
- `raw_profile` Text nullable

### `vc_training_plan`
- `id`, `user_id`, `created_at`
- `plan_start_date` Date nullable
- `plan_end_date` Date nullable
- `plan_data` Text nullable
- `plan_summary` Text nullable
- `is_active` Boolean default True

### `vc_coach_message`
- `id`, `user_id`, `created_at`
- `role` String(16) — `'user'` or `'assistant'`
- `content` Text
- `message_type` String(32) — `'onboarding'`, `'plan_generation'`, `'post_ride_review'`, `'general'`
- `activity_id` BigInteger FK to `vc_strava_activity.id`, nullable
- `metadata` Text nullable

Create a Flask-Migrate migration. Register the models in `flask/app/__init__.py`.

---

## Task 2 — New Lambdas

Create two new Lambdas following the Lambda pattern documented above exactly.

### `lambdas/coach_onboarding/lambda_function.py`

Receives:
```json
{
  "conversation_history": [{"role": "user|assistant", "content": "..."}],
  "user_message": "...",
  "coaching_style": "supportive|no_nonsense",
  "rider_ftp": 250,
  "rider_max_hr": 185
}
```
`rider_ftp` and `rider_max_hr` are nullable — pass `null` if not yet known. The coach should acknowledge known values rather than asking for them, and gather missing ones during conversation.

Returns:
```json
{
  "success": true,
  "reply": "...",
  "onboarding_complete": false,
  "extracted_profile": null,
  "token_usage": {}
}
```

`extracted_profile` when present contains: `target_event_name`, `target_event_date`, `target_event_distance_km`, `target_event_altitude_m`, `plan_start_date`, `weekly_hours_available`, `ftp` (if gathered), `max_hr` (if gathered).

The system prompt establishes the coach as an expert cycling coach conducting an initial rider assessment. Tone adapts to `coaching_style` — supportive is warm and encouraging, no_nonsense is direct and brief. The coach gathers target event details (including altitude), weekly hours, training history, limiters, and desired plan start date through natural conversation. It acknowledges any known FTP and max HR rather than asking for them, and gathers missing values conversationally. It signals completion via the `<<<PROFILE_COMPLETE>>>` marker when it has sufficient information.

The multi-turn conversation is managed by passing the full `conversation_history` on each call — the Lambda constructs the Anthropic `messages` array from history plus the new user message, rather than embedding history in a single prompt string.

### `lambdas/coach_plan/lambda_function.py`

Receives:
```json
{
  "rider_profile": {},
  "rider_ftp": 250,
  "coaching_style": "supportive|no_nonsense"
}
```

Returns:
```json
{
  "success": true,
  "plan_data": {},
  "plan_summary": "...",
  "token_usage": {}
}
```

Prompt Claude to return only valid JSON with no preamble. Parse and validate before returning.

Add both Lambdas to `lambdas/template.yaml`.

---

## Task 3 — Flask Coach Blueprint

Create `flask/app/coach/__init__.py` and `flask/app/coach/routes.py` as a blueprint with `url_prefix='/coach'`, following the Flask blueprint pattern documented above.

### `GET /coach/status`
Returns: `onboarding_complete`, `has_active_plan`, `plan_summary`, `message_count`

### `POST /coach/message`
Body: `{"message": "...", "coaching_style": "supportive"}`

- Load full `CoachMessage` history for this user, ordered by `created_at`
- Load `User.ftp` and `User.max_heart_rate`
- Invoke `coach_onboarding` Lambda, passing `rider_ftp` and `rider_max_hr` (nullable)
- Persist user message and assistant reply as two `CoachMessage` records — `message_type='onboarding'` if onboarding not yet complete, otherwise `'general'`
- If `onboarding_complete`: upsert `RiderCoachProfile` with extracted profile data (updating `User.ftp` and `User.max_heart_rate` if gathered during chat), invoke `coach_plan` Lambda, persist to `TrainingPlan`, persist a `CoachMessage` with `message_type='plan_generation'`
- Returns: `reply`, `onboarding_complete`, `plan_ready`, `token_usage`

### `GET /coach/plan`
Returns the active `TrainingPlan` as JSON.

Register the blueprint in `flask/app/__init__.py`.

---

## Task 4 — Next.js Coach Chat UI

Create `frontend/src/app/coach/page.jsx`. Read existing pages in `frontend/src/app/` first to understand fetch and auth patterns. Do not introduce new dependencies or new auth logic.

- On load: call `GET /coach/status`
- **Onboarding not complete**: show chat interface — coach messages left-aligned, rider messages right-aligned, text input and send button fixed at bottom. Each send calls `POST /coach/message`. When response includes `onboarding_complete: true`, transition to plan view.
- **Onboarding complete**: show plan view — weekly blocks as cards listing sessions (type, duration, zone, notes). Recent coach messages shown below as a read-only thread.
- Tailwind styling consistent with existing frontend.

---

## Constraints

- Do not modify `lambdas/coach/lambda_function.py` or any existing model or route
- Do not duplicate FTP — it lives on `vc_user`
- Do not use `db.JSON` — always `Text` with explicit serialisation
- Do not expose Lambdas directly to the Next.js frontend
- Do not introduce new npm or pip dependencies without checking existing requirements files first

---

Proceed task by task. Start with Task 1.
