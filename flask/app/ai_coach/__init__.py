from flask import Blueprint

ai_coach_bp = Blueprint('ai_coach', __name__, url_prefix='/ai-coach')

from app.ai_coach import routes
