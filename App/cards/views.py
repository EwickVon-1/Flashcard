import json

from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from cards.services.auth_service import register_user
from cards.services.set_service import toggle_save_set
from cards.services.stats_service import get_study_stats
from cards.services.study_service import create_query, get_next_card, process_grade, increment_query, destroy_query
from cards.utils.form_handler import handle_form
from cards.utils.permissions import authenticate_user_permission

from .forms import registerForm, loginForm, Gradeform, NewCard, NewSet
from .models import Card, Set, User, StudyData
# Create your views here.

QUEUE_PREFIX = "queue"

def register(request):
    form, is_valid = handle_form(request, registerForm)
    message = "Invalid registration details."
    if is_valid:
        # Save the information from the form
        username = form.cleaned_data["username"]
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        
        # Attempt to create a new User
        user, error = register_user(username, email, password)
        if error:
            message = error
            return render(request, "cards/register.html", {
                "message": message
            })
        login(request, user)
        return redirect("index")
    
    return render(request, "cards/register.html", {
        "form": form,
        "message": message
    })

def login_view(request):
    form, is_valid = handle_form(request, loginForm)
    message = ""
    if is_valid:
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect("index")
        
        message = "Invalid username and/or password."
    
    return render(request, "cards/login.html", {
        "form": form,
        "message": message
    })

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
    query = request.GET.get("q", "").strip()
    if query:
        results = Set.objects.filter(name__icontains=query)
    else:
        results = Set.objects.all()[:20]

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
    form, is_valid = handle_form(request, NewSet)

    if is_valid:
        flashcard_set = form.save(commit=False)
        # Add user ID and then save the form
        flashcard_set.owner = request.user
        flashcard_set.save()
        return redirect("index")

    form = NewSet()

    return render(request, "cards/create.html", {
        "form": form
    })

# Add new cards to a flashcard set
@login_required
def add(request, set_id, name):
    flashcard_set = get_object_or_404(Set, id=set_id)

    # Checks if the user is actually the owner
    error = authenticate_user_permission(request, flashcard_set, "set_view", set_id, name)
    if error:
        return error

    # If the user submits the form, save it
    form, is_valid = handle_form(request, NewCard)

    if is_valid:
        # Save it to the correct Flashcard Set
        card = form.save(commit=False)
        card.set = flashcard_set
        card.save()
        return redirect("set_view", set_id=set_id, name=name)

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
    authenticate_user_permission(request, flashcard_set, "set_view", set_id, name)

    # If the user submits the form, delete the card
    card = get_object_or_404(Card, set_id=set_id, id=card_id)
    card.delete()
    messages.success(request, f"Deleted Card '{card.question}'")
    return redirect("edit", set_id=set_id, name=name)

@login_required
def delete_set(request, set_id, name):
    flashcard_set = get_object_or_404(Set, id=set_id)

    # Checks if the user is the owner
    authenticate_user_permission(request, flashcard_set, "set_view", set_id, name)
    
    # If the user submits the form, delete the set
    flashcard_set.delete()
    messages.success(request, f"Deleted '{flashcard_set.name}'")
    return redirect("index")
    

@login_required
def edit_view(request, set_id, name):
    flashcard_set = get_object_or_404(Set, id=set_id)
    # Check if the user is actually the owner
    authenticate_user_permission(request, flashcard_set, "set_view", set_id, name)
    
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
    authenticate_user_permission(request, flashcard_set, "set_view", set_id, name)

    card = get_object_or_404(Card, set_id=set_id, id=card_id)

    form, is_valid = handle_form(request, NewCard, instance=card)
    if is_valid:
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

    success, message = toggle_save_set(request.user, flashcard_set)

    if not success:
        messages.error(request, message)
        return redirect("set_view", set_id=set_id, name=name)

    messages.success(request, message)

    return redirect("set_view", set_id=set_id, name=name)

@login_required
def stats(request, set_id=None, name=None):
    base_filter = StudyData.objects.filter(user=request.user)

    if set_id:
        base_filter = base_filter.filter(card__set_id=set_id)

    upcoming_cards, reviewed_cards = get_study_stats(request.user, base_filter, set_id)

    
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
    queue_key = create_query(request, QUEUE_PREFIX, set_id)

    form, is_valid = handle_form(request, Gradeform)
        
    if is_valid:
        card_id = int(request.POST.get("card_id"))
        grade = int(form.cleaned_data["grade"])

        if grade != 0:
            increment_query(request, queue_key)
                
        process_grade(request.user, card_id, set_id, grade)
        return redirect("study", set_id=set_id, name=name)
    
    card_to_study = get_next_card(request.user, set_id)
    
    if not card_to_study:
        destroy_query(request, queue_key)
        messages.success(request, "You have finished studying this Flashcard Set for now. Great job!")
        return redirect("set_view", set_id=set_id, name=name)
    
    return render(request, "cards/study.html", {
            "name": name,
            "set_id": set_id,
            "card_id": card_to_study.id,
            "card" : card_to_study,
            "cards_reviewed" : request.session.get(queue_key, 0),
            "grade" : Gradeform()
        })
