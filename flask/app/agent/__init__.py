from flask import Blueprint

agent_bp = Blueprint('agent', __name__, url_prefix='/agent')

from app.agent import routes
