from app.api.document.facade import DocumentFacade
from app.models import Document


def get_document(doc_id):
    e = Document.query.filter(Document.id == doc_id).first()
    if e is None:
        kwargs = {"status": 404}
        errors = [{"status": 404, "title": "document %s does not exist" % doc_id}]
    else:
        kwargs = {}
        errors = []
    return e, kwargs, errors


def register_document_api_urls(app):
    registrar = app.api_url_registrar
    registrar.register_get_routes(get_document, Document, DocumentFacade)
    registrar.register_relationship_get_route(get_document, DocumentFacade, 'editors')
