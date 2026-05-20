Iteration 1: Review strava module

- python3 agent_cli.py --agent architect --task "Review strava module. Identify where design preferences are not being followed and suggest refactorings" --code flask/app/strava  

Agent Output: 

📂 Base directory: /Users/patrick/dev/veloclicks/ai
📂 Repo root: /Users/patrick/dev/veloclicks

📖 Loading architect agent...
📖 Loading context...
📖 Loading code files: flask/app/strava

================================================================================
🤖 Running architect agent...
================================================================================

/Users/patrick/dev/veloclicks/ai/agent_cli.py:136: DeprecationWarning: The model 'claude-sonnet-4-20250514' is deprecated and will reach end-of-life on June 15th, 2026.
Please migrate to a newer model. Visit https://docs.anthropic.com/en/docs/resources/model-deprecations for more information.
  response = client.messages.create(
# Strava Module Review

## Current State Assessment

The strava module demonstrates several concerning anti-patterns that violate the established design principles:

### Major Issues

**1. Massive Route File with Business Logic**
- `routes.py` is 600+ lines containing complex business logic, token refresh, activity processing, and data transformation
- Violates the principle that routes should be API entry points only

**2. Giant Service Class Anti-Pattern**
- `utils.py` contains everything from token management to activity processing to coordinate transformation
- Single 500+ line file mixing multiple concerns without clear boundaries

**3. Inconsistent Module Naming**
- File named `utils.py` but contains core domain services
- Should be `tools.py` per design principles

**4. Mixed Responsibilities**
- Routes handling OAuth flows, activity sync, data processing, and API endpoints
- No clear separation between authentication, data ingestion, and presentation logic

**5. Direct Database Access from Routes**
- Routes directly manipulating `User` and `Activity` models
- Violates principle of going through tools.py services

## Proposed Refactoring

### Target Structure
```
strava/
├── __init__.py
├── routes.py       # API endpoints only
├── tools.py        # Domain services 
├── auth.py         # OAuth and token management
└── streams.py      # Keep as-is (already well-focused)
```

### 1. Slim Routes (`routes.py`)
```python
from flask import Blueprint, request, jsonify, redirect
from . import tools as strava_tools
from app.auth.tools import get_current_user_id

strava_bp = Blueprint('strava', __name__, url_prefix='/strava')

@strava_bp.route('/auth')
def strava_auth():
    """Handle Strava OAuth callback"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    
    result = strava_tools.handle_oauth_callback(
        request.args.get('code'),
        request.args.get('state'), 
        request.args.get('error')
    )
    
    if result.success:
        return redirect(result.redirect_url)
    else:
        return redirect(result.error_url)

@strava_bp.route('/synch')
def sync_activities():
    """Sync recent activities from Strava"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    
    result = strava_tools.sync_recent_activities(user_id)
    return jsonify(result.to_dict())

@strava_bp.route('/activities')
def get_activities():
    """Get user's activities with optional filtering"""
    user_id = get_current_user_id()
    filters = strava_tools.parse_activity_filters(request.args)
    
    activities = strava_tools.get_user_activities(user_id, filters)
    return jsonify(activities)
```

### 2. Focused Domain Services (`tools.py`)
```python
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime, timedelta

from app.models import User, Activity
from . import auth as strava_auth

@dataclass
class SyncResult:
    success: bool
    new_count: int
    total_processed: int
    message: str
    
    def to_dict(self):
        return {
            'success': self.success,
            'new_activities': self.new_count, 
            'total_processed': self.total_processed,
            'message': self.message
        }

@dataclass 
class OAuthResult:
    success: bool
    redirect_url: str
    error_url: Optional[str] = None

def handle_oauth_callback(code: str, state: str, error: str) -> OAuthResult:
    """Handle the complete OAuth flow"""
    if error:
        return OAuthResult(
            success=False,
            redirect_url=_build_error_url('access_denied'),
            error_url=_build_error_url('access_denied')
        )
    
    if not code or not state:
        return OAuthResult(
            success=False, 
            redirect_url=_build_error_url('missing_params')
        )
    
    # Exchange tokens and store
    tokens = strava_auth.exchange_code_for_tokens(code)
    if not tokens:
        return OAuthResult(
            success=False,
            redirect_url=_build_error_url('token_exchange')
        )
    
    strava_auth.store_user_tokens(int(state), tokens)
    
    # Perform initial sync
    sync_result = sync_recent_activities(int(state), days=30)
    
    return OAuthResult(
        success=True,
        redirect_url=_build_success_url(sync_result.new_count)
    )

def sync_recent_activities(user_id: int, days: int = 30) -> SyncResult:
    """Sync activities from last N days"""
    user = _get_user_or_error(user_id)
    
    time_window = _calculate_sync_window(user, days)
    activities = strava_auth.fetch_strava_activities(
        user_id, 
        time_window.after_epoch, 
        time_window.before_epoch
    )
    
    if not activities:
        return SyncResult(
            success=False,
            new_count=0, 
            total_processed=0,
            message="Failed to fetch activities from Strava"
        )
    
    new_count = _store_new_activities(user_id, activities)
    _update_last_sync(user, time_window.before_epoch)
    
    return SyncResult(
        success=True,
        new_count=new_count,
        total_processed=len(activities),
        message=f"Sync completed. {new_count} new activities added."
    )

def get_user_activities(user_id: int, filters: dict) -> List[dict]:
    """Get stored activities for a user with filtering"""
    return _query_activities_with_filters(user_id, filters)
```

### 3. Separate Auth Concerns (`auth.py`)
```python
from dataclasses import dataclass
from typing import Optional, List, Dict
import requests
from flask import current_app

from app.models import db, User

@dataclass
class TokenData:
    access_token: str
    refresh_token: str
    expires_at: int

def get_valid_access_token(user_id: int) -> Optional[str]:
    """Get valid access token, refreshing if necessary"""
    user = User.query.get(user_id)
    if not user:
        return None
        
    if _is_token_valid(user):
        return user.strava_access_token
    
    return _refresh_user_token(user)

def exchange_code_for_tokens(code: str) -> Optional[TokenData]:
    """Exchange OAuth code for access/refresh tokens"""
    # Implementation extracted from current routes.py
    pass

def fetch_strava_activities(user_id: int, after_epoch: int, before_epoch: int) -> Optional[List[Dict]]:
    """Fetch activities from Strava API"""
    # Implementation extracted from current utils.py
    pass

def store_user_tokens(user_id: int, tokens: TokenData):
    """Store tokens for user"""
    # Implementation extracted from current routes.py
    pass
```

## Migration Strategy

### Phase 1: Extract Auth Logic
1. Create `auth.py` with token management functions
2. Update routes to call auth functions instead of inline logic
3. Test OAuth flow still works

### Phase 2: Create Domain Services  
1. Rename `utils.py` to `tools.py`
2. Extract business logic from routes into service functions
3. Create proper return types and error handling

### Phase 3: Slim Routes
1. Refactor routes to be thin wrappers around tools functions
2. Remove all database access from routes
3. Standardize response formats

### Phase 4: Clean Up Boundaries
1. Remove duplicate constants and utilities
2. Establish clear contracts between layers
3. Add proper error handling and logging

## Benefits

**Separation of Concerns**: OAuth, business logic, and API endpoints clearly separated

**Testability**: Domain services can be tested independently of Flask routes

**Maintainability**: Changes to Strava API integration isolated to specific modules

**Reusability**: Activity sync logic can be called from other parts of the system

**Design Principle Compliance**: Routes become thin, business logic moves to tools, clear module boundaries

## Risks

**Short-term complexity**: Refactoring will require careful testing of OAuth flow

**Token refresh logic**: Critical path that must not break during migration

**Activity sync reliability**: Core product functionality that needs thorough validation

This refactoring transforms the strava module from a monolithic utilities collection into a properly bounded domain with clear responsibilities and contracts.

================================================================================
✅ Analysis complete
================================================================================