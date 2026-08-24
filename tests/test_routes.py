import unittest

from sqlalchemy import select
from starlette.requests import Request

from app.database import get_db
from app.main import politician_detail_page
from app.models import Politician


class RouteTests(unittest.TestCase):
    def test_politician_detail_page_loads(self):
        db = next(get_db())
        try:
            politician = db.scalar(select(Politician).order_by(Politician.id))
            self.assertIsNotNone(politician)
            request = Request({
                "type": "http",
                "method": "GET",
                "path": f"/politicians/{politician.id}",
                "headers": [],
            })
            response = politician_detail_page(request, politician.id, db, None)
            html = response.body.decode("utf-8")
            self.assertIn(politician.name, html)
        finally:
            db.close()
