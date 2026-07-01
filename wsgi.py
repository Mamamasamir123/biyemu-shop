"""Entry point kwa Render / gunicorn."""
from web.server import flask_app

application = flask_app