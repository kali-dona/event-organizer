"""This module sets up the Flask application, including database integration,
user authentication, email handling, and scheduled background tasks.
It also registers application blueprints and ensures necessary directories exist."""

import os
import atexit
from dotenv import load_dotenv

from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler

from config import Config

db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
login_manager = LoginManager()

def create_app(config_name=None):
    """Function initializes and configures the Flask app."""
    load_dotenv()
    app = Flask(__name__)
    if config_name:
        app.config.from_object(config_name)
    else:
        app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    login_manager.login_view = 'auth.login'

    from app.index.routes import index
    from app.auth.routes import auth
    from app.event.routes import event
    from app.user.routes import user
    from app.tasks import notify_upcoming_events, clean_up_old_notifications
    from app.models import User

    app.register_blueprint(index)
    app.register_blueprint(auth)
    app.register_blueprint(event)
    app.register_blueprint(user)

    with app.app_context():
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: app.app_context().push() or notify_upcoming_events(),
        trigger='interval',
        hours=12
    )
    scheduler.add_job(
        func=lambda: app.app_context().push() or clean_up_old_notifications(),
        trigger='interval',
        hours=24
    )
    scheduler.start()

    atexit.register(lambda: scheduler.shutdown())

    return app
