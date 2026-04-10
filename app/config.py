import os


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    ANTHROPIC_MODEL = 'claude-sonnet-4-20250514'
    OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY')
    AMAZON_AFFILIATE_TAG = os.environ.get('AMAZON_AFFILIATE_TAG', 'eventplanai-20')
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///eventplanner_dev.db'


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'sqlite:///eventplanner.db'
    )


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
}
