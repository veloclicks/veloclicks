from flask import Blueprint

insights_bp = Blueprint('insights', __name__, url_prefix='/insights')

from app.insights import routes
