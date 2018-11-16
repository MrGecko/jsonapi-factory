from datetime import date, datetime


def format_date(d):
    return datetime.strptime(d, '%Y')


def load_fixtures(db):

    from app.models import Editor
    from app.models import Document
    from app.models import DateInterval

    dargaud = Editor(name="Dargaud")
    atalante = Editor(name="Atalante")

    doc1 = Document(title="Document 1", subtitle="Sous-titre 1")
    doc1.editors.append(dargaud)
    doc1.origin_date = DateInterval(begin=format_date("1563"), begin_label="1563",
                                    end=format_date("1570"), end_label="1570")


    doc2 = Document(title="Document 2", subtitle="Sous-titre 2")
    doc2.editors.append(atalante)
    doc2.editors.append(dargaud)
    doc2.origin_date = DateInterval(begin=format_date("1459"), begin_label="1459")

    db.session.add(dargaud)
    db.session.add(atalante)
    db.session.add(doc1)
    db.session.add(doc2)

    db.session.commit()

