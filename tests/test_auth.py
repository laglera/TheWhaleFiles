import unittest
from datetime import timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth
from app.models import Base, Politician, User


class AuthTestCase(unittest.TestCase):
    """Base en memoria: las pruebas no tocan el SQLite del proyecto."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()

        self.user = User(
            email="ana@ejemplo.com",
            password_hash=auth.hash_password("contraseña-larga"),
            display_name="Ana",
            created_at=auth.utcnow(),
        )
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()


class PasswordTests(AuthTestCase):
    def test_verify_accepts_the_right_password(self):
        self.assertTrue(auth.verify_password("contraseña-larga", self.user.password_hash))

    def test_verify_rejects_the_wrong_password(self):
        self.assertFalse(auth.verify_password("otra-cosa", self.user.password_hash))

    def test_hash_is_salted(self):
        # Dos altas con la misma contraseña no pueden dar el mismo hash: si lo
        # dieran, una tabla de hashes revelaría quién comparte contraseña.
        self.assertNotEqual(auth.hash_password("misma"), auth.hash_password("misma"))

    def test_email_is_normalised(self):
        self.assertEqual(auth.normalise_email("  Ana@Ejemplo.COM "), "ana@ejemplo.com")


class CredentialValidationTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        from app.i18n import get_translations

        self.t = get_translations("es")

    def test_valid_credentials_have_no_errors(self):
        self.assertEqual(auth.credential_errors("ana@ejemplo.com", "12345678", self.t), [])

    def test_broken_email_is_reported(self):
        self.assertIn(
            self.t["auth_error_email"], auth.credential_errors("ana", "12345678", self.t)
        )

    def test_short_password_is_reported(self):
        self.assertIn(
            self.t["auth_error_short"], auth.credential_errors("ana@ejemplo.com", "abc", self.t)
        )

    def test_password_over_the_bcrypt_limit_is_reported(self):
        # bcrypt sólo procesa 72 bytes; más allá se rechaza en el formulario en
        # lugar de dejar que la librería reviente al hashear.
        long_password = "a" * (auth.MAX_PASSWORD_BYTES + 1)
        self.assertIn(
            self.t["auth_error_long"],
            auth.credential_errors("ana@ejemplo.com", long_password, self.t),
        )


class SessionTests(AuthTestCase):
    def test_session_resolves_back_to_its_user(self):
        token = auth.create_session(self.db, self.user)
        session = auth.resolve_session(self.db, token)

        self.assertIsNotNone(session)
        self.assertEqual(session.user.email, "ana@ejemplo.com")

    def test_raw_token_is_not_stored(self):
        token = auth.create_session(self.db, self.user)
        session = auth.resolve_session(self.db, token)
        self.assertNotEqual(session.token_hash, token)

    def test_unknown_token_resolves_to_nothing(self):
        auth.create_session(self.db, self.user)
        self.assertIsNone(auth.resolve_session(self.db, "inventado"))

    def test_empty_token_resolves_to_nothing(self):
        self.assertIsNone(auth.resolve_session(self.db, None))
        self.assertIsNone(auth.resolve_session(self.db, ""))

    def test_expired_session_is_rejected_and_removed(self):
        token = auth.create_session(self.db, self.user)
        session = auth.resolve_session(self.db, token)
        session.expires_at = auth.utcnow() - timedelta(seconds=1)
        self.db.commit()

        self.assertIsNone(auth.resolve_session(self.db, token))
        self.assertEqual(self.db.scalar(select(User.id)), self.user.id)

    def test_destroyed_session_no_longer_resolves(self):
        token = auth.create_session(self.db, self.user)
        auth.destroy_session(self.db, token)
        self.assertIsNone(auth.resolve_session(self.db, token))

    def test_sessions_are_independent(self):
        # Salir en un dispositivo no puede cerrar la sesión de los demás.
        first = auth.create_session(self.db, self.user)
        second = auth.create_session(self.db, self.user)
        auth.destroy_session(self.db, first)

        self.assertIsNone(auth.resolve_session(self.db, first))
        self.assertIsNotNone(auth.resolve_session(self.db, second))


class FollowTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.politician = Politician(
            name="Alex Morgan", chamber="Senate", state="California", party="Democratic"
        )
        self.db.add(self.politician)
        self.db.commit()

    def test_follow_then_unfollow(self):
        self.assertFalse(auth.is_following(self.db, self.user, self.politician.id))

        auth.follow(self.db, self.user, self.politician.id)
        self.assertTrue(auth.is_following(self.db, self.user, self.politician.id))

        auth.unfollow(self.db, self.user, self.politician.id)
        self.assertFalse(auth.is_following(self.db, self.user, self.politician.id))

    def test_following_twice_does_not_duplicate(self):
        # Un doble clic, o volver atrás y reenviar el formulario, no puede dejar
        # dos filas: la restricción de unicidad daría error en la segunda.
        auth.follow(self.db, self.user, self.politician.id)
        auth.follow(self.db, self.user, self.politician.id)

        self.assertEqual(len(self.user.follows), 1)

    def test_unfollowing_what_was_never_followed_is_harmless(self):
        auth.unfollow(self.db, self.user, self.politician.id)
        self.assertEqual(len(self.user.follows), 0)

    def test_visitor_without_session_follows_nobody(self):
        self.assertFalse(auth.is_following(self.db, None, self.politician.id))


if __name__ == "__main__":
    unittest.main()
