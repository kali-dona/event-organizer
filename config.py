"""This module defines the configuration settings used in the Flask app"""
import os


class Config:
    """Base configuration class that provides configuration parameters for setting up
    the Flask app, database connection, file uploads, email configuration, etc."""
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24))

    SERVER_NAME = 'localhost:5001'
    PREFERRED_URL_SCHEME = 'http'

    SCHEDULER_API_ENABLED = True

    UPLOAD_FOLDER = 'app/static/profile_pictures'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    MAIL_SERVER = 'smtp.abv.bg'
    MAIL_PORT = 465
    MAIL_USE_TLS = False
    MAIL_USE_SSL = True
    MAIL_USERNAME = 'organize.it@abv.bg'
    MAIL_PASSWORD = 'myPyth8$4Even$t'
    MAIL_DEFAULT_SENDER = 'organize.it@abv.bg'


class TestingConfig(Config):
    """Configuration subclass which inherits from the base
    Config class but overrides certain settings for testing purposes."""
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # SQLite in-memory bd for testing
    TESTING = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
