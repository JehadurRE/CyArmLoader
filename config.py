import os
from decouple import config


UPLOAD_PATH = os.path.join(os.getcwd(), 'media', 'uploads')

class Config(object):
    SECRET_KEY = config('SECRET_KEY') or 'guess-me'
    UPLOAD_FOLDER = UPLOAD_PATH
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True

    # EMAIL SETTINGS
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_DEBUG = True
    MAIL_USERNAME = config("EMAIL_ADDRESS")
    MAIL_PASSWORD = config("EMAIL_PASSWORD")


class ProductionConfig(Config):
    DEBUG = False
    MAIL_DEBUG = False


class StagingConfig(Config):
    DEVELOPMENT = True
    DEBUG = True


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
