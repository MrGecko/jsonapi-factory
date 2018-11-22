
from tests.base_server import TestBaseServer
from app import db


class TestGetRoutes(TestBaseServer):

    def load_fixtures(self):
        from ..data.fixtures.dataset001 import load_fixtures as load_dataset001
        with self.app.app_context():
            load_dataset001(db)

    def test_pagination(self):
        self._test_pagination_links("documents")
        self._test_pagination_links("documents/1")
        self._test_pagination_links("documents?page[size]=1")
        self._test_pagination_links("documents?page[size]=1&page[number]=2")
        self._test_pagination_links("documents?page[size]=2&page[number]=1")
        self._test_pagination_links("documents?page[number]=3")

        self._test_pagination_links("documents/1/editors")
        self._test_pagination_links("documents/2/editors?page[size]=1")
        self._test_pagination_links("documents/2/editors?page[size]=1&page[number]=2")
        self._test_pagination_links("documents/2/editors?page[size]=2&page[number]=1")
        self._test_pagination_links("documents/2/editors?page[number]=3")

    def test_relationships_routes(self):
        pass
