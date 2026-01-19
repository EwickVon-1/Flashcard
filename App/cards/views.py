from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import render, redirect

import random

from .form import NewCard, NewSet
from .models import Set, Card, User
# Create your views here.

def index(request):
    cards = Card.objects.all()
    return render(request, "cards/index.html", {
        "cards": cards
    })

def register(request):
    if request.method == "POST":
        # Save the information from the form
        username = request.POST["username"]
        email = request.POST["email"]

        # Compare password confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "cards/register.html", {
                "message": "Passwords must match."
            })
        
        # Attempt to create a new User
                # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "cards/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return redirect("index")
    else:
        return render(request, "cards/register.html")

def login_view(request):
    if request.method == "POST":
        # Attempt to sign in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect("index")
        else:
            return render(request, "auctions/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "cards/login.html")

def logout_view(request):
    logout(request)
    return redirect("index")

# Look at a Flashcard Set
def set(request, id, name):
    set = Set.objects.get(id=id)
    return render(request, "cards/set.html", {
        "name": name,
        "content": set
    })

# Create a new flashcard set
@login_required
def create(request):
    if request.method == "POST":
        # Save the form, but attach the user
        form = NewSet(request.POST)

        if form.is_valid():
            set = form.save(commit=False)
            # Add user ID and then save the form
            set.user = request.user
            set.save()
        else:
            messages.error(request, "Form not Valid")

    form = NewSet()

    return render(request, "cards/create.html", {
        "form": form
    })

# Add new cards to a flashcard set
@login_required
def add(request):
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