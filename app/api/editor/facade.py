from app.api.abstract_facade import JSONAPIAbstractFacade
from app.models import Editor


class EditorFacade(JSONAPIAbstractFacade):
    """

    """
    TYPE = "editor"
    TYPE_PLURAL = "editors"

    @staticmethod
    def get_model():
        return Editor

    @property
    def id(self):
        return self.obj.id

    def get_documents_resource_identifiers(self):
        from app.api.document.facade import DocumentFacade
        return [] if self.obj.documents is None else [DocumentFacade.make_resource_identifier(d.id, DocumentFacade.TYPE)
                                                      for d in self.obj.documents]

    def get_documents_resources(self):
        from app.api.document.facade import DocumentFacade
        return [] if self.obj.documents is None else [DocumentFacade(self.url_prefix, d,
                                                                     self.with_relationships_links,
                                                                     self.with_relationships_data).resource
                                                      for d in self.obj.documents]

    @staticmethod
    def get_obj(doc_id):
        e = Editor.query.filter(Editor.id == doc_id).first()
        if e is None:
            kwargs = {"status": 404}
            errors = [{"status": 404, "title": "editor %s does not exist" % doc_id}]
        else:
            kwargs = {}
            errors = []
        return e, kwargs, errors

    def __init__(self, *args, **kwargs):
        super(EditorFacade, self).__init__(*args, **kwargs)
        """Make a JSONAPI resource object describing what is a document

        A document is made of:
        attributes:
            id:
            name:
        relationships:
            editors
        Returns
        -------
            A dict describing the corresponding JSONAPI resource object
        """

        self.relationships = {
            "documents": {
                "links": self._get_links(rel_name="documents"),
                "resource_identifier_getter": self.get_documents_resource_identifiers,
                "resource_getter": self.get_documents_resources
            },
        }

        self.resource = {
            **self.resource_identifier,
            "attributes": {
                "id": self.obj.id,
                "name": self.obj.name
            },
            "meta": self.meta,
            "links": {
                "self": self.self_link
            }
        }
        if self.with_relationships_links:
            self.resource["relationships"] = self.get_exposed_relationships()
