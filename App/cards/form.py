from django import forms
from .models import Card

class NewCard(forms.ModelForm):
    class Meta:
        model = Card
        fields = ["question",
                  "answer"]

    widgets = {
        "answer": forms.Textarea(attrs={"rows": 5})
    }
    