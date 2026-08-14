import unittest

from starlette.requests import Request

from app.database import get_db
from app.main import politician_detail_page


class RouteTests(unittest.TestCase):
    def test_politician_detail_page_loads(self):
        request = Request({"type": "http", "method": "GET", "path": "/politicians/1", "headers": []})
        db = next(get_db())
        try:
            response = politician_detail_page(request, 1, db)
            html = response.body.decode("utf-8")
        finally:
            db.close()

        self.assertIn("Alex Morgan", html)
