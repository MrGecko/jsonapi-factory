

def load_fixtures(db):

    print("loading fixtures")
    from .dataset001 import load_fixtures as load_dataset001

    load_dataset001(db)

