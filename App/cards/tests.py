from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import base64, hashlib

from cards.utils.oauth_pkce import (
    generate_code_verifier,
    generate_code_challenge,
    get_auth_url,
    request_token,
    refresh_token,
    get_valid_token,
)
from cards.models import SpotifyToken

User = get_user_model()


class CodeVerifierTests(TestCase):

    def test_default_length(self):
        verifier = generate_code_verifier()
        self.assertEqual(len(verifier), 128)

    def test_custom_length(self):
        verifier = generate_code_verifier(length=64)
        self.assertEqual(len(verifier), 64)

    def test_invalid_length_too_short(self):
        with self.assertRaises(ValueError):
            generate_code_verifier(length=42)

    def test_invalid_length_too_long(self):
        with self.assertRaises(ValueError):
            generate_code_verifier(length=129)

    def test_allowed_characters(self):
        import string
        allowed = set(string.ascii_letters + string.digits + "-._~")
        verifier = generate_code_verifier()
        self.assertTrue(set(verifier).issubset(allowed))

    def test_uniqueness(self):
        # Astronomically unlikely to collide
        self.assertNotEqual(generate_code_verifier(), generate_code_verifier())


class CodeChallengeTests(TestCase):

    def test_challenge_matches_spec(self):
        """Manually compute the expected challenge and compare."""
        verifier = "test_verifier_string"
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        expected = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
        self.assertEqual(generate_code_challenge(verifier), expected)

    def test_no_padding(self):
        challenge = generate_code_challenge(generate_code_verifier())
        self.assertNotIn("=", challenge)

    def test_url_safe(self):
        challenge = generate_code_challenge(generate_code_verifier())
        self.assertNotIn("+", challenge)
        self.assertNotIn("/", challenge)

class GetAuthUrlTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="pass")

    def test_returns_spotify_url(self):
        request = self.factory.get("/")
        request.session = {}
        url = get_auth_url(request)
        self.assertIn("https://accounts.spotify.com/authorize", url)

    def test_url_contains_required_params(self):
        request = self.factory.get("/")
        request.session = {}
        url = get_auth_url(request)
        for param in ["code_challenge", "code_challenge_method=S256",
                      "response_type=code", "client_id"]:
            self.assertIn(param, url)

    def test_verifier_stored_in_session(self):
        request = self.factory.get("/")
        request.session = {}
        get_auth_url(request)
        self.assertIn("spotify_code_verifier", request.session)


class RequestTokenTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="pass")

    def _make_request(self, session_data=None):
        request = self.factory.get("/")
        request.user = self.user
        request.session = session_data or {"spotify_code_verifier": "test_verifier"}
        return request

    @patch("cards.utils.oauth_pkce.requests.post")
    def test_successful_token_exchange(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "access_abc",
            "refresh_token": "refresh_xyz",
            "expires_in": 3600,
        }

        request = self._make_request()
        result = request_token(request, "auth_code_123")

        self.assertTrue(result)
        token = SpotifyToken.objects.get(user=self.user)
        self.assertEqual(token.access_token, "access_abc")
        self.assertEqual(token.refresh_token, "refresh_xyz")

    @patch("cards.utils.oauth_pkce.requests.post")
    def test_failed_token_exchange(self, mock_post):
        mock_post.return_value.status_code = 400

        request = self._make_request()
        result = request_token(request, "bad_code")

        self.assertFalse(result)
        self.assertFalse(SpotifyToken.objects.filter(user=self.user).exists())

    def test_missing_verifier_returns_false(self):
        request = self._make_request(session_data={})  # no verifier
        result = request_token(request, "auth_code_123")
        self.assertFalse(result)

    @patch("cards.utils.oauth_pkce.requests.post")
    def test_verifier_removed_from_session_after_use(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "a", "refresh_token": "r", "expires_in": 3600
        }
        request = self._make_request()
        request_token(request, "code")
        self.assertNotIn("spotify_code_verifier", request.session)


class RefreshTokenTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass")
        self.token = SpotifyToken.objects.create(
            user=self.user,
            access_token="old_access",
            refresh_token="old_refresh",
            expires_at=timezone.now() - timedelta(hours=1),  # already expired
        )

    @patch("cards.utils.oauth_pkce.requests.post")
    def test_successful_refresh(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "new_access",
            "expires_in": 3600,
        }
        result = refresh_token(self.token)

        self.assertTrue(result)
        self.token.refresh_from_db()
        self.assertEqual(self.token.access_token, "new_access")
        self.assertEqual(self.token.refresh_token, "old_refresh")  # unchanged

    @patch("cards.utils.oauth_pkce.requests.post")
    def test_refresh_token_rotated(self, mock_post):
        """Spotify sometimes returns a new refresh token."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }
        refresh_token(self.token)
        self.token.refresh_from_db()
        self.assertEqual(self.token.refresh_token, "new_refresh")

    @patch("cards.utils.oauth_pkce.requests.post")
    def test_failed_refresh(self, mock_post):
        mock_post.return_value.status_code = 401
        result = refresh_token(self.token)
        self.assertFalse(result)


class GetValidTokenTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass")

    def test_no_token_returns_none(self):
        self.assertIsNone(get_valid_token(self.user))

    def test_valid_token_returned_directly(self):
        SpotifyToken.objects.create(
            user=self.user,
            access_token="valid_token",
            refresh_token="refresh",
            expires_at=timezone.now() + timedelta(hours=1),  # not expired
        )
        self.assertEqual(get_valid_token(self.user), "valid_token")

    @patch("cards.utils.oauth_pkce.refresh_token")
    def test_expired_token_triggers_refresh(self, mock_refresh):
        mock_refresh.return_value = True
        token = SpotifyToken.objects.create(
            user=self.user,
            access_token="expired_token",
            refresh_token="refresh",
            expires_at=timezone.now() - timedelta(hours=1),  # expired
        )
        get_valid_token(self.user)
        mock_refresh.assert_called_once_with(token)

    @patch("cards.utils.oauth_pkce.refresh_token", return_value=False)
    def test_failed_refresh_returns_none(self, _):
        SpotifyToken.objects.create(
            user=self.user,
            access_token="expired",
            refresh_token="refresh",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertIsNone(get_valid_token(self.user))
