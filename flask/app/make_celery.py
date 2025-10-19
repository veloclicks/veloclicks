from app import create_app

# This is called from docker-compose to return the celery app
# It calls create_app in __init__.py to create the celery instance
# and put in in the flask_app.extensions dictionary which is then
# retrieved and returned
print("make_celery() : Calling create_app(isCelery=True)")
flask_app = create_app(isCelery=True)

celery_app = flask_app.extensions["celery"]