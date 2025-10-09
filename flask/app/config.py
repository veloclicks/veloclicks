import os
from dotenv import load_dotenv

load_dotenv()

#
# Loads from .env file in root folder
#
class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 
        f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@"
        f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
    TEST_KEY = os.environ.get('TEST_KEY')
    
    BROKER_URL = os.environ.get('BROKER_URL')
    RESULT_BACKEND = os.environ.get('RESULT_BACKEND')

    # Demo user configuration
    DEMO_USERNAME = os.environ.get('DEMO_USERNAME', 'demo@veloclicks.com')

