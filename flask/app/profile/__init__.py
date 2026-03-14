# Profile module
from flask import Blueprint

profile_bp = Blueprint('profile', __name__, url_prefix='/api')

from app.profile import routes
