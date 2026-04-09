import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app

env = os.environ.get('FLASK_ENV', 'development')
config_name = 'production' if env == 'production' else 'development'
application = create_app(config_name)

if __name__ == '__main__':
    application.run()
