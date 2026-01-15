from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, redirect

import random

from .form import NewCard
from .models import Card
# Create your views here.

def index(request):
    cards = Card.objects.all()
    return render(request, "cards/index.html", {
        "cards": cards
    })

def create(request):
    # If the user submits the form, save it
    if request.method == "POST":
        form = NewCard(request.POST)

        if form.is_valid():
            form.save()
            return redirect("index")

        messages.error(request, "Form not Valid")

    form = NewCard()

    return render(request, "cards/create.html", {
        "form": form
    })

def entry(request):
    pass