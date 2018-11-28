from app import db
from app.api.abstract_facade import JSONAPIAbstractFacade
from app.models import Document


# decorator for test purposes
def decorator_function_with_arguments(arg1, arg2, arg3):
    def wrap(f):
        print("Wrapping", f)
        def wrapped_f(*args):
            print("Inside wrapped_f()")
            res = f(*args)
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
    def get_resource_facade(url_prefix, doc_id):
        e = Document.query.filter(Document.id == doc_id).first()
        if e is None:
            kwargs = {"status": 404}
            errors = [{"status": 404, "title": "document %s does not exist" % doc_id}]
        else:
            kwargs = {}
            errors = []
            e = DocumentFacade(url_prefix, e)
        return e, kwargs, errors

    # noinspection PyArgumentList
    @staticmethod
    @decorator_function_with_arguments("I should be protected", "by an auth", "system !")
    def create_resource(id, attributes, related_resources):
        resource = None
        errors = None
        try:
            _g = attributes.get
            doc = Document(
                id=id,
                title=_g("title"),
                subtitle=_g("subtitle"),
                origin_date_id=_g("origin-date-id")
            )
            doc.editors = related_resources.get("editors")
            db.session.add(doc)
            db.session.commit()
            resource = doc
        except Exception as e:
            print(e)
            errors = [{"status": 403, "title": "Error creating resource 'Document' with data: %s" % (str([id, attributes, related_resources]))}]
            db.session.rollback()
        return resource, errors

    def get_editors_resource_identifiers(self):
        from app.api.editor.facade import EditorFacade
        return [] if self.obj.editors is None else [EditorFacade.make_resource_identifier(e.id, EditorFacade.TYPE)
                                                    for e in self.obj.editors]

    @decorator_function_with_arguments("decorated", "relationship", "getter !")
    def get_editors_resources(self):
        from app.api.editor.facade import EditorFacade
        return [] if self.obj.editors is None else [EditorFacade(self.url_prefix, e,
                                                                 self.with_relationships_links,
                                                                 self.with_relationships_data).resource
                                                    for e in self.obj.editors]

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

        self.relationships = {
            "editors": {
                "links": self._get_links(rel_name="editors"),
                "resource_identifier_getter": self.get_editors_resource_identifiers,
                "resource_getter": self.get_editors_resources
            },
        }
        self.resource = {
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
            self.resource["attributes"]["origin-date-range-label"] = self.obj.origin_date.range_label

        if self.with_relationships_links:
            self.resource["relationships"] = self.get_exposed_relationships()
