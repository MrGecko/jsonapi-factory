from app.api.abstract_facade import JSONAPIAbstractFacade
from app.models import Editor


class EditorFacade(JSONAPIAbstractFacade):
    """

    """
    TYPE = "editor"
    TYPE_PLURAL = "editors"

    @property
    def id(self):
        return self.obj.id

    @staticmethod
    def get_resource_facade(url_prefix, doc_id, **kwargs):
        e = Editor.query.filter(Editor.id == doc_id).first()
        if e is None:
            kwargs = {"status": 404}
            errors = [{"status": 404, "title": "editor %s does not exist" % doc_id}]
        else:
            e = EditorFacade(url_prefix, e, **kwargs)
            kwargs = {}
            errors = []
        return e, kwargs, errors

    @property
    def resource(self):
        resource = {
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
            resource["relationships"] = self.get_exposed_relationships()

        return resource

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

        from app.api.document.facade import DocumentFacade
        self.relationships = {
            "documents": {
                "links": self._get_links(rel_name="documents"),
                "resource_identifier_getter": self.get_related_resource_identifiers(DocumentFacade, "documents", True),
                "resource_getter": self.get_related_resources(DocumentFacade, "documents", True),
            },
        }
