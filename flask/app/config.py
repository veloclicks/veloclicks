import os
from dotenv import load_dotenv
load_dotenv()


# 
# Resolve parameters from AWS Parameter Store
#
def resolve_ssm_parameter(value):
    """Resolve Parameter Store values if they start with ssm://"""
    print(f"----- config.py : Resolving SSM parameter {value}")
    
    if isinstance(value, str) and value.startswith('ssm://'):
        try:
            import boto3
            parameter_name = '/' + value.replace('ssm://', '')
            ssm = boto3.client('ssm', region_name='eu-west-2')
            response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
            resolved_value = response['Parameter']['Value']
            print(f"----- config.py : Resolved {parameter_name}")
            return resolved_value
        except Exception as e:
            print(f"----- config.py : Failed to resolve {value}: {e}")
            return value
    return value


# Resolve environment variables
database_url    = resolve_ssm_parameter(os.getenv('DATABASE_URL'))
secret_key      = resolve_ssm_parameter(os.getenv('SECRET_KEY'))
strava_client_id     = resolve_ssm_parameter(os.getenv('STRAVA_CLIENT_ID'))
strava_client_secret = resolve_ssm_parameter(os.getenv('STRAVA_CLIENT_SECRET'))


# Debug configuration for Lambda environment
print("\n----- config.py : LAMBDA FLASK CONFIGURATION ----")
print(f"LOG_LEVEL: {os.getenv('LOG_LEVEL', 'INFO')}")
try:
    print(f"Raw DATABASE_URL: {os.getenv('DATABASE_URL')}")
    print(f"Resolved DATABASE_URL: {database_url[:50]}..." if database_url else "None")
    print(f"SECRET_KEY exists: {bool(secret_key)}")
    print(f"Raw STRAVA_CLIENT_ID: {os.getenv('STRAVA_CLIENT_ID')}")
    print(f"Resolved STRAVA_CLIENT_ID: {strava_client_id}")
    print(f"STRAVA_CLIENT_SECRET exists: {bool(strava_client_secret)}")
    print(f"FLASK_APP: {os.getenv('FLASK_APP')}")
    print(f"SKIP_CELERY: {os.getenv('SKIP_CELERY')}")
    print(f"TEST_PARAM: {os.getenv('TEST_PARAM')}")
    print(f"FRONTEND_URL: {os.getenv('FRONTEND_URL')}")
    print("-------------------------------------")
except Exception as e:
    print(f"----- config.py : Exception getting environment config: {e}")


#
# Loads from .env file in root folder or from zappa config
#
class Config:
    print(f"----- config.py : Config class")
    SQLALCHEMY_DATABASE_URI = database_url or f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY              = secret_key
    STRAVA_CLIENT_ID        = strava_client_id
    STRAVA_CLIENT_SECRET    = strava_client_secret
    LOG_LEVEL               = os.getenv('LOG_LEVEL', 'INFO')
    TEST_KEY                = os.getenv('TEST_KEY')

    BROKER_URL      = os.getenv('BROKER_URL')
    RESULT_BACKEND  = os.getenv('RESULT_BACKEND')
    DEMO_USERNAME   = os.getenv('DEMO_USERNAME', 'demo@veloclicks.com')

    # Celery configuration - default is false, returns a boolean by comparing strings 
    SKIP_CELERY     = os.getenv('SKIP_CELERY', 'false').lower() == 'true'
    
    # Debug configuration for Lambda environment
    print("\n----- config.py.Config : LOCAL FLASK CONFIGURATION ----")
    print(f"LOG_LEVEL: {os.getenv('LOG_LEVEL', 'INFO')}")
    try:
        print(f"Raw DATABASE_URL: {os.getenv('DATABASE_URL')}")
        print(f"Resolved DATABASE_URL: {database_url[:50]}..." if database_url else "None")
        print(f"SECRET_KEY exists: {bool(secret_key)}")
        print(f"Raw STRAVA_CLIENT_ID: {os.getenv('STRAVA_CLIENT_ID')}")
        print(f"Resolved STRAVA_CLIENT_ID: {strava_client_id}")
        print(f"STRAVA_CLIENT_SECRET exists: {bool(strava_client_secret)}")
        print(f"FLASK_APP: {os.getenv('FLASK_APP')}")
        print(f"SKIP_CELERY: {os.getenv('SKIP_CELERY')}")
        print(f"TEST_PARAM: {os.getenv('TEST_PARAM')}")
        print(f"FRONTEND_URL: {os.getenv('FRONTEND_URL')}")
        print("-------------------------------------")
    except Exception as e:
        print(f"----- config.py : Exception getting environment config: {e}")