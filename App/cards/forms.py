from django import forms
from .models import Card, Set

class NewSet(forms.ModelForm):
    class Meta:
        model = Set
        fields = ["name", 
                  "description"]
    
    widgets = {
        "description": forms.Textarea(attrs={"rows": 5})
    }


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
        ("Correct", "Correct"),
        ("Incorrect", "Incorrect")
    ]

    grade = forms.ChoiceField(choices=choices, widget=forms.RadioSelect)