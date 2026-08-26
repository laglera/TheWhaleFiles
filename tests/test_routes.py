import unittest

from starlette.requests import Request

from app.main import politician_detail_page
from tests.support import memory_session, seed_declarant


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.db = memory_session()
        self.person = seed_declarant(self.db)

    def tearDown(self):
        self.db.close()

    def test_politician_detail_page_loads(self):
        request = Request({
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": ("testserver", 80),
            "path": f"/politicians/{self.person.id}",
            "query_string": b"",
            "headers": [],
        })
        response = politician_detail_page(request, self.person.id, self.db, None)
        html = response.body.decode("utf-8")
        self.assertIn(self.person.name, html)
