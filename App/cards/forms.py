from django import forms
from .models import Card, Set

class loginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

class registerForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords must match.")

        return cleaned_data

class NewSet(forms.ModelForm):
    class Meta:
        model = Set
        fields = ["name", 
                  "description"]
        widgets = {
        "description": forms.Textarea(attrs={"rows": 5})
        }

class AddToSetForm(forms.Form):
    existing_set = forms.ModelChoiceField(
        queryset=Set.objects.none(),  # overridden in view
        required=False,
        empty_label="-- Add to existing set --"
    )
    
class NewCard(forms.ModelForm):
    class Meta:
        model = Card
        fields = ["question",
                  "answer"]
        widgets = {
        "answer": forms.Textarea(attrs={"rows": 5})
        }

class Gradeform(forms.Form):
    choices = [
        (0, "Again"),
        (1, "Hard"),
        (2, "Good"),
        (3, "Easy")
    ]

    grade = forms.ChoiceField(choices=choices, widget=forms.RadioSelect)

class SearchForm(forms.Form):
    query = forms.CharField(
        label="Search",
        max_length=200,
        widget=forms.TextInput(attrs={
            "placeholder": "Enter search terms",
            "class": "form-control"
        })
    )
