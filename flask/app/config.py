"""
Configuration module for Flask application

Environment Resolution:
- LOCAL/DOCKER: Reads from .env file in project root via load_dotenv()
- AWS LAMBDA: Reads from Lambda environment variables set by Zappa (zappa_settings.json)
  - Non-sensitive values (LOG_LEVEL, FLASK_APP, etc.) are plain strings
  - Sensitive values (DATABASE_URL, SECRET_KEY, etc.) use ssm:// prefix and are resolved from AWS Parameter Store
"""

import os
from dotenv import load_dotenv
load_dotenv()

# Configuration variables (resolved at module load time)
DATABASE_URL = None
POSTGRES_USER = None
POSTGRES_PASSWORD = None
POSTGRES_HOST = None
POSTGRES_PORT = None
POSTGRES_DB = None
SECRET_KEY = None
STRAVA_CLIENT_ID = None
STRAVA_CLIENT_SECRET = None
ANTHROPIC_API_KEY = None
LOG_LEVEL = None
FLASK_APP = None
SKIP_CELERY = None
FRONTEND_URL = None
BROKER_URL = None
RESULT_BACKEND = None
# DEMO_USERNAME = None
# TEST_KEY = None


#
# Resolve parameters from AWS Parameter Store
#
def resolve_ssm_parameter(value):
    if isinstance(value, str) and value.startswith('ssm://'):
        try:
            import boto3
            parameter_name = '/' + value.replace('ssm://', '')
            ssm = boto3.client('ssm', region_name='eu-west-2')
            response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
            resolved_value = response['Parameter']['Value']
            return resolved_value
        except Exception as e:
            print(f"----- config.py : Failed to resolve {value}: {e}")
            return value
    return value

#
# Resolves environment configuration - whether from AWS Param Store or a local .env or zappa settings
# Zappa settings should contain the non-sensitive config fo AWS, sensitive should be in param store
#
def resolve_env_config():
    global DATABASE_URL, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB
    global SECRET_KEY, STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, ANTHROPIC_API_KEY
    global LOG_LEVEL, FLASK_APP, SKIP_CELERY, FRONTEND_URL, BROKER_URL, RESULT_BACKEND  # , DEMO_USERNAME, TEST_KEY

    if os.getenv('AWS_EXECUTION_ENV') is not None or os.getenv('AWS_LAMBDA_FUNCTION_NAME') is not None:
        # AWS Lambda - resolve SSM parameters
        DATABASE_URL = resolve_ssm_parameter(os.getenv('DATABASE_URL'))
        SECRET_KEY = resolve_ssm_parameter(os.getenv('SECRET_KEY'))
        STRAVA_CLIENT_ID = resolve_ssm_parameter(os.getenv('STRAVA_CLIENT_ID'))
        STRAVA_CLIENT_SECRET = resolve_ssm_parameter(os.getenv('STRAVA_CLIENT_SECRET'))
        ANTHROPIC_API_KEY = resolve_ssm_parameter(os.getenv('ANTHROPIC_API_KEY'))
    else:
        # Running locally - use environment variables directly
        DATABASE_URL = os.getenv('DATABASE_URL')
        SECRET_KEY = os.getenv('SECRET_KEY')
        STRAVA_CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
        STRAVA_CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
        ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

        # Fallback PostgreSQL connection variables (only used locally if DATABASE_URL not set)
        POSTGRES_USER = os.getenv('POSTGRES_USER')
        POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
        POSTGRES_HOST = os.getenv('POSTGRES_HOST')
        POSTGRES_PORT = os.getenv('POSTGRES_PORT')
        POSTGRES_DB = os.getenv('POSTGRES_DB')

    # Common configuration (both environments)
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    FLASK_APP = os.getenv('FLASK_APP')
    SKIP_CELERY = os.getenv('SKIP_CELERY', 'false').lower() == 'true'
    FRONTEND_URL = os.getenv('FRONTEND_URL')
    BROKER_URL = os.getenv('BROKER_URL')
    RESULT_BACKEND = os.getenv('RESULT_BACKEND')
    # DEMO_USERNAME = os.getenv('DEMO_USERNAME', 'demo@veloclicks.com')
    # TEST_KEY = os.getenv('TEST_KEY')


# log environment variables
def log_config():
    """Log configuration values for debugging"""
    print("\n----- config.py : ENVIRONMENT CONFIGURATION ----")
    try:
        print(f"LOG_LEVEL: {LOG_LEVEL}")
        print(f"DATABASE_URL: {DATABASE_URL[:4]}...{DATABASE_URL[-4:]}" if DATABASE_URL else "None")
        print(f"STRAVA_CLIENT_ID: {STRAVA_CLIENT_ID}")
        print(f"STRAVA_CLIENT_SECRET: {STRAVA_CLIENT_SECRET[:4]}...{STRAVA_CLIENT_SECRET[-4:]}" if STRAVA_CLIENT_SECRET else "None")
        print(f"ANTHROPIC_API_KEY: {ANTHROPIC_API_KEY[:4]}...{ANTHROPIC_API_KEY[-4:]}" if ANTHROPIC_API_KEY else "None")
        print(f"FLASK_APP: {FLASK_APP}")
        print(f"SKIP_CELERY: {SKIP_CELERY}")
        print(f"FRONTEND_URL: {FRONTEND_URL}")
        print(f"BROKER_URL: {BROKER_URL}")
        print(f"RESULT_BACKEND: {RESULT_BACKEND}")
        #print(f"DEMO_USERNAME: {DEMO_USERNAME}")
        #print(f"TEST_KEY: {TEST_KEY}")
        print("-------------------------------------")
    except Exception as e:
        print(f"----- config.py : Exception getting environment config: {e}")


resolve_env_config()
log_config()


#
# Loads from .env file in root folder or from zappa config
#
class Config:

    SQLALCHEMY_DATABASE_URI = DATABASE_URL or f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = SECRET_KEY
    STRAVA_CLIENT_ID = STRAVA_CLIENT_ID
    STRAVA_CLIENT_SECRET = STRAVA_CLIENT_SECRET
    ANTHROPIC_API_KEY = ANTHROPIC_API_KEY

    LOG_LEVEL = LOG_LEVEL
    FLASK_APP = FLASK_APP
    SKIP_CELERY = SKIP_CELERY
    FRONTEND_URL = FRONTEND_URL
    BROKER_URL = BROKER_URL
    RESULT_BACKEND = RESULT_BACKEND
    #DEMO_USERNAME = DEMO_USERNAME
    #TEST_KEY = TEST_KEY