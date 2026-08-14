import unittest

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

from app.main import app


@unittest.skipIf(TestClient is None, "httpx not installed in this environment")
class RouteTests(unittest.TestCase):
    def test_politician_detail_page_loads(self):
        client = TestClient(app)
        response = client.get("/politicians/1")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Alex Morgan", response.text)
