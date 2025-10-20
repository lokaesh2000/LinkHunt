# webapp/__init__.py
from flask import Flask
from .routes import web_bp

def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.register_blueprint(web_bp)
    return app
