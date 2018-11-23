from app.api.document.facade import DocumentFacade
from app.models import Document


def register_document_api_urls(app):
    registrar = app.api_url_registrar
    registrar.register_get_routes(Document, DocumentFacade)
    registrar.register_relationship_get_route(DocumentFacade, 'editors')

    registrar.register_post_routes(Document, DocumentFacade)
