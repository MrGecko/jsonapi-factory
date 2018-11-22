import pprint
from elasticsearch import Elasticsearch
from flask import Flask, Blueprint
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

from werkzeug.contrib.profiler import ProfilerMiddleware
from dotenv import load_dotenv

from app.api.response_factory import JSONAPIResponseFactory


# Initialize Flask extensions
db = SQLAlchemy()

api_bp = Blueprint('api_bp', __name__)
app_bp = Blueprint('app_bp', __name__, template_folder='templates', static_folder='static')


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class PrefixMiddleware(object):

    def __init__(self, app, prefix=''):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):

        if environ['PATH_INFO'].startswith(self.prefix):
            environ['PATH_INFO'] = environ['PATH_INFO'][len(self.prefix):]
            environ['SCRIPT_NAME'] = self.prefix
            return self.app(environ, start_response)


def create_app(config_name="dev"):
    """ Create the application """
    app = Flask(__name__)
    if not isinstance(config_name, str):
        from config import config
        app.config.from_object(config)
    else:
        print("Load environment variables for config '%s'" % config_name)
        # It is important to load the .env file before parsing the config file
        load_dotenv('%s.env' % config_name, verbose=True)
        from config import config
        app.config.from_object(config[config_name])

    app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix=app.config["APP_URL_PREFIX"])

    db.init_app(app)
    config[config_name].init_app(app)

    app.db = db

    app.elasticsearch = Elasticsearch([app.config['ELASTICSEARCH_URL']]) if app.config['ELASTICSEARCH_URL'] else None

    # =====================================
    # Import models & app routes
    # =====================================

    from app import models
    from app import routes

    # =====================================
    # register api routes
    # =====================================

    from app.api.route_registrar import JSONAPIRouteRegistrar
    app.api_url_registrar = JSONAPIRouteRegistrar(app.config["API_VERSION"], app.config["API_URL_PREFIX"])

    from app.api import routes

    from app.api.document.routes import register_document_api_urls
    from app.api.editor.routes import register_editor_api_urls

    with app.app_context():
        # generate GET routes for the API
        register_document_api_urls(app)
        register_editor_api_urls(app)

    app.register_blueprint(app_bp)
    app.register_blueprint(api_bp)

    if app.config["DB_DROP_AND_CREATE_ALL"]:
        print("DB_DROP_AND_CREATE_ALL")
        with app.app_context():
            db.drop_all()
            db.create_all()

        # LOAD FIXTURES
        if app.config["LOAD_FIXTURES"]:
            from db.fixtures import load_fixtures
            with app.app_context():
                load_fixtures(db)

    return app
