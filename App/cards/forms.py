from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import Card, Set


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = get_user_model()
        fields = ["username", "email", "password1", "password2"]

    def clean_email(self):
        model = get_user_model()
        email = self.cleaned_data["email"]

        if model.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")

        return email


class NewSet(forms.ModelForm):
    class Meta:
        model = Set
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}


class AddToSetForm(forms.Form):
    existing_set = forms.ModelChoiceField(
        queryset=Set.objects.none(),  # overridden in view
        required=False,
        empty_label="-- Add to existing set --",
    )


class NewCard(forms.ModelForm):
    class Meta:
        model = Card
        fields = ["question", "answer"]
        widgets = {"answer": forms.Textarea(attrs={"rows": 5})}


class Gradeform(forms.Form):
    card_id = forms.IntegerField(widget=forms.HiddenInput())
    choices = [(0, "Again"), (1, "Hard"), (2, "Good"), (3, "Easy")]

    grade = forms.ChoiceField(choices=choices, widget=forms.RadioSelect)


class SearchForm(forms.Form):
    query = forms.CharField(
        label="Search",
        max_length=200,
        widget=forms.TextInput(
            attrs={"placeholder": "Enter search terms", "class": "form-control"}
        ),
    )
