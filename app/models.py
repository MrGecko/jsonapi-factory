from app import db

from app.search import add_to_index, remove_from_index, query_index


class SearchableMixin(object):

    __searchable__ = []

    @classmethod
    def search(cls, expression, fields=None, page=None, per_page=None, index=None):

        # by default, search on the model table
        # custom index allow to use multiple indexes: index="table1,table2,table3..."
        if index is None:
            index = cls.__tablename__

        # perform the query
        print(page, per_page)
        results, total = query_index(index=index, query=expression,
                                 fields=fields, page=page, per_page=per_page)
        print(expression, results, total)
        if total == 0:
            return cls.query.filter_by(id=0), 0
        when = []
        #TODO recuperer les indexes et faire les bonnes requetes/jointures
        ids = [r.id for r in results]

        if len(ids) == 0:
            return cls.query.filter_by(id=0), 0

        for i in range(len(ids)):
            when.append((ids[i], i))

        #print("test")
        #print("when:", when)
        #for idx in index.split(","):
        #    obj = db.session.query(MODELS_HASH_TABLE[idx]).filter()
        #    print(idx, obj)
        return cls.query.filter(cls.id.in_(ids)).order_by(
            db.case(when, value=cls.id)), total

    @classmethod
    def before_commit(cls, session):
        session._changes = {
            'add': list(session.new),
            'update': list(session.dirty),
            'delete': list(session.deleted)
        }

    @classmethod
    def after_commit(cls, session):
        for obj in session._changes['add']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['update']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['delete']:
            if isinstance(obj, SearchableMixin):
                remove_from_index(obj.__tablename__, obj)
        session._changes = None

    @classmethod
    def reindex(cls):
        for obj in cls.query:
            add_to_index(cls.__tablename__, obj)


db.event.listen(db.session, 'before_commit', SearchableMixin.before_commit)
db.event.listen(db.session, 'after_commit', SearchableMixin.after_commit)


association_editor_edits_document = db.Table('editor_edits_document',
    db.Column('editor_id', db.Integer, db.ForeignKey('editor.id'), primary_key=True),
    db.Column('document_id', db.Integer, db.ForeignKey('document.id'), primary_key=True),
)


class DateRange(SearchableMixin, db.Model):
    """ """
    __tablename__ = 'date_range'
    __searchable__ = []

    id = db.Column("id", db.Integer, primary_key=True, autoincrement=True)

    begin = db.Column("begin", db.Date, nullable=False)
    begin_label = db.Column("begin_label", db.String(10))
    begin_confidence = db.Column("begin_confidence", db.Float, default=1)

    end = db.Column("end", db.Date)
    end_label = db.Column("end_label", db.String(10))
    end_confidence = db.Column("end_confidence", db.Float)

    @property
    def range(self):
        if self.end:
            return "%s-%s" % (self.begin, self.end)
        else:
            return str(self.begin)

    @property
    def range_label(self):
        if self.end_label:
            return "%s-%s" % (self.begin_label, self.end_label)
        else:
            return self.begin_label


class Document(SearchableMixin, db.Model):
    """ """
    __tablename__ = 'document'
    __searchable__ = ['title', 'subtitle']

    id = db.Column("id", db.Integer, primary_key=True, autoincrement=True)
    title = db.Column("title", db.String(256))
    subtitle = db.Column("subtitle", db.String(256))

    origin_date_id = db.Column("origin_date_id", db.Integer, db.ForeignKey("date_range.id"))
    origin_date = db.relationship("DateRange")


class Editor(SearchableMixin, db.Model):
    """ """
    __tablename__ = 'editor'
    __searchable__ = ['name']

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)

    # relationships
    documents = db.relationship("Document", secondary=association_editor_edits_document, backref=db.backref('editors'))

