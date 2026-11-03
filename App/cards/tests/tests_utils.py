
from django.core.exceptions import PermissionDenied

from cards.forms import RegisterForm
from cards.models import Set
from cards.utils.form_handler import handle_form
from cards.utils.permissions import authenticate_user_permission

from .base import FAST_PASSWORD_HASHER, BaseDatabaseTestCase, make_request, make_user


class HandleRegisterFormTests(BaseDatabaseTestCase):

    def test_valid_post(self):
        request = make_request(method="post")

        request.POST = {
            "username": "newuser",
            "email": "new@example.com",
            "password1": "StrongPassword123!",
            "password2": "StrongPassword123!",
        }

        form, is_valid = handle_form(
            request,
            RegisterForm
        )

        self.assertTrue(is_valid)
        self.assertEqual(form.cleaned_data["username"], "newuser")
        self.assertEqual(form.cleaned_data["email"], "new@example.com")

    def test_invalid_email(self):
        request = make_request(method="post")

        request.POST = {
            "username": "newuser",
            "email": "invalid-email",
            "password1": "StrongPassword123!",
            "password2": "StrongPassword123!",
        }

        form, is_valid = handle_form(request, RegisterForm)

        self.assertFalse(is_valid)
        self.assertIn("email", form.errors)

    @FAST_PASSWORD_HASHER
    def test_duplicate_email(self):
        user = make_user()

        request = make_request(method="post")

        request.POST = {
            "username": "newuser",
            "email": user.email,
            "password1": "StrongPassword123!",
            "password2": "StrongPassword123!",
        }

        form, is_valid = handle_form(request, RegisterForm)

        self.assertFalse(is_valid)
        self.assertIn("email", form.errors)

    def test_password_mismatch(self):
        request = make_request(method="post")

        request.POST = {
            "username": "newuser",
            "email": "new@example.com",
            "password1": "StrongPassword123!",
            "password2": "DifferentPassword123!",
        }

        form, is_valid = handle_form(request, RegisterForm)

        self.assertFalse(is_valid)
        self.assertIn("password2", form.errors)

    def test_get_request(self):
        request = make_request(method="get")

        form, is_valid = handle_form(request, RegisterForm)

        self.assertFalse(is_valid)
        self.assertIsInstance(form, RegisterForm)
        self.assertFalse(form.is_bound)

@FAST_PASSWORD_HASHER
class AuthenticateUserPermissionTests(BaseDatabaseTestCase):
   
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user()
        cls.other_user = make_user()


    def setUp(self):
        super().setUp()

        params = {
                "owner": self.owner,
                "name": "Test_Set_Name",
                "description": "This is a sample description.",
                }

        self.flashcard_set = Set.objects.create(**params)

    def test_owner_has_permission(self):
        request = make_request(user=self.owner)

        result = authenticate_user_permission(
            request,
            self.flashcard_set
        )

        self.assertIsNone(result)

    def test_other_user_denied_permission(self):
        request = make_request(user=self.other_user)

        with self.assertRaises(PermissionDenied):
            authenticate_user_permission(
                request,
                self.flashcard_set
            )

    def test_anonymous_user_denied_permission(self):
        request = make_request()

        with self.assertRaises(PermissionDenied):
            authenticate_user_permission(
                request,
                self.flashcard_set
            )
