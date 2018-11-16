from app.api.abstract_facade import JSONAPIAbstractFacade


class DocumentFacade(JSONAPIAbstractFacade):
    """

    """
    TYPE = "document"
    TYPE_PLURAL = "documents"

    @property
    def id(self):
        return self.obj.id

    @property
    def type(self):
        return self.TYPE

    @property
    def type_plural(self):
        return self.TYPE_PLURAL

    def get_editors_resource_identifiers(self):
        from app.api.editor.facade import EditorFacade
        return [] if self.obj.editors is None else [EditorFacade.make_resource_identifier(e.id, EditorFacade.TYPE)
                                                    for e in self.obj.editors]

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
            },
            "meta": self.meta,
            "links": {
                "self": self.self_link
            }
        }

        if self.obj.origin_date:
            self.resource["attributes"]["origin-date-interval-label"] = self.obj.origin_date.interval_label

        if self.with_relationships_links:
            self.resource["relationships"] = self.get_exposed_relationships()


