from app.api.editor.facade import EditorFacade
from app.models import Document, Editor


def get_editor(doc_id):
    e = Document.query.filter(Editor.id == doc_id).first()
    if e is None:
        kwargs = {"status": 404}
        errors = [{"status": 404, "title": "editor %s does not exist" % doc_id}]
    else:
        kwargs = {}
        errors = []
    return e, kwargs, errors


def register_editor_api_urls(app):
    registrar = app.api_url_registrar
    registrar.register_get_routes(get_editor, Editor, EditorFacade)
    registrar.register_relationship_get_route(get_editor, EditorFacade, 'editors')
