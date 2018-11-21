
import os
from sqlalchemy_utils import database_exists, create_database


basedir = os.path.abspath(os.path.dirname(__file__))


def parse_var_env(var_name):
    v = os.environ.get(var_name)
    if v == "True":
        v = True
    elif v == "False":
        v = False
    return v


class Config(object):
    SECRET_KEY = parse_var_env('SECRET_KEY')

    SQLALCHEMY_DATABASE_URI = 'sqlite:////' + os.path.join(os.path.abspath(os.getcwd()), parse_var_env('DATABASE_URI'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DB_DROP_AND_CREATE_ALL = parse_var_env('DB_DROP_AND_CREATE_ALL') or False
    LOAD_FIXTURES = parse_var_env('LOAD_FIXTURES') or False

    ELASTICSEARCH_URL = parse_var_env('ELASTICSEARCH_URL')

    SCSS_STATIC_DIR = os.path.join(basedir, "app ", "static", "css")
    SCSS_ASSET_DIR = os.path.join(basedir, "app", "assets", "scss")
    CSRF_ENABLED = parse_var_env('CSRF_ENABLED')

    APP_URL_PREFIX = parse_var_env('APP_URL_PREFIX')
    API_VERSION = parse_var_env('API_VERSION')
    API_URL_PREFIX = parse_var_env('API_URL_PREFIX')

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):

    @staticmethod
    def init_app(app):
        print('THIS APP IS IN DEBUG MODE. YOU SHOULD NOT SEE THIS IN PRODUCTION.')
        with app.app_context():
            db_url = app.config["SQLALCHEMY_DATABASE_URI"]
            if not database_exists(db_url):
                # create db if not exist
                create_database(db_url)
            else:
                pass


class TestConfig(Config):
    DB_DROP_AND_CREATE_ALL = True


config = {
    "dev": DevelopmentConfig,
    "prod": Config,
    "test": TestConfig
}
