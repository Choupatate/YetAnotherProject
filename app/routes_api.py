from flask import Blueprint

bp = Blueprint("api", __name__, url_prefix="/api")

# Routes are added in a later phase (create/update story, image upload).
