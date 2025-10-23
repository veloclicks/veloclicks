import os
from dotenv import load_dotenv

load_dotenv()

def resolve_ssm_parameter(value):
    """Resolve Parameter Store values if they start with ssm://"""
    if isinstance(value, str) and value.startswith('ssm://'):
        try:
            import boto3
            parameter_name = '/' + value.replace('ssm://', '')  # Add leading slash
            ssm = boto3.client('ssm', region_name='eu-west-2')
            response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
            resolved_value = response['Parameter']['Value']
            print(f"✅ Resolved {parameter_name} from Parameter Store")
            return resolved_value
        except Exception as e:
            print(f"❌ Failed to resolve {value}: {e}")
            return value
    return value

# Resolve environment variables
database_url = resolve_ssm_parameter(os.getenv('DATABASE_URL'))
secret_key = resolve_ssm_parameter(os.getenv('SECRET_KEY'))

# Debug prints for Lambda environment
print("=== CONFIG DEBUG ===")
try:
    print(f"Raw DATABASE_URL: {os.getenv('DATABASE_URL')}")
    print(f"Resolved DATABASE_URL: {database_url[:50]}..." if database_url else "None")
    print(f"SECRET_KEY exists: {bool(secret_key)}")
    print(f"FLASK_APP: {os.getenv('FLASK_APP')}")
    print(f"SKIP_CELERY: {os.getenv('SKIP_CELERY')}")
    print("==================")
except Exception as e:
    print(f"Exception getting environment config: {e}")

#
# Loads from .env file in root folder or from zappa config
#
class Config:
    SQLALCHEMY_DATABASE_URI = database_url or f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = secret_key
    TEST_KEY        = os.getenv('TEST_KEY')

    BROKER_URL      = os.getenv('BROKER_URL')
    RESULT_BACKEND  = os.getenv('RESULT_BACKEND')

   
    DEMO_USERNAME   = os.getenv('DEMO_USERNAME', 'demo@veloclicks.com')

    # Celery configuration - set to true 
    SKIP_CELERY     = os.getenv('SKIP_CELERY', 'false').lower() == 'true'

