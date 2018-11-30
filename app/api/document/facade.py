from app.api.abstract_facade import JSONAPIAbstractFacade
from app.models import Document


# decorator for test purposes
def decorator_function_with_arguments(arg1, arg2, arg3):
    def wrap(f):
        print("Wrapping", f)
        def wrapped_f(*args, **kwargs):
            print("Inside wrapped_f()")
            res = f(*args, **kwargs)
            return res
        return wrapped_f
    return wrap


class DocumentFacade(JSONAPIAbstractFacade):
    """

    """
    TYPE = "document"
    TYPE_PLURAL = "documents"

    @property
    def id(self):
        return self.obj.id

    @staticmethod
    @decorator_function_with_arguments("decorated", "resource", "!")
    def get_resource_facade(url_prefix, doc_id, **kwargs):
        e = Document.query.filter(Document.id == doc_id).first()
        if e is None:
            kwargs = {"status": 404}
            errors = [{"status": 404, "title": "document %s does not exist" % doc_id}]
        else:
            e = DocumentFacade(url_prefix, e, **kwargs)
            kwargs = {}
            errors = []
        return e, kwargs, errors

    @staticmethod
    def create_resource(model, obj_id, attributes, related_resources):
        if "origin-date-range-label" in attributes:
            attributes["origin_date"] = attributes.pop("origin-date-range-label")
        return JSONAPIAbstractFacade.create_resource(model, obj_id, attributes, related_resources)

    @property
    def resource(self):
        resource = {
            **self.resource_identifier,
            "attributes": {
                "id": self.obj.id,
                "title": self.obj.title,
                "subtitle": self.obj.subtitle,
                "origin-date-id": self.obj.origin_date.id if self.obj.origin_date else None
            },
            "meta": self.meta,
            "links": {
                "self": self.self_link
            }
        }

        if self.obj.origin_date:
            resource["attributes"]["origin-date-range-label"] = self.obj.origin_date.range_label

        if self.with_relationships_links:
            resource["relationships"] = self.get_exposed_relationships()

        return resource

    def __init__(self, *args, **kwargs):
        super(DocumentFacade, self).__init__(*args, **kwargs)
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

        from app.api.editor.facade import EditorFacade
        self.relationships = {
            "editors": {
                "links": self._get_links(rel_name="editors"),
                "resource_identifier_getter": self.get_related_resource_identifiers(EditorFacade, "editors", to_many=True),
                "resource_getter": self.get_related_resources(EditorFacade, "editors", to_many=True),
            },
        }
