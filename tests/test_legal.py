"""Lo que la web le dice a quien la lee antes de invertir: el aviso de que no
es asesoramiento, los términos, la privacidad y que no se avisa a terceros de
cada visita."""

import unittest

from app.security import content_security_policy
from tests.test_http import call


class DisclaimerTests(unittest.TestCase):
    def test_every_page_says_it_is_not_financial_advice(self):
        # Quien llega a una ficha desde un buscador no pasa por la portada: el
        # aviso tiene que ir en la plantilla base, no en una página concreta.
        for path in ("/", "/legal", "/no-existe"):
            _status, _headers, body = call("GET", path)
            self.assertIn("No es asesoramiento financiero".encode(), body, path)

    def test_the_notice_is_translated(self):
        _status, _headers, body = call("GET", "/", b"lang=en")
        self.assertIn(b"Not financial advice", body)


class LegalPageTests(unittest.TestCase):
    def test_it_carries_terms_and_privacy(self):
        status, headers, body = call("GET", "/legal")
        self.assertEqual(status, 200)
        self.assertIn(b"text/html", headers[b"content-type"])
        for anchor in (b'id="aviso"', b'id="terminos"', b'id="privacidad"'):
            self.assertIn(anchor, body)
        self.assertIn("Sesgo de supervivencia".encode(), body)
        self.assertIn("brutos".encode(), body)

    def test_english_version(self):
        _status, _headers, body = call("GET", "/legal", b"lang=en")
        self.assertIn(b"Terms of use", body)
        self.assertIn(b"Survivorship", body)

    def test_the_footer_links_it(self):
        _status, _headers, body = call("GET", "/")
        self.assertIn(b"/legal?lang=es#privacidad", body)

    def test_it_is_in_the_sitemap(self):
        _status, _headers, body = call("GET", "/sitemap.xml")
        self.assertIn(b"<loc>http://testserver/legal</loc>", body)


class FontTests(unittest.TestCase):
    def test_no_page_asks_google_for_fonts(self):
        # Cada visita le entregaba a Google la IP del visitante.
        _status, _headers, body = call("GET", "/")
        self.assertNotIn(b"fonts.googleapis.com", body)
        self.assertNotIn(b"fonts.gstatic.com", body)
        self.assertIn(b"/static/fonts/inter-latin.woff2", body)

    def test_the_policy_only_allows_local_fonts(self):
        policy = content_security_policy("n")
        self.assertIn("font-src 'self';", policy)
        self.assertNotIn("googleapis", policy)

    def test_the_font_files_are_served(self):
        status, headers, body = call("GET", "/static/fonts/inter-latin.woff2")
        self.assertEqual(status, 200)
        self.assertTrue(body.startswith(b"wOF2"))


if __name__ == "__main__":
    unittest.main()
