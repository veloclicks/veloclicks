from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from celery import Celery, Task
from flask_cors import CORS



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
# initialise celery
#
def celery_init_app(app: Flask) -> Celery:
    print('celery_init_app()')
    
    # get config that was added to the app
    celery_config = app.config.get('CELERY')

    # Access specific keys
    broker_url = app.config['CELERY']['broker_url']
    result_backend = app.config['CELERY']['result_backend']
    ignore_result = app.config['CELERY']['task_ignore_result']
    
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
# factory method for flask app
#
def create_app(isCelery=False) -> Flask:
    app = Flask(__name__)
    
    # load configuration from Config.py
    from app.config import Config
    app.config.from_object(Config)
    #print("Application config:", app.config)
    
    # make the app CORS compatible
    CORS(app)
    
    #
    # ----------- DATABASE INTIIALISATION ----------- 
    #
    if not isCelery:
        print('create_app() : Initialising database...............')
        from app.model import db
        db.init_app(app)
        migrate = Migrate()
        migrate.init_app(app, db)
    
        # import models - this will create the migrations
        with app.app_context():
            from app.models.user import User
            from app.models.car import Car
            from app.models.strava import Activity

    
    #
    # ----------- CELERY ----------- 
    #
    # TODO : THIS IS CURRENTLY CALLED TWICE
    print('create_app() : Initialising celery...............')
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
    
    print('create_app() : Registering blueprints...............')
    # register our blueprints - this should be after db init
    from app.views.main import main_bp
    app.register_blueprint(main_bp, url_prefix='/')
    from app.views.api import api_bp
    app.register_blueprint(api_bp)
    from app.views.strava import strava_bp
    app.register_blueprint(strava_bp)
    
    
    # Import tasks before initializing Celery
    print('create_app() : Configuring celery tasks...............')
    from app import tasks

    @app.route("/test_task/")
    def test_task():
        print('/test-task/ invoked')
        try:
            result = tasks.test_task.delay()
            return {"result_id": result.id}
        except Exception as e:
            return jsonify({'error': str(e)}), 500


    @app.route('/my_task/')
    def my_task():
        print('/my_task/ invoked')
        try:
            task = celery_app.send_task('app.tasks.my_task')
            return jsonify({'task_id': task.id}), 202
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return app