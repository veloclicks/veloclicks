import os
from dotenv import load_dotenv

load_dotenv()

#
# Loads from .env file in root folder or from zappa config
#
class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 
        f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@"
        f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY      = os.getenv('SECRET_KEY')
    TEST_KEY        = os.getenv('TEST_KEY')

    BROKER_URL      = os.getenv('BROKER_URL')
    RESULT_BACKEND  = os.getenv('RESULT_BACKEND')

   
    DEMO_USERNAME   = os.getenv('DEMO_USERNAME', 'demo@veloclicks.com')

    # Celery configuration - set to true 
    SKIP_CELERY     = os.getenv('SKIP_CELERY', 'false').lower() == 'true'

