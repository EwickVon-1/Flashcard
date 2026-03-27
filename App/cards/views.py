from datetime import date, timedelta
import json

from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404

from .forms import Gradeform, NewCard, NewSet
from .models import Card, Set, User, StudyData
# Create your views here.

MAX_CARDS_TO_STUDY = 10

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
            return render(request, "cards/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "cards/login.html")

def logout_view(request):
    logout(request)
    return redirect("index")

@login_required
def index(request):
    owned_sets = Set.objects.filter(owner=request.user)
    saved_sets = Set.objects.filter(saved_by=request.user)


    return render(request, "cards/index.html", {
        "owned_sets" : owned_sets, 
        "saved_sets" : saved_sets
    })

def search(request):
    query = request.GET.get("q", "")
    if query:
        results = Set.objects.filter(name__icontains=query)
    else:
        results = Set.objects.none()

    return render(request, "cards/search.html", {
        "query": query,
        "results": results
    })

# Look at a Flashcard Set
def set_view(request, set_id, name):
    flashcard_set = get_object_or_404(Set, id=set_id)
    cards = Card.objects.filter(set = flashcard_set)
    return render(request, "cards/set.html", {
        "name": name,
        "content": flashcard_set,
        "cards": cards
    })

# Create a new flashcard set
@login_required
def create(request):
    if request.method == "POST":
        # Save the form, but attach the user
        form = NewSet(request.POST)

        if form.is_valid():
            flashcard_set = form.save(commit=False)
            # Add user ID and then save the form
            flashcard_set.owner = request.user
            flashcard_set.save()
            return redirect("index")
        else:
            messages.error(request, "Form not Valid")

    form = NewSet()

    return render(request, "cards/create.html", {
        "form": form
    })

# Add new cards to a flashcard set
@login_required
def add(request, set_id, name):
    flashcard_set = get_object_or_404(Set, id=set_id)

    # Checks if the user is actually the owner
    if request.user != flashcard_set.owner:
        messages.error(request, "You do not have permission to add a card to this Flashcard Set")
        return redirect("set_view", set_id=set_id, name=name)

    # If the user submits the form, save it
    if request.method == "POST":
        form = NewCard(request.POST)

        if form.is_valid():
            # Save it to the correct Flashcard Set
            card = form.save(commit=False)
            card.set = flashcard_set
            card.save()
            return redirect("set_view", set_id=set_id, name=name)

        messages.error(request, "Form not Valid")

    form = NewCard()

    return render(request, "cards/add.html", {
        "id": set_id,
        "name": name,
        "form": form
    })

@login_required
def delete_card(request, set_id, name, card_id):
    flashcard_set = get_object_or_404(Set, id=set_id)

    # Checks if the user is the owner
    if request.user != flashcard_set.owner:
        messages.error(request, "You do not have permission to delete a card from this Flashcard Set")
        return redirect("set_view", set_id=set_id, name=name)
    
    # If the user submits the form, delete the card
    card = get_object_or_404(Card, set_id=set_id, id=card_id)
    card.delete()
    messages.success(request, f"Deleted Card '{card.question}'")
    return redirect("edit", set_id=set_id, name=name)

@login_required
def delete_set(request, set_id, name):
    flashcard_set = get_object_or_404(Set, id=set_id)

    # Checks if the user is the owner
    if request.user != flashcard_set.owner:
        messages.error(request, "You do not have permission to delete this Flashcard Set")
        return redirect("set_view", set_id=set_id, name=name)
    
    # If the user submits the form, delete the set
    flashcard_set.delete()
    messages.success(request, f"Deleted '{flashcard_set.name}'")
    return redirect("index")
    

@login_required
def edit_view(request, set_id, name):
    flashcard_set = get_object_or_404(Set, id=set_id)
    # Check if the user is actually the owner
    if request.user != flashcard_set.owner: 
        messages.error(request, "You do not have permission edit this Flashcard Set")
        return redirect("set_view", set_id=set_id, name=name)
    
    card = Card.objects.filter(set_id=set_id)
        
    return render(request, "cards/edit.html", {
        "set_id" : set_id,
        "cards" : card,
        "set_name" : name
    })

@login_required
def edit_card(request, set_id, name, card_id): 
    flashcard_set = get_object_or_404(Set, id=set_id)
    # Check if the user is actually the owner
    if request.user != flashcard_set.owner: 
        messages.error(request, "You do not have permission edit this Flashcard Set")
        return redirect("set_view", set_id=set_id, name=name)
    
    # POST METHOD
    card = get_object_or_404(Card, set_id=set_id, id=card_id)

    if request.method == "POST":
        form = NewCard(request.POST, instance=card)

        if form.is_valid():
            form.save()
            return redirect("edit", set_id=set_id, name=name)
    
    form = NewCard(instance=card)
    
    return render(request, "cards/edit_card.html", {
        "set_id" : set_id,
        "card_id" : card_id,
        "form" : form,
        "name" : name
    })

@login_required
def save_set(request, set_id, name):
    flashcard_set = get_object_or_404(Set, id=set_id)

    # If the user is the owner, they can't save their own set
    if request.user == flashcard_set.owner:
        messages.error(request, "You cannot save your own Flashcard Set")
        return redirect("set_view", set_id=set_id, name=name)

    # If the user has already saved the set, they unsave the set
    if request.user in flashcard_set.saved_by.all():
        flashcard_set.saved_by.remove(request.user)
        messages.success(request, f"Removed '{flashcard_set.name}' from saved sets.")
        return redirect("set_view", set_id=set_id, name=name)
    
    # Otherwise, save the set for the user
    request.user.saved_sets.add(flashcard_set)
    messages.success(request, f"Saved '{flashcard_set.name}' to your saved sets.")
    return redirect("set_view", set_id=set_id, name=name)

@login_required
def stats(request, set_id=None, name=None):
    base_filter = StudyData.objects.filter(user=request.user)
    if set_id:
        base_filter = base_filter.filter(card__set_id=set_id)

    upcoming_cards = (base_filter
                      .filter(user=request.user, 
                              due_date__lte=date.today() + timedelta(days=7))
                      .values("due_date")
                      .annotate(count=Count("id"))
                      .order_by("due_date")) 

    reviewed_cards = (base_filter
                      .filter(user=request.user, 
                              last_studied__gte=date.today() - timedelta(days=30))
                      .values("last_studied")
                      .annotate(count=Count("id"))
                      .order_by("last_studied"))
    
    upcoming_cards_data = {
    "labels": [card["due_date"].strftime("%Y-%m-%d") for card in upcoming_cards],
    "values": [card["count"] for card in upcoming_cards],
    }

    reviewed_cards_data = {
    "labels": [card["last_studied"].strftime("%Y-%m-%d") for card in reviewed_cards],
    "values": [card["count"] for card in reviewed_cards],
    }


    return render(request, "cards/stats.html", {
        "name": name,
        "username": request.user.username,
        "upcoming_cards_data": json.dumps(upcoming_cards_data),
        "reviewed_cards_data": json.dumps(reviewed_cards_data)
    })





@login_required
def study(request, set_id, name):
    
    # Get the next card to study for the user. There are three cases:
    # 1. If there are cards that are due for review, return the card with the earliest due date
    # 2. If there are no cards that are due for review, but there are still cards that haven't been studied, return one of those cards
    # 3. If there are no cards left to study, redirect to the set view

    QUEUE_KEY = f"queue.{set_id}"
    
    if QUEUE_KEY not in request.session:
        request.session[QUEUE_KEY] = 0

    if request.session[QUEUE_KEY] == MAX_CARDS_TO_STUDY:
        del request.session[QUEUE_KEY]
        messages.success(request, "You have finished studying this Flashcard Set for now. Great job!")        
        return redirect("set_view", set_id=set_id, name=name)

    if request.method == "POST":
        form = Gradeform(request.POST)
        
        if form.is_valid():
            card_id = int(request.POST.get("card_id"))
            grade = int(form.cleaned_data["grade"])

            if grade != 0:
                request.session[QUEUE_KEY] += 1
                request.session.modified = True
                
            card = get_object_or_404(Card, id=card_id, set_id=set_id)
            study_data, created = StudyData.objects.get_or_create(user=request.user, card=card)
            study_data.update_study_data(grade)
            return redirect("study", set_id=set_id, name=name)
    
    cards_in_set = Card.objects.filter(set_id=set_id)
    study_data = StudyData.objects.filter(user=request.user,
                                          card__set_id=set_id,
                                          due_date__lte=date.today()).order_by("due_date").first()    
    unstudied_card = cards_in_set.exclude(studied_card__user=request.user).first()
    
    if study_data:
        card_to_study = study_data.card
    elif unstudied_card:
        card_to_study = unstudied_card
    else:
        del request.session[QUEUE_KEY]
        messages.success(request, "You have finished studying this Flashcard Set for now. Great job!")
        return redirect("set_view", set_id=set_id, name=name)
    
    
    return render(request, "cards/study.html", {
            "name": name,
            "set_id": set_id,
            "card_id": card_to_study.id,
            "card" : card_to_study,
            "cards_reviewed" : request.session[QUEUE_KEY],
            "grade" : Gradeform()
        })
