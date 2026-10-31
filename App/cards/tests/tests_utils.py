import base64
import hashlib
import unittest
from datetime import timedelta
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from cards.models import GoogleToken
from cards.utils.google_oauth import GoogleOAuthService


class CodeVerifierTest(unittest.TestCase):
    def test_default(self):
        verifier = GoogleOAuthService._generate_code_verifier()
        self.assertEqual(len(verifier), 128)

    def test_custom_length(self):
        verifier = GoogleOAuthService._generate_code_verifier(length=64)
        self.assertEqual(len(verifier), 64)

    def test_lower_bound(self):
        verifier = GoogleOAuthService._generate_code_verifier(length=43)
        self.assertEqual(len(verifier), 43)

    def test_out_of_bounds(self):
        with self.assertRaises(ValueError):
            GoogleOAuthService._generate_code_verifier(length=42)

        with self.assertRaises(ValueError):
            GoogleOAuthService._generate_code_verifier(length=129)


    def test_invalid_input(self):
        for length in (82.5, "64", None, [], True, False):
            with self.subTest(length=length), self.assertRaises(TypeError):
                GoogleOAuthService._generate_code_verifier(length) # type: ignore

    def test_output(self):
        import string

        allowed = string.ascii_letters + string.digits + "-._~"
        verifier = GoogleOAuthService._generate_code_verifier()

        self.assertIsInstance(verifier, str)
        self.assertTrue(set(verifier).issubset(allowed))

    def test_uniqueness(self):
        self.assertNotEqual(GoogleOAuthService._generate_code_verifier(), GoogleOAuthService._generate_code_verifier())

class CodeChallengeTest(unittest.TestCase):
    def setUp(self):
        self.verifier = GoogleOAuthService._generate_code_verifier(43)

    def test_challenge_matches_expected(self):
        """Manually compute the expected challenge and compare."""
        verifier = "a" * 64

        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        expected = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

        self.assertEqual(GoogleOAuthService._generate_code_challenge(verifier), expected)

    def test_output_is_string(self):
        challenge = GoogleOAuthService._generate_code_challenge(self.verifier)

        self.assertIsInstance(challenge, str)

    def test_no_padding(self):
        challenge = GoogleOAuthService._generate_code_challenge(self.verifier)

        self.assertNotIn("=", challenge)

    def test_deterministic(self):
        first = GoogleOAuthService._generate_code_challenge(self.verifier)
        second = GoogleOAuthService._generate_code_challenge(self.verifier)

        self.assertEqual(first, second)

    def test_uniqueness(self):
        verifier1 = "a" * 64
        verifier2 = "b" * 64

        self.assertNotEqual(
            GoogleOAuthService._generate_code_challenge(verifier1), GoogleOAuthService._generate_code_challenge(verifier2)
        )

    def test_url_safe(self):
        challenge = GoogleOAuthService._generate_code_challenge(self.verifier)
        self.assertNotIn("+", challenge)
        self.assertNotIn("/", challenge)

    def test_non_string_input(self):
        for verifier in (None, 123, True, b"abc"):
            with self.subTest(verifier=verifier), self.assertRaises(TypeError):
                GoogleOAuthService._generate_code_challenge(verifier) # type: ignore

    def test_empty_string(self):
        with self.assertRaises(ValueError):
            GoogleOAuthService._generate_code_challenge("")

    def test_verifier_too_short(self):
        with self.assertRaises(ValueError):
            GoogleOAuthService._generate_code_challenge("a" * 42)

    def test_verifier_too_long(self):
        with self.assertRaises(ValueError):
            GoogleOAuthService._generate_code_challenge("a" * 129)

    def test_invalid_characters(self):
        with self.assertRaises(ValueError):
            GoogleOAuthService._generate_code_challenge("a" * 42 + " " + "b")


@override_settings(
    GOOGLE_CLIENT_ID="test-client-id",
    GOOGLE_SCOPE="youtube.readonly",
    GOOGLE_REDIRECT_URI="http://localhost:8000/auth/callback/",
)
class GetAuthUrlTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get("/")

        self.request.session = {} # type: ignore

    @patch(
        "cards.utils.google_oauth.GoogleOAuthService._generate_code_challenge",
        return_value="test-code-challenge",
    )
    @patch(
        "cards.utils.google_oauth.GoogleOAuthService._generate_code_verifier",
        return_value="test-code-verifier",
    )
    @patch(
        "cards.utils.google_oauth.secrets.token_urlsafe",
        return_value="test-oauth-state",
    )
    def test_returns_valid_url(
        self, mock_token_urlsafe, mock_code_verifier, mock_code_challenge
    ):
        url = GoogleOAuthService.get_authorization_url(self.request)

        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        self.assertEqual(parsed_url.scheme, "https")
        self.assertEqual(parsed_url.netloc, "accounts.google.com")
        self.assertEqual(parsed_url.path, "/o/oauth2/v2/auth")

        params = {
            "response_type": "code",
            "client_id": "test-client-id",
           "scope": "youtube.readonly",
            "redirect_uri": "http://localhost:8000/auth/callback/",
            "access_type": "offline",
            "code_challenge_method": "S256",
            "code_challenge": "test-code-challenge",
            "state": "test-oauth-state",
        }

        for param, value in params.items():
            self.assertIn(param, query_params)
            self.assertEqual([value], query_params[param])

        # Verify that session stores correctly
        self.assertEqual(
                self.request.session[GoogleOAuthService._SESSION_KEY],
                {
                    "verifier": "test-code-verifier",
                    "state": "test-oauth-state",
                },
                )

        # Verify that mock tests ran validly
        mock_token_urlsafe.assert_called_once_with(32)
        mock_code_verifier.assert_called_once_with()
        mock_code_challenge.assert_called_once_with("test-code-verifier")

    def test_request_without_session(self):
        new_request = self.factory.get("/")

        with self.assertRaises(AttributeError):
            GoogleOAuthService.get_authorization_url(new_request)

    def test_none_request(self):
        with self.assertRaises(AttributeError):
            GoogleOAuthService.get_authorization_url(None)

@override_settings(
    GOOGLE_CLIENT_ID="test-client-id",
    GOOGLE_CLIENT_SECRET="test-client-secret",
    GOOGLE_REDIRECT_URI="http://localhost:8000/auth/callback/",
)
class RequestTokenTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.post("/oauth/callback")

        middleware = SessionMiddleware(lambda request: HttpResponse())
        middleware.process_request(self.request)
        self.request.session.save()

        User = get_user_model()
        self.user = User.objects.create_user( # type: ignore
                username ="oauth-test-user",
                email = "oauth-test@example.com",
                password = "test-password"
)

        self.request.user = self.user

        # Store test state and verifiers
        self.transaction = {
                "verifier": "expected-code",
                "state": "expected-state"
                }

        self.request.session[GoogleOAuthService._SESSION_KEY] = (
                self.transaction.copy()
                )

        # We create a Mock response 
        self.valid_response = {
                "access_token": "test-access-token",
                "expires_in": 3600,
                "refresh_token": "test-refresh-token"
                }

    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token") 
    def test_successful_token_exchange(self, mock_exchange):
        mock_exchange.return_value = self.valid_response

        result = GoogleOAuthService.request_token(self.request, "authorization_code", "expected-state")
        self.assertTrue(result)

        # Ensure that we passed in the correct args
        args, _ = mock_exchange.call_args
        payload = args[0]
        
        self.assertEqual(payload["client_id"], "test-client-id")
        self.assertEqual(payload["client_secret"], "test-client-secret")
        self.assertEqual(payload["grant_type"], "authorization_code")
        self.assertEqual(payload["code"], "authorization_code")
        self.assertEqual(payload["redirect_uri"], "http://localhost:8000/auth/callback/")
        self.assertEqual(payload["code_verifier"], "expected-code")

        # Ensure that Google was contacted
        mock_exchange.assert_called_once()

        # Verify that the token was saved
        token = GoogleToken.objects.get(user=self.user)

        self.assertEqual(token.access_token, "test-access-token")
        self.assertEqual(token.refresh_token, "test-refresh-token")
        
        self.assertGreater(token.expires_at, timezone.now())
        
        # Check that the session has been popped
        self.assertNotIn(
                    GoogleOAuthService._SESSION_KEY,
                    self.request.session,
                )
        
    def test_code_not_string(self):
        for invalid in (None, 123, True):
            with self.subTest(invalid=invalid), self.assertRaises(TypeError):
                GoogleOAuthService.request_token(self.request, invalid, "expected-state") # type: ignore

    def test_state_not_string(self):
        for invalid in (None, 123, True):
            with self.subTest(invalid=invalid), self.assertRaises(TypeError):
                GoogleOAuthService.request_token(self.request, "expected-code", invalid) # type: ignore

    def test_empty_code(self):
        result = GoogleOAuthService.request_token(self.request, "", "expected-state")
        self.assertFalse(result)

    def test_empty_state(self):
        result = GoogleOAuthService.request_token(self.request, "expected-code", "")
        self.assertFalse(result)

    def test_diff_state(self):
        result = GoogleOAuthService.request_token(self.request, "expected-code", "unexpected-state")
        self.assertFalse(result)
        self.assertIn(
                GoogleOAuthService._SESSION_KEY,
                self.request.session,
            )

    def test_invalid_transaction(self):
            invalid_transactions = [
                None,
                [],
                "invalid",
                {},
                {"state": "expected-state"},
                {"verifier": "expected-code-verifier"},
                {"state": 123, "verifier": "expected-code-verifier"},
                {"state": "expected-state", "verifier": None},
                {"state": "", "verifier": ""},
            ]

            for transaction in invalid_transactions:
                with self.subTest(transaction=transaction):
                    self.request.session[
                        GoogleOAuthService._SESSION_KEY
                    ] = transaction

                    result = GoogleOAuthService.request_token(
                        self.request,
                        "authorization-code",
                        "expected-state",
                    )

                self.assertFalse(result)

    @patch(
            "cards.utils.google_oauth.GoogleOAuthService._exchange_token"
        )
    def test_invalid_transaction_does_not_exchange_token(self, mock_exchange):
            self.request.session[GoogleOAuthService._SESSION_KEY] = {
                "state": "expected-state",
                "verifier": None,
            }

            result = GoogleOAuthService.request_token(
                self.request,
                "authorization-code",
                "expected-state",
            )

            self.assertFalse(result)
            mock_exchange.assert_not_called()

            @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
            def test_exchange_token_fails(self, mock_exchange):
                mock_exchange.return_value = {}

                result = GoogleOAuthService.request_token(
                        self.request,
                        "authorization-code",
                        "expected-state"
                        )

                self.assertFalse(result)

    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
    def test_refresh_token_is_optional(self, mock_exchange):
        response = {
            "access_token": "new-access-token",
            "expires_in": 3600
        }

        mock_exchange.return_value = response

        result = GoogleOAuthService.request_token(
            self.request,
            "authorization-code",
            "expected-state"
        )

        self.assertTrue(result)

        token = GoogleToken.objects.get(user=self.user)

        self.assertEqual(token.access_token, "new-access-token")

    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
    def test_existing_refresh_token_is_preserved(self, mock_exchange):
        GoogleToken.objects.create(
            user=self.user,
            access_token="old-access-token",
            refresh_token="old-refresh-token",
            expires_at=timezone.now() + timedelta(hours=1)
        )

        return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600
        }

        mock_exchange.return_value = return_value

        result = GoogleOAuthService.request_token(
            self.request,
            "authorization-code",
            "expected-state"
        )

        self.assertTrue(result)

        token = GoogleToken.objects.get(user=self.user)

        self.assertEqual(token.access_token, "new-access-token")
        self.assertEqual(token.refresh_token, "old-refresh-token")

    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
    def test_transaction_used_twice(self, mock_exchange):
        mock_exchange.return_value = self.valid_response

        first_result = GoogleOAuthService.request_token(
                self.request,
                "authorization-code",
                "expected-state"
                )

        second_result = GoogleOAuthService.request_token(
                self.request,
                "authorization-code",
                "expected-state"
                )

        self.assertTrue(first_result)
        self.assertFalse(second_result)

@override_settings(
        GOOGLE_CLIENT_ID = "test-client-id",
        GOOGLE_CLIENT_SECRET = "test-client-secret"
        )
class RefreshTokenTests(TestCase):
 
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user( # type: ignore
                username ="oauth-test-user",
                email = "oauth-test@example.com",
                password = "test-password"
                )

        self.token = GoogleToken.objects.create(
                user = self.user,
                access_token = "test-access-token",
                refresh_token = "test-refresh-token",
                expires_at = timezone.now() + timedelta(seconds = 3600)
                )

        self.valid_response = {
            "access_token": "new-access-token",
            "expires_in": 3600,
            "refresh_token": "new-refresh-token"
        } 

    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
    def test_successful_token_refresh(self, mock_exchange):
        mock_exchange.return_value = self.valid_response

        result = GoogleOAuthService._refresh_token(self.token)
        self.assertTrue(result)


        # Validate that the payload contains the correct information
        args, _ = mock_exchange.call_args

        payload = args[0]

        self.assertEqual(payload["grant_type"], "refresh_token")
        self.assertEqual(payload["refresh_token"], "test-refresh-token")
        self.assertEqual(payload["client_id"], "test-client-id")
        self.assertEqual(payload["client_secret"], "test-client-secret")

        # Ensure that Google was contacted
        mock_exchange.assert_called_once()

        # Verify that the token was saved
        token = GoogleToken.objects.get(user=self.user)

        self.assertEqual(token.access_token, "new-access-token")
        self.assertEqual(token.refresh_token, "new-refresh-token") 
        self.assertGreater(token.expires_at, timezone.now())
        
    def test_invalid_token(self):
        for invalid in [None, 500, "token", False]:
            with self.subTest(token=invalid), self.assertRaises(TypeError):
                GoogleOAuthService._refresh_token(invalid)
    
    def test_missing_refresh_token(self):
        self.token.refresh_token = None

        self.assertFalse(GoogleOAuthService._refresh_token(self.token))

    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
    def test_exchange_token_fails(self, mock_exchange):
        mock_exchange.return_value = {}

        self.assertFalse(GoogleOAuthService._refresh_token(self.token))

class TestExchangeToken(SimpleTestCase):
    def setUp(self):
        self.payload = {
                "grant_type": "authorization-code",
                "code": "test-code-verifier",
                }

        # Create a mock response from Google
        self.valid_response = Mock()
        self.valid_response.ok = True
        self.valid_response.status_code = 200
        self.valid_response.json.return_value = {
                "access_token": "test-access-token",
                "expires_in": 3600,
                "refresh_token": "test-refresh-token",
                }
    @patch("cards.utils.google_oauth.requests.post")
    def test_successful_token_exchange(self, mock_post):
        mock_post.return_value = self.valid_response

        # Check if data is valid
        result = GoogleOAuthService._exchange_token(self.payload)
        self.assertEqual(result.get("access_token"), "test-access-token")
        self.assertEqual(result.get("expires_in"), 3600)
        self.assertEqual(result.get("refresh_token"), "test-refresh-token")

        # Ensure that google was contacted
        mock_post.assert_called_once()

        # Check if payload to Google is correct
        _, kwargs = mock_post.call_args

        self.assertEqual(kwargs["data"], self.payload)
        self.assertEqual(kwargs["timeout"], 10)
        self.assertEqual(
            kwargs["headers"]["Content-Type"],
            "application/x-www-form-urlencoded",
        )

    def test_invalid_payload(self):
        for payload in (None, [], "invalid", 123):
            with self.subTest(payload=payload), self.assertRaises(TypeError):
                GoogleOAuthService._exchange_token(payload) # type: ignore

    @patch("cards.utils.google_oauth.requests.post")
    def test_http_fails(self, mock_post):
        response = Mock()
        response.valid_response.ok = False
        response.status_code = 400

        mock_post.return_value = response
        result = GoogleOAuthService._exchange_token(self.payload)
        self.assertEqual(result, {})

    @patch("cards.utils.google_oauth.requests.post")
    def test_invalid_json_returned(self, mock_post):
       response = Mock() 
       response.valid_response.ok = True
       response.status_code = 200

       for invalid in [5, "access_token", -45, None]:
           with self.subTest(data=invalid):
               response.json.return_value = invalid
               mock_post.return_value = response

               self.assertEqual(GoogleOAuthService._exchange_token(self.payload), {})

    @patch("cards.utils.google_oauth.requests.post")
    def test_request_failure(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException("Network Error")

        result = GoogleOAuthService._exchange_token(self.payload)

        self.assertEqual(result, {})

    @patch("cards.utils.google_oauth.requests.post")
    def test_invalid_json_response(self, mock_post):
        response = Mock()
        response.ok = True
        response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = response

        result = GoogleOAuthService._exchange_token(self.payload)

        self.assertEqual(result, {})

    @patch("cards.utils.google_oauth.requests.post")
    def test_invalid_access_token(self, mock_post):
        invalid_values = (None, "", 123, True, [])

        for invalid in invalid_values:
            with self.subTest(access_token=invalid):
                response = Mock()
                response.ok = True
                response.json.return_value = {
                    "access_token": invalid,
                    "expires_in": 3600,
                }
                mock_post.return_value = response

                result = GoogleOAuthService._exchange_token(
                    self.payload
                )

                self.assertEqual(result, {})

    @patch("cards.utils.google_oauth.requests.post")
    def test_invalid_expiration(self, mock_post):
        invalid_values = (
            None,
            0,
            -1,
            True,
            "3600",
            45.23,
            float("inf"),
            float("-inf"),
            float("nan"),
        )

        for invalid in invalid_values:
            with self.subTest(expires_in=invalid):
                response = Mock()
                response.ok = True
                response.json.return_value = {
                    "access_token": "test-access-token",
                    "expires_in": invalid,
                }
                mock_post.return_value = response

                result = GoogleOAuthService._exchange_token(
                    self.payload
                )

                self.assertEqual(result, {})
        

class TestGetToken(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user( # type: ignore
            username ="oauth-test-user",
            email = "oauth-test@example.com",
            password = "test-password"
            )

        self.token = GoogleToken.objects.create(
                user = self.user,
                access_token = "test-access-token",
                refresh_token = "test-refresh-token",
                expires_at = timezone.now() + timedelta(seconds = 3600)
                )

    def test_valid_token(self):
        result = GoogleOAuthService.get_valid_token(self.user)

        self.assertEqual(result, "test-access-token")

    def test_no_token(self):
        User = get_user_model()
        user2 = User.objects.create_user(  # type: ignore
            username ="test-user2",
            email = "oauth-test2@example.com",
            password = "test-password"
            )

        result = GoogleOAuthService.get_valid_token(user2)
        self.assertEqual(result, None)

    def test_expired_no_refresh(self):
        self.token.refresh_token = None
        self.token.expires_at = timezone.now()

        result = GoogleOAuthService.get_valid_token(self.user)
        self.assertEqual(result, None)

    @patch("cards.utils.google_oauth.GoogleOAuthService._refresh_token")
    def test_expired_refresh_fails(self, mock_refresh):
        mock_refresh.return_value = False
        self.token.expires_at = timezone.now()

        result = GoogleOAuthService.get_valid_token(self.user)
        self.assertEqual(result, None)
  
    @patch("cards.utils.google_oauth.GoogleOAuthService._refresh_token")
    def test_expired_refresh_success(self, mock_refresh):
        def side_effect(token):
            token.access_token = "new-access-token"
            token.refresh_token = "new-refresh-token"
            token.expires_at = timezone.now() + timedelta(hours=1)
            token.save()
            return True

        mock_refresh.side_effect = side_effect

        result = GoogleOAuthService.get_valid_token(self.user)
        self.assertTrue(result)
