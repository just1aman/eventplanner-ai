from flask import Blueprint

wizard_bp = Blueprint('wizard', __name__, template_folder='../../templates/wizard')

from app.blueprints.wizard import routes  # noqa: E402, F401
