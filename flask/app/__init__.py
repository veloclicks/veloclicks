from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
import logging
import sys


#
# Test broker connection to redis
#
def test_broker_connection(broker_url):
    print('celery_init_app() : Testing broker access:', broker_url)
    from kombu import Connection
    try:
        with Connection(broker_url) as conn:
            # ensure_connection will attempt to establish a connection
            conn.ensure_connection(max_retries=3)
        print("celery_init_app() : Successfully connected to broker at %s", broker_url)
    except Exception as e:
        print("celery_init_app() : Failed to connect to broker at %s: %s", broker_url, e)
        # Optionally, you could raise an exception here to stop further execution
        raise

#
# initialise celery with a Flask instance passed in as the app variable
# Note that the main init methos is below this one
#
def celery_init_app(app: Flask) -> "Celery":
    print('__init__.py >> celery_init_app()')
    from celery import Celery, Task
    
    # get config that was added to the app
    celery_config = app.config.get('CELERY')

    # Access specific keys
    broker_url      = app.config['CELERY']['broker_url']
    result_backend  = app.config['CELERY']['result_backend']
    ignore_result   = app.config['CELERY']['task_ignore_result']
    
    # test broiker connetivity
    test_broker_connection(broker_url)
    
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(
        app.import_name,
        task_cls=FlaskTask,
        broker_url=broker_url,
        result_backend=result_backend,
        ignore_result = ignore_result,
        imports=['app.tasks']
    )
    # not really necessary
    celery_app.set_default()
    
    return celery_app


# --------------------------------------------------------------

#
# factory method for flask app - this is the best practise way to create a flask
# instance but its also called by celery as a celery instance will share code and
# needs the flask context. For simplicity here, celery runs in the same context
# and create_app is actually called twice - once by flask and once by celery
# If its celery I don't instantiate the database as its already there
#
def create_app(*args, **kwargs) -> Flask:
    print("__init__.py create_app()")
    
    is_celery   = kwargs.get('isCelery', False)
    app = Flask(__name__)

    # load configuration from Config.py
    print("__init__.py create_app() >> Loading config from app.config.Config")
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


    # Now we can access app.config for skip_celery
    skip_celery = kwargs.get('skipCelery', app.config.get('SKIP_CELERY', False))
    print(f"__init__.py create_app() >> skip_celery is {skip_celery}")

    # make the app CORS compatible
    CORS(app)


    #
    # --- DATABASE INTIIALISATION - DON"T DO THIS IF THE FLASK APP IS BEING CREATED BY CELERY ----
    #
    if not is_celery:
        from app.models import db, User, Activity
        db.init_app(app)
        migrate = Migrate()
        migrate.init_app(app, db)

        # import models - this will create the migrations
        with app.app_context():
            # Models already imported above
            pass

    #
    # Create celery instance if requested (don't request from zappa AWS as it won;t work in lambda
    #
    if not skip_celery:
        
        from celery import Celery, Task
        
        app.config.from_mapping(
            CELERY=dict(
                broker_url="redis://redis:6379/0",
                result_backend="redis://redis:6379/0",
                task_ignore_result=True,
            ),
        )
        app.config.from_prefixed_env()
        celery_app = celery_init_app(app)
        app.extensions["celery"] = celery_app

    #
    # ----------- VIEWS AND URL ROUTING -----------
    #

    # register our blueprints - this should be after db init
    from app.views.main import main_bp
    app.register_blueprint(main_bp, url_prefix='/')
    
    from app.views.api import api_bp
    app.register_blueprint(api_bp)
    
    from app.strava import strava_bp
    app.register_blueprint(strava_bp)

    from app.agent import agent_bp
    app.register_blueprint(agent_bp)

    from app.insights import insights_bp
    app.register_blueprint(insights_bp)

    # Register CLI commands
    from app.admin.cli import admin
    app.cli.add_command(admin)

    #
    # If Celery is enabled, create the tasks
    #
    if not skip_celery:
        @app.route("/test_task/")
        def test_task():
            try:
                from app import tasks  # Lazy import only when route is called
                result = tasks.test_task.delay()
                return {"result_id": result.id}
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @app.route('/my_task/')
        def my_task():
            try:
                task = celery_app.send_task('app.tasks.my_task')
                return jsonify({'task_id': task.id}), 202
            except Exception as e:
                return jsonify({'error': str(e)}), 500

    return app


# Create app instance for Zappa (Docker will continue using create_app() directly)
application = create_app()