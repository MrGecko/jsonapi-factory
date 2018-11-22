from app.api.editor.facade import EditorFacade
from app.models import Editor


def register_editor_api_urls(app):
    registrar = app.api_url_registrar
    registrar.register_get_routes(Editor, EditorFacade)
    registrar.register_relationship_get_route(EditorFacade, 'documents')
