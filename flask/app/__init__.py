from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
import logging
import sys


def create_app(*args, **kwargs) -> Flask:
    app = Flask(__name__)

    # load configuration from Config.py
    from app.config import Config
    app.config.from_object(Config)

    # -------------- logging -----------------
    log_level = getattr(logging, app.config['LOG_LEVEL'].upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler that writes to stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Reduce noise from Zappa and other third-party loggers
    logging.getLogger('zappa').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('anthropic._base_client').setLevel(logging.WARNING)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    logging.getLogger('httpcore.http11').setLevel(logging.WARNING)
    logging.getLogger('httpcore.connection').setLevel(logging.WARNING)

    # make the app CORS compatible
    CORS(app)

    # --- DATABASE INITIALISATION ---
    from app.models import db, User, Activity
    db.init_app(app)
    migrate = Migrate()
    migrate.init_app(app, db)

    with app.app_context():
        pass

    # ----------- VIEWS AND URL ROUTING -----------

    from app.admin import admin_bp
    app.register_blueprint(admin_bp)

    from app.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.profile import profile_bp
    app.register_blueprint(profile_bp)

    from app.strava import strava_bp
    app.register_blueprint(strava_bp)

    from app.ai_coach import ai_coach_bp
    app.register_blueprint(ai_coach_bp)

    # Register CLI commands
    from app.admin.cli import admin
    app.cli.add_command(admin)

    return app


# Create app instance for Zappa (Docker will continue using create_app() directly)
application = create_app()
