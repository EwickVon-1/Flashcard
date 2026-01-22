from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import render, redirect

from .forms import Gradeform, NewCard, NewSet
from .models import Card, Set, User
# Create your views here.
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
            return render(request, "auctions/login.html", {
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
    pass

# Look at a Flashcard Set
def set(request, id, name):
    set = Set.objects.get(id=id)
    cards = Card.objects.filter(set = set)
    return render(request, "cards/set.html", {
        "name": name,
        "content": set,
        "cards": cards
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
            set.owner = request.user
            set.save()
            return redirect("index")
        else:
            messages.error(request, "Form not Valid")

    form = NewSet()

    return render(request, "cards/create.html", {
        "form": form
    })

# Add new cards to a flashcard set
@login_required
def edit(request, id, name):
    set = Set.objects.get(id=id)

    # Checks if the user is actually the owner
    if request.user != set.owner:
        messages.error(request, "You do not have permission to edit this Flashcard Set")
        return redirect("set", id=id, name=name)

    # If the user submits the form, save it
    if request.method == "POST":
        form = NewCard(request.POST)

        if form.is_valid():
            # Save it to the correct Flashcard Set
            card = form.save(commit=False)
            card.set = set
            card.save()
            return redirect("set", id=id, name=name)

        messages.error(request, "Form not Valid")

    form = NewCard()

    return render(request, "cards/edit.html", {
        "id": id,
        "name": name,
        "form": form
    })

def study(request, set_id, name):

    # Create a study queue, if there doesn't exist any yet
    QUEUE_KEY = f"queue.{set_id}"
    if QUEUE_KEY not in request.session:
        # Set a new queue session to that initial set of cards
        request.session[QUEUE_KEY] = []

        # Get initial cards to add to the queue (currently all of them)
        card_ids = Card.objects.filter(set_id = set_id).values_list('id', flat=True)

        if not card_ids.exists():
            messages.error("Invalid Cards in Set")
            return redirect("set", id=set_id, name=name)

        request.session[QUEUE_KEY] = list(card_ids)

    # Check if there already exists a "review" key
    REVIEW_KEY = f"review.{set_id}"
    if REVIEW_KEY not in request.session:
        # Create a new review session
        request.session[REVIEW_KEY] = []
    
    # Create two modes: Queue Mode and Review Mode
    if (request.session[QUEUE_KEY]):
        mode = QUEUE_KEY
    elif (request.session[REVIEW_KEY]):
        mode = REVIEW_KEY
    else:
        # End of Study Session
        del request.session[QUEUE_KEY]
        del request.session[REVIEW_KEY]
        return redirect("set", id=set_id, name=name)
    
    # If the user got the card incorrect, save in session to review later
    if request.method == "POST":
        form = Gradeform(request.POST)
        
        if form.is_valid():
            # Extract user choice from the form
            card_id = request.POST.get("card_id")
            grade = form.cleaned_data["grade"]
            if grade == "Incorrect":
                request.session[REVIEW_KEY].append(card_id)
                request.session.modified = True
        return redirect("study", set_id=set_id, name=name)
    
    # Extract the current card
    curr_card_id = request.session[mode].pop(0)
    request.session.modified = True

    current_card = Card.objects.get(id=curr_card_id,
                                    set_id = set_id)
    
    # Calculate remaining cards to inform user
    cards_remaining = len(request.session[QUEUE_KEY]) + len(request.session[REVIEW_KEY]) + 1
    print(cards_remaining)

    return render(request, "cards/study.html", {
        "name": name,
        "set_id": set_id,
        "card_id": curr_card_id,
        "card" : current_card,
        "remaining_cards" : cards_remaining,
        "grade" : Gradeform()
    })