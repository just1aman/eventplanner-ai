from flask import Flask, render_template
from app.extensions import db, login_manager, csrf, migrate, oauth
from app.config import config_by_name


def create_app(config_name='development'):
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    oauth.init_app(app)

    # Register Google OAuth provider
    oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )

    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    from app.blueprints.auth import auth_bp
    from app.blueprints.wizard import wizard_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.api import api_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(wizard_bp, url_prefix='/event')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    # Import models so they're registered with SQLAlchemy
    from app import models  # noqa: F401

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    return app
