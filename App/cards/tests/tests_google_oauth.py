import string
from datetime import timedelta
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import requests
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from cards.models import GoogleToken
from cards.tests.base import (
    FAST_PASSWORD_HASHER,
    GOOGLE_SETTINGS,
    BaseDatabaseTestCase,
    BaseTestCase,
    FrozenTime,
    fake_response,
    make_google_token,
    make_request,
    make_user,
)
from cards.utils.google_oauth import GoogleOAuthService


class CodeVerifierTest(SimpleTestCase):
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
        allowed = string.ascii_letters + string.digits + "-._~"
        verifier = GoogleOAuthService._generate_code_verifier()

        self.assertIsInstance(verifier, str)
        self.assertTrue(set(verifier).issubset(allowed))

    def test_uniqueness(self):
        self.assertNotEqual(GoogleOAuthService._generate_code_verifier(), GoogleOAuthService._generate_code_verifier())

class CodeChallengeTest(SimpleTestCase):
    def setUp(self):
        self.verifier = GoogleOAuthService._generate_code_verifier(43)

    def test_challenge_matches_expected(self):
        """Used an example of a SHA256 code_challenge from RFC 7636"""
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"

        expected = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

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

@override_settings(**GOOGLE_SETTINGS)
class GetAuthUrlTests(TestCase):

    def setUp(self):
        self.request = make_request()

        self.request.session = {}
        
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

    def test_code_challenge_matches_session_verifier(self):
        url = GoogleOAuthService.get_authorization_url(self.request)

        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        # Retrieve the verifier stored in the session
        session_data = self.request.session[GoogleOAuthService._SESSION_KEY]
        verifier = session_data["verifier"]

        # Generate the expected challenge using the session verifier
        expected_challenge = GoogleOAuthService._generate_code_challenge(verifier)

        self.assertEqual(
            query_params["code_challenge"][0],
            expected_challenge,
        )

    def test_request_without_session(self):
        new_request = make_request()

        with self.assertRaises(AttributeError):
            GoogleOAuthService.get_authorization_url(new_request)

    def test_none_request(self):
        with self.assertRaises(AttributeError):
            GoogleOAuthService.get_authorization_url(None)

    def test_consecutive_calls_generate_unique_values_and_overwrite_session(self):
        # First call
        first_url = GoogleOAuthService.get_authorization_url(self.request)
        first_session = self.request.session[GoogleOAuthService._SESSION_KEY].copy()

        first_params = parse_qs(urlparse(first_url).query)

        # Second call
        second_url = GoogleOAuthService.get_authorization_url(self.request)
        second_session = self.request.session[GoogleOAuthService._SESSION_KEY].copy()

        second_params = parse_qs(urlparse(second_url).query)

        # Verify that generated values are unique
        self.assertNotEqual(first_session["verifier"], second_session["verifier"])
        self.assertNotEqual(first_session["state"], second_session["state"])
        self.assertNotEqual(
            first_params["code_challenge"],
            second_params["code_challenge"],
        )

        # Verify that the session contains the second call's values
        self.assertEqual(
            self.request.session[GoogleOAuthService._SESSION_KEY],
            second_session,
        )

        self.assertNotEqual(first_session, second_session)

        # Verify that the second URL contains the second call's state
        self.assertEqual(second_params["state"][0], second_session["state"])

@FAST_PASSWORD_HASHER
@override_settings(**GOOGLE_SETTINGS)
class RequestTokenTests(BaseDatabaseTestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()

    def setUp(self):
        self.request = make_request(
                user=self.user,
                method="post",
                with_session=True,
                path="/oauth/callback",
                )

        self.transaction = {
                "verifier": "expected-code",
                "state": "expected-state",
                }

        self.request.session[GoogleOAuthService._SESSION_KEY] = (
                self.transaction.copy()
                )

        self.valid_response = {
            "access_token": "test-access-token",
            "expires_in": 3600,
            "refresh_token": "test-refresh-token",
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

    def test_no_verifier(self):
        self.request.session[GoogleOAuthService._SESSION_KEY] = {
                "state": "expected-state"
                }
        result = GoogleOAuthService.request_token(self.request, "expected-code", "expected-state")
        self.assertFalse(result)


    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token") 
    def test_user_not_auth(self, mock_exchange):
        user2 = Mock()
        user2.is_authenticated = False
        self.request.user = user2
        result = GoogleOAuthService.request_token(self.request, "expected-code", "expected-state")
        self.assertFalse(result)
        
        mock_exchange.assert_not_called()

    def test_diff_state(self):
        result = GoogleOAuthService.request_token(self.request, "expected-code", "unexpected-state")
        self.assertFalse(result)
        self.assertIn(
                GoogleOAuthService._SESSION_KEY,
                self.request.session,
            )


    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token") 
    def test_invalid_transaction(self, mock_exchange):
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
                    mock_exchange.assert_not_called()
                    

    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
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


    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
    def test_invalid_client_id(self, mock_exchange):
        with override_settings(GOOGLE_CLIENT_ID = None), self.assertRaises(ImproperlyConfigured):
            GoogleOAuthService.request_token(self.request, "authorization-code", "expected-state")

        mock_exchange.assert_not_called()

    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
    def test_invalid_secret_key(self, mock_exchange):
        with override_settings(GOOGLE_CLIENT_SECRET = None), self.assertRaises(ImproperlyConfigured):
            GoogleOAuthService.request_token(self.request, "authorization-code", "expected-state")

        mock_exchange.assert_not_called()

    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
    def test_invalid_redirect_uri(self, mock_exchange):
        with override_settings(GOOGLE_REDIRECT_URI = None), self.assertRaises(ImproperlyConfigured):
            GoogleOAuthService.request_token(self.request, "authorization-code", "expected-state")

        mock_exchange.assert_not_called()


@FAST_PASSWORD_HASHER
@override_settings(**GOOGLE_SETTINGS)
class RefreshTokenTests(BaseDatabaseTestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()

    def setUp(self):
        self.token = make_google_token(self.user)

        self.valid_response = {
            "access_token": "new-access-token",
            "expires_in": 3600,
            "refresh_token": "new-refresh-token",
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

        with self.assertLogs("cards.utils.google_oauth", level="WARNING"):
            self.assertFalse(GoogleOAuthService._refresh_token(self.token))

    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
    def test_exchange_token_fails(self, mock_exchange):
        mock_exchange.return_value = {}

        self.assertFalse(GoogleOAuthService._refresh_token(self.token))

    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
    def test_existing_refresh_token_is_preserved(self, mock_exchange):
        mock_exchange.return_value = {
                "access_token": "new-access-token",
                "expires_in": 3600,
                }

        result = GoogleOAuthService._refresh_token(self.token)
        self.assertTrue(result)

        # Verify that the token was saved with the old refresh_token
        token = GoogleToken.objects.get(user=self.user)

        self.assertEqual(token.refresh_token, "test-refresh-token")

    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
    def test_invalid_client_id(self, mock_exchange):
        with override_settings(GOOGLE_CLIENT_ID = None), self.assertRaises(ImproperlyConfigured):
            GoogleOAuthService._refresh_token(self.token)

        mock_exchange.assert_not_called()

    @patch("cards.utils.google_oauth.GoogleOAuthService._exchange_token")
    def test_invalid_secret_key(self, mock_exchange):
        with override_settings(GOOGLE_CLIENT_SECRET = None), self.assertRaises(ImproperlyConfigured):
            GoogleOAuthService._refresh_token(self.token)

        mock_exchange.assert_not_called()

class TestExchangeToken(BaseTestCase):
    def setUp(self):
        self.payload = {
                "grant_type": "authorization-code",
                "code": "test-code-verifier",
                }

        # Create a mock response from Google
        self.valid_response = fake_response(
            json={
                "access_token": "test-access-token",
                "expires_in": 3600,
                "refresh_token": "test-refresh-token",
            })

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
        response = fake_response(json = {}, ok=False, status=400)

        mock_post.return_value = response
        with self.assertLogs("cards.utils.google_oauth", level="WARNING"):
            result = GoogleOAuthService._exchange_token(self.payload)
            self.assertEqual(result, {})

    @patch("cards.utils.google_oauth.requests.post")
    def test_invalid_json_returned(self, mock_post):
        response = fake_response(json = {})

        for invalid in [5, "access_token", -45, None]:
            with self.subTest(data=invalid):
                response.json.return_value = invalid
                mock_post.return_value = response

                with self.assertLogs("cards.utils.google_oauth", level="WARNING"):
                    self.assertEqual(GoogleOAuthService._exchange_token(self.payload), {})

    @patch("cards.utils.google_oauth.requests.post")
    def test_request_failure(self, mock_post):

        mock_post.side_effect = requests.RequestException("Network Error")

        with self.assertLogs("cards.utils.google_oauth", level="WARNING"):
            result = GoogleOAuthService._exchange_token(self.payload)

            self.assertEqual(result, {})

    @patch("cards.utils.google_oauth.requests.post")
    def test_invalid_json_response(self, mock_post):
        response = fake_response(json={}, ok=True, json_error=ValueError("Invalid JSON"))

        mock_post.return_value = response

        with self.assertLogs("cards.utils.google_oauth", level="WARNING"):
            result = GoogleOAuthService._exchange_token(self.payload)

            self.assertEqual(result, {})

    @patch("cards.utils.google_oauth.requests.post")
    def test_invalid_access_token(self, mock_post):
        invalid_values = (None, "", 123, True, [])

        for invalid in invalid_values:
            with self.subTest(access_token=invalid):
                response = fake_response(json = {
                    "access_token": invalid,
                    "expires_in": 3600
                    })

                mock_post.return_value = response

                with self.assertLogs("cards.utils.google_oauth", level="WARNING"):
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
                response = fake_response(json= {
                    "access_token": "test-access-token",
                    "expires_in": invalid,
                    })

                mock_post.return_value = response

                with self.assertLogs("cards.utils.google_oauth", level="WARNING"):
                    result = GoogleOAuthService._exchange_token(
                        self.payload
                    )

                    self.assertEqual(result, {})
        
@FAST_PASSWORD_HASHER
class GetTokenTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()

    def setUp(self):
        self.token = make_google_token(self.user)

    def get_fresh_user(self):
        User = get_user_model()
        return User.objects.get(pk=self.user.pk)

    def test_valid_token(self):
        result = GoogleOAuthService.get_valid_token(self.user)

        self.assertEqual(result, "test-access-token")

    def test_no_token(self):
        user = make_user()
        result = GoogleOAuthService.get_valid_token(user)
        self.assertEqual(result, "")

    @patch("cards.utils.google_oauth.GoogleOAuthService._refresh_token")
    def test_invalid_access_token(self, mock_refresh):
        self.token.access_token = None

        def side_effect(token):
            token.access_token = "new-access-token"
            token.refresh_token = "new-refresh-token"
            token.expires_at = timezone.now() + timedelta(hours=1)
            token.save()
            return True

        mock_refresh.side_effect = side_effect
        self.token.save()

        result = GoogleOAuthService.get_valid_token(self.get_fresh_user())
        
        mock_refresh.assert_called_once()
        self.assertEqual(result, "new-access-token")


    def test_expired_no_refresh(self):
        self.token.refresh_token = None
        self.token.expires_at = timezone.now()
        self.token.save()

        result = GoogleOAuthService.get_valid_token(self.get_fresh_user())
        self.assertEqual(result, "")

    @patch("cards.utils.google_oauth.GoogleOAuthService._refresh_token")
    def test_expired_refresh_fails(self, mock_refresh):
        mock_refresh.return_value = False
        self.token.expires_at = timezone.now()
        self.token.save()

        result = GoogleOAuthService.get_valid_token(self.user)
        self.assertEqual(result, "")

        mock_refresh.assert_called_once()
  
    @patch("cards.utils.google_oauth.GoogleOAuthService._refresh_token")
    def test_expired_refresh_success(self, mock_refresh):
        def side_effect(token):
            token.access_token = "new-access-token"
            token.refresh_token = "new-refresh-token"
            token.expires_at = timezone.now() + timedelta(hours=1)
            token.save()
            return True

        mock_refresh.side_effect = side_effect
        self.token.expires_at = timezone.now()
        self.token.save()

        result = GoogleOAuthService.get_valid_token(self.get_fresh_user())

        mock_refresh.assert_called_once()
        self.assertEqual(result, "new-access-token") 

        self.token.refresh_from_db()
        self.assertEqual(self.token.refresh_token, "new-refresh-token")

    def test_almost_expired(self): 
        with FrozenTime() as frozen_now:
            self.token.refresh_token = None
            self.token.expires_at = frozen_now + timedelta(seconds=61)
            self.token.save()

            self.assertEqual(GoogleOAuthService.get_valid_token(self.get_fresh_user()), "test-access-token") 

            self.token.expires_at = frozen_now + timedelta(seconds = 60)
            self.token.save()

            self.assertEqual(GoogleOAuthService.get_valid_token(self.get_fresh_user()), "")

            self.token.expires_at = frozen_now + timedelta(seconds = 59)
            self.token.save()

            self.assertEqual(GoogleOAuthService.get_valid_token(self.get_fresh_user()), "")
